import os, sqlite3, math
from collections import defaultdict
try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import OneHotEncoder
    from sklearn.pipeline import Pipeline
    SKLEARN=True
except ImportError:
    SKLEARN=False

DB=os.path.join(os.path.dirname(os.path.abspath(__file__)),"canteen.db")

class DemandPredictor:
    def __init__(self):
        self.model=None
        self.menus=["Veg Thali","Pav Bhaji","Idli Sambar","Rice Bowl","Poha"]
        self.weather=["Sunny","Cloudy","Rainy"]
        self.weekdays=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        self._train()

    def _train(self):
        if not SKLEARN or not os.path.exists(DB): return
        try:
            con=sqlite3.connect(DB)
            rows=con.execute("SELECT weekday,menu,weather,expected_students,meals_sold FROM records").fetchall()
            con.close()
            if len(rows)<8: return
            X=[[r[0],r[1],r[2],r[3]] for r in rows]
            y=[r[4] for r in rows]
            prep=ColumnTransformer([("cat",OneHotEncoder(handle_unknown="ignore"),[0,1,2])],remainder="passthrough")
            self.model=Pipeline([("prep",prep),("rf",RandomForestRegressor(n_estimators=120,random_state=42,min_samples_leaf=2))])
            self.model.fit(X,y)
        except Exception:
            self.model=None

    def predict(self,data):
        weekday,menu,weather,students=data["weekday"],data["menu"],data["weather"],int(data["expected_students"])
        if self.model:
            demand=float(self.model.predict([[weekday,menu,weather,students]])[0])
            method="Random Forest trained on canteen history"
        else:
            factor=0.94
            if weekday in ["Saturday"]: factor-=0.12
            if weekday=="Sunday": factor-=0.55
            if weather=="Rainy": factor-=0.06
            if menu in ["Veg Thali","Pav Bhaji"]: factor+=0.015
            demand=students*factor
            method="Baseline estimator (Random Forest activates after installing dependencies)"
        demand=max(0,min(students*1.15, demand))
        demand=int(round(demand))
        recommended=max(0,math.ceil(demand*1.035))
        surplus=max(0,recommended-demand)
        return {"predicted_demand":demand,"recommended_preparation":recommended,
                "expected_surplus":surplus,"waste_risk":"Low" if surplus<=5 else ("Medium" if surplus<=15 else "High"),
                "method":method}

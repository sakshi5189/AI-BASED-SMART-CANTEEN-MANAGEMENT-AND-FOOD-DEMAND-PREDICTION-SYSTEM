from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3, os, csv, io, math
from datetime import date, timedelta
from predictor import DemandPredictor

APP_DIR=os.path.dirname(os.path.abspath(__file__))
DB=os.path.join(APP_DIR,"canteen.db")
app=Flask(__name__)
app.secret_key=os.environ.get("SECRET_KEY","change-this-secret-in-production")
predictor=DemandPredictor()

def db():
    con=sqlite3.connect(DB)
    con.row_factory=sqlite3.Row
    return con

def init_db():
    con=db()
    con.execute("""CREATE TABLE IF NOT EXISTS records(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        service_date TEXT NOT NULL, weekday TEXT NOT NULL, menu TEXT NOT NULL,
        weather TEXT NOT NULL, expected_students INTEGER NOT NULL,
        meals_prepared INTEGER NOT NULL, meals_sold INTEGER NOT NULL,
        leftovers INTEGER NOT NULL, notes TEXT DEFAULT ''
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS surplus(
        id INTEGER PRIMARY KEY AUTOINCREMENT, service_date TEXT NOT NULL,
        menu TEXT NOT NULL, quantity INTEGER NOT NULL, status TEXT DEFAULT 'Available'
    )""")
    count=con.execute("SELECT COUNT(*) FROM records").fetchone()[0]
    if count==0:
        import random
        random.seed(12)
        menus=["Veg Thali","Pav Bhaji","Idli Sambar","Rice Bowl","Poha"]
        start=date.today()-timedelta(days=75)
        for i in range(75):
            d=start+timedelta(days=i)
            weekday=d.strftime("%A")
            weather=random.choice(["Sunny","Cloudy","Rainy"])
            menu=menus[i%len(menus)]
            base_n=145 if weekday in ["Monday","Tuesday","Wednesday","Thursday"] else 115
            if weekday=="Sunday": base_n=30
            if weather=="Rainy": base_n-=12
            expected=max(20,base_n+random.randint(-18,20))
            sold=max(10,int(expected*random.uniform(.88,1.02)))
            prepared=int(expected*1.04)
            leftovers=max(0,prepared-sold)
            con.execute("""INSERT INTO records(service_date,weekday,menu,weather,expected_students,meals_prepared,meals_sold,leftovers)
                VALUES(?,?,?,?,?,?,?,?)""",(d.isoformat(),weekday,menu,weather,expected,prepared,sold,leftovers))
            if leftovers>=8:
                con.execute("INSERT INTO surplus(service_date,menu,quantity,status) VALUES(?,?,?,'Available')",(d.isoformat(),menu,leftovers))
    con.commit(); con.close()

@app.route("/")
def dashboard():
    con=db()
    totals=con.execute("SELECT COUNT(*) days, COALESCE(SUM(meals_prepared),0) prepared, COALESCE(SUM(meals_sold),0) sold, COALESCE(SUM(leftovers),0) waste FROM records").fetchone()
    recent=con.execute("SELECT * FROM records ORDER BY service_date DESC,id DESC LIMIT 7").fetchall()
    available=con.execute("SELECT * FROM surplus WHERE status='Available' ORDER BY service_date DESC,id DESC LIMIT 8").fetchall()
    menu_stats=con.execute("SELECT menu,SUM(meals_prepared) prepared,SUM(meals_sold) sold,SUM(leftovers) waste FROM records GROUP BY menu ORDER BY waste DESC").fetchall()
    con.close()
    waste_rate=round((totals["waste"]/totals["prepared"]*100),1) if totals["prepared"] else 0
    return render_template("dashboard.html",totals=totals,recent=recent,available=available,menu_stats=menu_stats,waste_rate=waste_rate)

@app.route("/predict",methods=["GET","POST"])
def predict():
    result=None
    if request.method=="POST":
        try:
            students=int(request.form["expected_students"])
            if students<1 or students>10000: raise ValueError("Students must be between 1 and 10,000.")
            data={"expected_students":students,"weekday":request.form["weekday"],"menu":request.form["menu"],"weather":request.form["weather"]}
            result=predictor.predict(data)
            result["menu"]=data["menu"]
            result["weekday"]=data["weekday"]
            result["weather"]=data["weather"]
            result["expected_students"]=students
        except Exception as e:
            flash(str(e),"error")
    return render_template("predict.html",result=result)

@app.route("/records",methods=["GET","POST"])
def records():
    con=db()
    if request.method=="POST":
        try:
            d=request.form["service_date"]
            weekday=date.fromisoformat(d).strftime("%A")
            menu=request.form["menu"].strip()
            weather=request.form["weather"]
            students=int(request.form["expected_students"])
            prepared=int(request.form["meals_prepared"])
            sold=int(request.form["meals_sold"])
            if not menu or min(students,prepared,sold)<0 or max(students,prepared,sold)>10000 or sold>prepared:
                raise ValueError("Please enter valid values. Sold meals cannot exceed prepared meals.")
            leftovers=prepared-sold
            con.execute("""INSERT INTO records(service_date,weekday,menu,weather,expected_students,meals_prepared,meals_sold,leftovers,notes)
                VALUES(?,?,?,?,?,?,?,?,?)""",(d,weekday,menu,weather,students,prepared,sold,leftovers,request.form.get("notes","")))
            if leftovers>0:
                con.execute("INSERT INTO surplus(service_date,menu,quantity,status) VALUES(?,?,?,'Available')",(d,menu,leftovers))
            con.commit()
            predictor._train()
            flash("Daily canteen record saved successfully.","success")
            return redirect(url_for("records"))
        except Exception as e:
            flash(str(e),"error")
    rows=con.execute("SELECT * FROM records ORDER BY service_date DESC,id DESC LIMIT 100").fetchall()
    con.close()
    return render_template("records.html",rows=rows,today=date.today().isoformat())

@app.route("/surplus")
def surplus():
    con=db()
    rows=con.execute("SELECT * FROM surplus ORDER BY service_date DESC,id DESC").fetchall()
    con.close()
    return render_template("surplus.html",rows=rows)

@app.post("/surplus/<int:item_id>/claim")
def claim(item_id):
    con=db()
    con.execute("UPDATE surplus SET status='Claimed' WHERE id=?",(item_id,))
    con.commit(); con.close()
    flash("Surplus listing marked as claimed.","success")
    return redirect(url_for("surplus"))

@app.route("/import",methods=["GET","POST"])
def import_csv():
    if request.method=="POST":
        f=request.files.get("file")
        if not f or not f.filename.lower().endswith(".csv"):
            flash("Please select a CSV file.","error")
            return redirect(url_for("import_csv"))
        try:
            stream=io.StringIO(f.stream.read().decode("utf-8-sig"))
            reader=csv.DictReader(stream)
            required={"service_date","menu","weather","expected_students","meals_prepared","meals_sold"}
            if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
                raise ValueError("CSV headers must include: "+", ".join(sorted(required)))
            con=db(); added=0
            for r in reader:
                d=date.fromisoformat(r["service_date"])
                prepared=int(r["meals_prepared"]); sold=int(r["meals_sold"])
                if sold>prepared: continue
                leftovers=prepared-sold
                con.execute("""INSERT INTO records(service_date,weekday,menu,weather,expected_students,meals_prepared,meals_sold,leftovers)
                    VALUES(?,?,?,?,?,?,?,?)""",(d.isoformat(),d.strftime("%A"),r["menu"],r["weather"],int(r["expected_students"]),prepared,sold,leftovers))
                if leftovers>0:
                    con.execute("INSERT INTO surplus(service_date,menu,quantity,status) VALUES(?,?,?,'Available')",(d.isoformat(),r["menu"],leftovers))
                added+=1
            con.commit(); con.close()
            predictor._train()
            flash(f"Imported {added} records.","success")
            return redirect(url_for("records"))
        except Exception as e:
            flash("Import failed: "+str(e),"error")
    return render_template("import.html")

@app.route("/health")
def health():
    return jsonify({"status":"ok","application":"SmartCanteen AI"})

init_db()
predictor._train()
if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=os.environ.get("FLASK_DEBUG")=="1")

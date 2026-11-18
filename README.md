# SmartCanteen AI – Food Demand Forecasting & Waste Reduction

A working Flask + SQLite college canteen prototype. It predicts meal demand, recommends preparation quantity, stores daily records, estimates surplus, and shows an in-app surplus-food listing.

## Features
- Demand prediction using Random Forest when scikit-learn is installed; safe baseline fallback otherwise.
- Inputs: expected student count, weekday, menu and weather.
- Recommended preparation quantity with a small configurable safety buffer.
- Daily record entry and historical dashboard.
- Surplus-food listings; canteen staff can mark a listing as claimed.
- CSV import for historical data.
- SQLite database is created and seeded automatically on first run.
- Responsive web interface.

## 1. Run locally (Windows)
Install Python 3.10 or newer. Open PowerShell in this folder:

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

If PowerShell blocks activation, run:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

Open http://127.0.0.1:5000

## 2. Run locally (Mac/Linux)
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

## 3. First-time demo
1. Open Dashboard. Demo history is seeded automatically.
2. Open **Predict Demand** and enter tomorrow's expected student count, weekday, menu and weather.
3. Open **Daily Records** to enter actual prepared and sold meals after service.
4. Open **Surplus Food** to see remaining meals and mark them as claimed.
5. Use **Import CSV** to upload `sample_data.csv`.

## 4. Deploy on Render
1. Create a GitHub repository and upload all project files (do not upload `venv/`).
2. Sign in to Render and choose **New + → Web Service**.
3. Connect the GitHub repository.
4. Render detects `render.yaml`, or set:
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app`
5. Deploy. Open the generated HTTPS URL.

**Important deployment note:** SQLite on a free ephemeral web instance may reset when the service restarts/redeploys. For a real college rollout, attach a persistent disk or move the database to managed PostgreSQL. Do not treat the demo seed data as actual canteen records.

## 5. Model and data notes
- The app starts with clearly synthetic demonstration records so the dashboard is not empty.
- Random Forest trains from records stored in SQLite when there are enough rows and dependencies are installed.
- For reliable forecasts, collect at least 4–8 weeks of real daily data. Include dates, menu, weather, expected attendance, meals prepared and meals sold.
- Prediction is a planning estimate, not a guarantee. Staff should review it before cooking.
- The starter model predicts meals sold (demand) from the entered expected student count and context. The safety buffer is 3.5%; edit it in `predictor.py` if your canteen needs another value.

## 6. CSV format
Required columns:
`service_date,menu,weather,expected_students,meals_prepared,meals_sold`

Date format: `YYYY-MM-DD`. Weather values can be Sunny, Cloudy or Rainy. The CSV importer skips rows where sold meals exceed prepared meals.

## 7. Project structure
```text
SmartCanteen_AI/
├── app.py
├── predictor.py
├── requirements.txt
├── Procfile
├── render.yaml
├── sample_data.csv
├── templates/
│   ├── base.html
│   ├── dashboard.html
│   ├── predict.html
│   ├── records.html
│   ├── surplus.html
│   └── import.html
└── static/
    └── style.css
```

## Future improvements for production
- Student login and opt-in notifications (email/WhatsApp/push).
- Role-based access for canteen staff and students.
- PostgreSQL + backups, authentication, audit logs and HTTPS.
- Ingredient-level demand forecasting and food-safety expiry tracking.
- Evaluate MAE/RMSE on a time-based holdout set before using predictions operationally.

## License
Educational project starter. Review security, privacy and food-safety requirements before real deployment.

# Project Overview: WeatherVN

WeatherVN is an AI-powered weather forecasting and storm tracking system specifically designed for the East Sea (Biển Đông) and surrounding regions. It uses real-time data from GFS (NCEP) and GDACS to predict storm trajectories, intensity, and provide general weather forecasts.

## Tech Stack
- **Backend**: Flask (Main application), SQLAlchemy (ORM), FastAPI (Real-time components).
- **ML & Data Processing**: `pandas`, `numpy`, `scikit-learn`, `xgboost`, `xarray`, `cfgrib`, `eccodes`.
- **Database**: PostgreSQL (Production/Recommended), SQLite (Local/Development).
- **Frontend**: HTML (Jinja2 templates), Vanilla CSS, JavaScript.
- **Operating System**: Primarily Windows (as indicated by `START.bat` and README instructions).

## Key Features
- Real-time storm detection and tracking.
- 24/7 continuous forecasting (automated GFS data fetching every 6 hours).
- Historical storm simulation (e.g., Typhoon Rai 2021).
- Generative AI analysis for meteorological indices.
- Interactive web interface with maps.

# Suggested Commands

## Environment Setup
- **Create Virtual Environment**: `python -m venv venv`
- **Activate Virtual Environment (Windows)**: `venv\Scripts\activate`
- **Install Dependencies**: `pip install -r requirements.txt`

## Running the Application
- **Main Entry Point**: `python app.py`
- **Integrated Control**: Run `START.bat` for a menu-driven interface to start the Web Server, Real-time forecasting, or ML training.
- **Real-time Worker**: `python services/realtime_weather/worker_v4_auto.py` (based on directory structure).

## Testing and Evaluation
- **ML Accuracy Test**: `python tests/test_ml_accuracy.py --all`
- **Test Specific Province**: `python tests/test_ml_accuracy.py --province "Hà Nội"`

## Database
- **Seed Database**: `python seed_db.py`

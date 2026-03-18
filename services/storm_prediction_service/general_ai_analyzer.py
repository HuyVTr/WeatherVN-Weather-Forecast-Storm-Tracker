import os
import json
import numpy as np
import xarray as xr
import glob
import warnings
import sys
import io
import datetime # For logging/timestamps
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*Ignoring index file.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*Your GRIB data does not have a valid index.*", category=UserWarning)

# === FIX LỖI UNICODE TRÊN WINDOWS (tương thích) ===
try:
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# --- PATH DEFINITIONS ---
SERVICE_ROOT = os.path.dirname(os.path.abspath(__file__))
SERVICES_DIR = os.path.dirname(SERVICE_ROOT)
PROJECT_ROOT = os.path.dirname(SERVICES_DIR)

# Central data store paths
DATA_STORE_DIR = os.path.join(PROJECT_ROOT, "project_data")
RAW_GRIB_DIR = os.path.join(DATA_STORE_DIR, "data") # This would be where GFS files are stored

# === IMPORT: AI SERVICES (nếu có) ===
try:
    # Assuming ai_engine is relative to the storm_pipeline
    sys.path.append(os.path.join(SERVICES_DIR, "realtime_weather", "storm_pipeline"))
    from ai_service import ai_engine
    AI_AVAILABLE = True
    print("✅ Đã tải module AI Service")
except Exception as e:
    AI_AVAILABLE = False
    print(f"⚠️ Không tìm thấy module AI Service: {e}")

# ============================================
# GENERAL AI ANALYSIS FUNCTION
# ============================================

def process_ai_analysis(output_dir=RAW_GRIB_DIR, detected_storm=None): # Added detected_storm
    if not AI_AVAILABLE:
        print("⚠️ AI Service không khả dụng, bỏ qua phân tích AI.")
        return None
    try:
        # If a storm is already detected, we can pass it directly to the AI engine
        if detected_storm:
            anomaly, safety = ai_engine.analyze_weather_situation(None, None, detected_storm=detected_storm)
            print(f"🧠 AI Report: Safety Score {safety.get('risk_score', 'N/A')}/100 - {safety.get('status', '')}")
            return {"ai_anomaly": anomaly, "marine_safety": safety, "analyzed_file": "From Detected Storm", "timestamp": datetime.datetime.now().isoformat()}

        # Original logic: If no storm is pre-detected, analyze the GFS file from scratch.
        # Find the latest GRIB file (f000)
        pattern = os.path.join(output_dir, "*_f000.grib2")
        files = glob.glob(pattern)
        if not files:
            pattern = os.path.join(output_dir, "*.grib2") # Fallback
            files = glob.glob(pattern)
        if not files:
            print("⚠️ Không tìm thấy tệp GRIB2 nào để phân tích AI.")
            return None

        latest_file = max(files, key=os.path.getmtime)
        print(f"🧠 Đang phân tích AI trên tệp GRIB mới nhất: {os.path.basename(latest_file)}")
        
        # Open and process the data
        with xr.open_dataset(latest_file, engine="cfgrib", backend_kwargs={'indexpath': '', 'filter_by_keys': {'typeOfLevel': 'heightAboveGround', 'level': 10, 'stepType': 'instant'}}) as ds_10m:
            u10 = ds_10m['u10'].data
            v10 = ds_10m['v10'].data
            lats_1d = ds_10m['latitude'].data
            lons_1d = ds_10m['longitude'].data
        
        with xr.open_dataset(latest_file, engine="cfgrib", backend_kwargs={'indexpath': '', 'filter_by_keys': {'typeOfLevel': 'meanSea', 'stepType': 'instant'}}) as ds_msl:
            prmsl = ds_msl['prmsl'].data

        # Calculate wind speed and crop to the region
        wind_speed_2d = np.sqrt(u10**2 + v10**2)
        pressure_2d = prmsl / 100 # Convert Pa to hPa

        lat_indices = np.where((lats_1d >= 3) & (lats_1d <= 26))[0]
        lon_indices = np.where((lons_1d >= 100) & (lons_1d <= 121))[0]
        if lat_indices.size == 0 or lon_indices.size == 0:
            print("⚠️ Khu vực Biển Đông không hợp lệ trong dữ liệu GRIB.")
            return None

        lat_slice = slice(lat_indices.min(), lat_indices.max() + 1)
        lon_slice = slice(lon_indices.min(), lon_indices.max() + 1)

        pressure_cropped = pressure_2d[lat_slice, lon_slice]
        wind_cropped = wind_speed_2d[lat_slice, lon_slice]

        # Call AI engine with raw data
        anomaly, safety = ai_engine.analyze_weather_situation(pressure_cropped, wind_cropped)
        
        if safety:
            print(f"🧠 AI Report: Safety Score {safety.get('risk_score', 'N/A')}/100 - {safety.get('status', '')}")

        return {"ai_anomaly": anomaly, "marine_safety": safety, "analyzed_file": os.path.basename(latest_file), "timestamp": datetime.datetime.now().isoformat()}
    except Exception as e:
        print(f"❌ Lỗi AI Analysis: {e}")
        return None

if __name__ == '__main__':
    print("Chạy module phân tích AI tổng quát độc lập.")
    result = process_ai_analysis()
    if result:
        print("\n--- Kết quả phân tích AI ---")
        print(json.dumps(result, indent=4))
    else:
        print("\nKhông có kết quả phân tích AI.")

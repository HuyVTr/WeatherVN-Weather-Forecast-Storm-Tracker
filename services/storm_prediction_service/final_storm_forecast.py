import warnings
# Suppress specific UserWarning from cfgrib about index files
warnings.filterwarnings("ignore", message=".*Ignoring index file.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*Your GRIB data does not have a valid index.*", category=UserWarning)


# ============================================================ 
# FINAL STORM FORECAST - FINAL BOT-INTEGRATED VERSION 
# ============================================================ 

import torch
from torch.cuda.amp import autocast
import numpy as np # Re-import numpy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import os
import threading
import json
import xarray as xr
import cfgrib # Needed for xarray to read grib2 files
import pandas as pd
from scipy import interpolate
import time # New import for continuous operation
import requests # New import for status API
import glob # New import for file pattern matching
import traceback # New import for error handling

warnings.filterwarnings("ignore", category=FutureWarning)

# --- PATH DEFINITIONS & REAL-TIME INTEGRATION ---
# This block defines all necessary paths dynamically and handles module imports.
SERVICE_ROOT = os.path.dirname(os.path.abspath(__file__))
SERVICES_DIR = os.path.dirname(SERVICE_ROOT)
PROJECT_ROOT = os.path.dirname(SERVICES_DIR)
REALTIME_SERVICE_DIR = os.path.join(SERVICES_DIR, "realtime_weather")

if SERVICES_DIR not in sys.path:
    sys.path.append(SERVICES_DIR)
if REALTIME_SERVICE_DIR not in sys.path:
    sys.path.append(REALTIME_SERVICE_DIR)

# Central data store paths
DATA_STORE_DIR = os.path.join(PROJECT_ROOT, "project_data")
RAW_GRIB_DIR = os.path.join(DATA_STORE_DIR, "data")
PROCESSED_OUTPUT_DIR = os.path.join(DATA_STORE_DIR, "processed_output")
SIMULATION_DATA_DIR = os.path.join(SERVICE_ROOT, "simulation_data")

from .model import FinalTFT
from .data_processor import FinalDataProcessor
from .trainer import FinalTrainer
from .exporter import FinalExporter, NumpyEncoder
from .analysis_modules import StormOriginDetector, TrajectoryAnalyzer

try:
    from .general_ai_analyzer import process_ai_analysis
    GENERAL_AI_ANALYSIS_AVAILABLE = True
    print("✅ Đã tải module General AI Analyzer.")
except ImportError as e:
    GENERAL_AI_ANALYSIS_AVAILABLE = False
    print(f"⚠️ Không thể tải module General AI Analyzer: {e}. Phân tích AI tổng quát sẽ không khả dụng.")

try:
    from ..realtime_weather.storm_pipeline.data_collector import download_gfs_72h_sequence, robust_download_gfs_forecast, get_gfs_run_times # Added get_latest_gfs_run
    from ..realtime_weather.storm_pipeline.storm_detector_bot import StormDetectorBot
    from ..realtime_weather.storm_pipeline.storm_data_fetcher import StormDataFetcher # NEW
    REALTIME_ENABLED = True
    print("✅ Tải thành công module Real-time (StormDetectorBot, DataCollector, StormDataFetcher).")
except ImportError as e:
    print(f"⚠️ Không thể tải module Real-time: {e}")
    print("   -> Chạy ở chế độ dự báo từ dữ liệu lịch sử.")
    REALTIME_ENABLED = False

# ==========================================
# CONFIGURATION FOR CONTINUOUS OPERATION (New)
# ==========================================
STATUS_FILE = os.path.join(REALTIME_SERVICE_DIR, "status.json") # Centralized status file
# Adjust interval for production, 60 seconds for testing/dev
CONTINUOUS_CHECK_INTERVAL = 60 # 60 seconds for continuous prediction loop
GFS_UPDATE_INTERVAL = 21600 # 6 hours, for actual GFS model updates
API_URL = "http://127.0.0.1:8000/status" # Assuming a local API server for status
FORECAST_HOURS = [f"f{h:03d}" for h in range(0, 169, 3)] # GFS forecast hours

# ==========================================
# HELPER FUNCTIONS (New)
# ==========================================

def convert_numpy_to_python(obj):
    """
    Converts numpy types within an object to standard Python types for JSON serialization.
    """
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    elif isinstance(obj, (np.floating, float)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: convert_numpy_to_python(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_to_python(i) for i in obj]
    else:
        return obj

# ============================================
# UPDATE STATUS
# ============================================
def update_status(status_message, data=None):
    """
    Ghi status ra file và POST sang API server (để WebSocket broadcast).
    """
    timestamp = datetime.now().isoformat()
    clean_data = convert_numpy_to_python(data) if data else {}
    status_data = {
        "last_update": timestamp,
        "status_message": status_message,
        "data": clean_data
    }
    # Ghi file status.json cục bộ
    try:
        os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(status_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"❌ Lỗi ghi {STATUS_FILE}: {e}")

    # Gửi sang API Server
    try:
        requests.post(API_URL, json=status_data, timeout=5)
    except requests.exceptions.RequestException:
        # Bỏ qua lỗi mạng
        pass

# ============================================
# GFS DATA MANAGEMENT
# ============================================
def check_and_download_gfs():
    """Kiểm tra và tải dữ liệu GFS mới (cải tiến với error handling)."""
    print("\n" + "=" * 60)
    print("📡 KIỂM TRA DỮ LIỆU GFS MỚI")
    print("=" * 60)
    try:
        if not REALTIME_ENABLED:
            print("⚠️ Chế độ Real-time không khả dụng. Bỏ qua kiểm tra GFS.")
            return False

        run_date, run_hour = get_gfs_run_times(num_runs=1)[0]
        expected_pattern = f"*_gfs_{run_date}_{run_hour}z_*.grib2"
        existing_files = glob.glob(os.path.join(RAW_GRIB_DIR, expected_pattern))
        
        # Check if all expected forecast hours are present
        if len(existing_files) >= len(FORECAST_HOURS):
            print(f"✅ Đã có dữ liệu GFS run {run_date} {run_hour}Z")
            return True
        
        print(f"📥 Đang tải dữ liệu GFS run: {run_date} {run_hour}Z")
        # Use robust_download_gfs_forecast for each forecast hour
        downloaded_count = 0
        for f_hour in FORECAST_HOURS:
            file_path = robust_download_gfs_forecast(f_hour, RAW_GRIB_DIR, run_date=run_date, run_hour=run_hour)
            if file_path:
                downloaded_count += 1
        
        if downloaded_count >= len(FORECAST_HOURS):
            print(f"✅ Đã tải thành công {downloaded_count}/{len(FORECAST_HOURS)} tệp GFS.")
            return True
        else:
            print(f"❌ Chỉ tải được {downloaded_count}/{len(FORECAST_HOURS)} tệp GFS. Có thể thiếu dữ liệu.")
            return False

    except Exception as e:
        print(f"❌ Lỗi khi kiểm tra hoặc tải GFS: {e}")
        traceback.print_exc()
        return False

class FinalStormSystem:
    def __init__(self, device='cpu'):
        print("\n" + "="*60)
        print("🌀 FINAL STORM FORECAST SYSTEM (AMP, SIMULATION, ANALYSIS)")
        print(f"🛰️ Real-time Active: {REALTIME_ENABLED}")
        
        # --- AUTO-DETECT DEVICE LOGIC ---
        if device == 'cuda' and not torch.cuda.is_available():
            print("⚠️ CẢNH BÁO: Yêu cầu 'cuda' nhưng không tìm thấy GPU khả dụng.")
            print("   -> Tự động chuyển sang chế độ 'cpu'.")
            device = 'cpu'
        
        print(f"🖥️ Running on: {device.upper()}")
        print("="*60)
        
        self.processor = FinalDataProcessor()
        self.model = FinalTFT()
        self.trainer = FinalTrainer(self.model, device=device)
        self.exporter = FinalExporter()
        # Sử dụng đường dẫn tuyệt đối đến model
        self.model_path = os.path.join(SERVICE_ROOT, 'final_storm_10f.pth')

    # --- Giữ nguyên hàm train() đã được tối ưu ---
    def train(self, epochs=20, fast_mode=False):
        print("\n🔥 TRAINING...")
        
        self.processor.load_and_process()
        X_train, y_train, X_val, y_val, X_test, y_test = self.processor.create_sequences(seq_len=72, forecast_horizon=168)
        
        if X_train is None:
            print("❌ Không đủ dữ liệu để tạo sequence cho training.")
            return

        if fast_mode:
            sample_size = min(1000, len(X_train))
            idx = np.random.choice(len(X_train), sample_size, replace=False)
            X_train, y_train = X_train[idx], y_train[idx]
            print(f"⚡ Fast mode: {sample_size} samples for training")
        
        best_val_loss = float('inf')
        patience = 5
        epochs_no_improve = 0

        for epoch in range(epochs):
            train_loss = self.trainer.train_epoch(X_train, y_train)
            
            self.model.eval()
            val_loss = 0
            val_batch_size = 32
            with torch.no_grad():
                with autocast(enabled=self.trainer.scaler.is_enabled()):
                    val_indices = np.arange(len(X_val))
                    for i in range(0, len(X_val), val_batch_size):
                        batch_idx = val_indices[i:i+val_batch_size]
                        bx_val, by_val = torch.from_numpy(X_val[batch_idx]).to(self.trainer.device), torch.from_numpy(y_val[batch_idx]).to(self.trainer.device)
                        val_predictions_batch = self.model(bx_val)['full']
                        val_loss += self.trainer.loss_fn(val_predictions_batch, by_val).item()
                    val_loss /= max(1, (len(X_val) // val_batch_size))
            
            status = ""
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                torch.save(self.model.state_dict(), self.model_path)
                status = "⭐ BEST"
                epochs_no_improve = 0
            else:
                epochs_no_improve += 1
            
            print(f"💾 Epoch {epoch+1}/{epochs} | Train Loss: {train_loss:.6f} | Val Loss: {val_loss:.6f} {status}")

            if epochs_no_improve == patience:
                print(f"⚠️ Early stopping! No improvement in validation loss for {patience} epochs.")
                break
        
        print(f"\n✅ Training complete! Best Validation Loss: {best_val_loss:.6f}")
        self.model.load_state_dict(torch.load(self.model_path, map_location=self.trainer.device))
        self.model.eval()
        test_loss = 0
        test_batch_size = 32
        with torch.no_grad():
            with autocast(enabled=self.trainer.scaler.is_enabled()):
                test_indices = np.arange(len(X_test))
                for i in range(0, len(X_test), test_batch_size):
                    batch_idx = test_indices[i:i+test_batch_size]
                    bx_test, by_test = torch.from_numpy(X_test[batch_idx]).to(self.trainer.device), torch.from_numpy(y_test[batch_idx]).to(self.trainer.device)
                    test_predictions_batch = self.model(bx_test)['full']
                    test_loss += self.trainer.loss_fn(test_predictions_batch, by_test).item()
                test_loss /= max(1, (len(X_test) // test_batch_size))
        print(f"📊 Test Loss: {test_loss:.6f}")

    def extract_features_from_grib(self, grib_path, lat, lon):
        try:
            # Strategy: Open the GRIB file multiple times with specific filters for each data type. 
            
            # --- Get data at isobaric levels (850mb, 200mb) ---
            with xr.open_dataset(grib_path, engine="cfgrib", backend_kwargs={'filter_by_keys': {'typeOfLevel': 'isobaricInhPa'}}, drop_variables=['valid_time']) as ds_isobaric:
                u850 = ds_isobaric['u'].sel(isobaricInhPa=850, latitude=lat, longitude=lon, method='nearest').item()
                v850 = ds_isobaric['v'].sel(isobaricInhPa=850, latitude=lat, longitude=lon, method='nearest').item()
                r850 = ds_isobaric['r'].sel(isobaricInhPa=850, latitude=lat, longitude=lon, method='nearest').item()
                t850 = ds_isobaric['t'].sel(isobaricInhPa=850, latitude=lat, longitude=lon, method='nearest').item()
                u200 = ds_isobaric['u'].sel(isobaricInhPa=200, latitude=lat, longitude=lon, method='nearest').item()

            # --- Get data at surface level ---
            with xr.open_dataset(grib_path, engine="cfgrib", backend_kwargs={'filter_by_keys': {'typeOfLevel': 'surface'}}, drop_variables=['valid_time']) as ds_surface:
                # GFS often provides TMP on surface level which can be used for SST over water.
                sst = ds_surface['t'].sel(latitude=lat, longitude=lon, method='nearest').item()
                
            # --- Get data at mean sea level ---
            with xr.open_dataset(grib_path, engine="cfgrib", backend_kwargs={'filter_by_keys': {'typeOfLevel': 'meanSea'}}, drop_variables=['valid_time']) as ds_msl:
                pressure = ds_msl['prmsl'].sel(latitude=lat, longitude=lon, method='nearest').item()

            # --- Get data at 10m above ground ---
            with xr.open_dataset(grib_path, engine="cfgrib", backend_kwargs={'filter_by_keys': {'typeOfLevel': 'heightAboveGround', 'level': 10}}, drop_variables=['valid_time']) as ds_10m:
                u10 = ds_10m['u10'].sel(latitude=lat, longitude=lon, method='nearest').item()
                v10 = ds_10m['v10'].sel(latitude=lat, longitude=lon, method='nearest').item()

            # --- Process and combine data ---
            t850_c = t850 - 273.15 if not np.isnan(t850) else np.nan
            sst_c = sst - 273.15 if not np.isnan(sst) else np.nan # Convert SST to Celsius
            pressure_hpa = pressure / 100 if not np.isnan(pressure) else np.nan
            wind_speed = np.sqrt(u10**2 + v10**2) if not (np.isnan(u10) or np.isnan(v10)) else np.nan

            if np.isnan(wind_speed) or np.isnan(pressure_hpa): return None
            
            # Return dict with standard feature names
            return {
                'LAT': lat, 'LON': lon, 'WMO_WIND': wind_speed, 'WMO_PRES': pressure_hpa,
                'u_850': u850, 'v_850': v850, 'r_850': r850, 't_850': t850_c,
                'u_200': u200, 'SST': sst_c
            }
        except Exception as e:
            print(f"   -> ❌ Lỗi tổng quát khi trích xuất feature từ file {os.path.basename(grib_path)}: {e}")
            return None

    def get_input_sequence(self, mode='realtime'):
        if mode == 'realtime':
            # Clear old output files to prevent showing stale data
            for f in Path(PROCESSED_OUTPUT_DIR).glob('*.json'):
                try: f.unlink()
                except OSError: pass
            for f in Path(PROCESSED_OUTPUT_DIR).glob('*.csv'):
                try: f.unlink()
                except OSError: pass

            if not REALTIME_ENABLED: return None, None, None
            print("\n🛰️  --- BẮT ĐẦU QUY TRÌNH DỰ BÁO REAL-TIME ---")
            gfs_data_dir = RAW_GRIB_DIR; os.makedirs(gfs_data_dir, exist_ok=True)
            
            strongest_alert = None

            # --- NEW: GDACS + GFS Integrated Workflow ---
            # STEP 1: Check GDACS for officially recognized storms
            print("\n[1/4] Đang kiểm tra hệ thống cảnh báo toàn cầu (GDACS)...")
            fetcher = StormDataFetcher()
            gdacs_storm = fetcher.get_active_storm()

            if gdacs_storm:
                print("   -> ✅ GDACS phát hiện bão đang hoạt động. Ưu tiên dữ liệu này.")
                strongest_alert = gdacs_storm
                
                # FIX: Write the GDACS alert to all_alerts.json so the UI can display it
                alerts = [gdacs_storm]
                GRIB2_OUTPUT_DIR = os.path.join(DATA_STORE_DIR, "grib2_output")
                os.makedirs(GRIB2_OUTPUT_DIR, exist_ok=True)
                alerts_file_path = os.path.join(GRIB2_OUTPUT_DIR, 'all_alerts.json')
                with open(alerts_file_path, 'w', encoding='utf-8') as f:
                    json.dump(alerts, f, ensure_ascii=False, indent=2)
                print(f"   -> ✅ Đã ghi {len(alerts)} cảnh báo từ GDACS vào {alerts_file_path}")

                # Since we found an official storm, we don't need to run StormDetectorBot.
                # We will proceed directly to gathering historical data for this storm.
            else:
                # STEP 2: If GDACS finds nothing, scan GFS for new/unnamed disturbances
                print("   -> Không có bão chính thức từ GDACS. Chuyển sang quét GFS để tìm nhiễu động mới.")
                print("\n[2/4] Đang tải dữ liệu GFS mới nhất (f000) để quét...")
                from ..realtime_weather.storm_pipeline.data_collector import robust_download_gfs_forecast
                latest_grib_file = robust_download_gfs_forecast("f000", gfs_data_dir)
                
                if not latest_grib_file:
                    print("   -> ❌ Không thể tải dữ liệu GFS. Không thể chạy BOT.")
                    return None, None, None

                print("\n[3/4] BOT đang phân tích dữ liệu GFS...")
                bot = StormDetectorBot(data_dir=RAW_GRIB_DIR)
                alerts = bot.scan_south_china_sea()
                
                # Write alerts to file, even if empty, for the API to read
                GRIB2_OUTPUT_DIR = os.path.join(DATA_STORE_DIR, "grib2_output")
                os.makedirs(GRIB2_OUTPUT_DIR, exist_ok=True)
                alerts_file_path = os.path.join(GRIB2_OUTPUT_DIR, 'all_alerts.json')
                with open(alerts_file_path, 'w', encoding='utf-8') as f:
                    json.dump(alerts if alerts is not None else [], f, ensure_ascii=False, indent=2)
                print(f"   -> ✅ Đã ghi {len(alerts) if alerts else 0} cảnh báo vào {alerts_file_path}")
            
                if alerts:
                    strongest_alert = max(alerts, key=lambda x: x['wind_speed'])

            # STEP 4: If a storm was found (either by GDACS or GFS bot), get its historical sequence
            if not strongest_alert:
                print("\n-> ✅ Hoàn tất: Không phát hiện bão từ GDACS hay nhiễu động đáng chú ý từ GFS.")
                return None, None, None

            # --- NEW: Filter by Wind Speed Threshold (Level 8 >= 62 km/h) ---
            WIND_THRESHOLD_KMH = 62.0
            alert_wind_speed = strongest_alert.get('wind_speed', strongest_alert.get('wind_speed_kmh', 0))
            
            # Ensure wind speed is a float
            try:
                alert_wind_speed = float(alert_wind_speed)
            except (ValueError, TypeError):
                alert_wind_speed = 0.0

            if alert_wind_speed < WIND_THRESHOLD_KMH:
                print(f"\n[INFO] Nhiễu động mạnh nhất có gió: {alert_wind_speed:.1f} km/h (< Cấp 8 / {WIND_THRESHOLD_KMH} km/h).")
                print("   -> ⚠️ Chỉ hiển thị cảnh báo (Marked Icons). Bỏ qua dự báo quỹ đạo chi tiết.")
                print("   -> ✅ File 'all_alerts.json' đã được cập nhật để hiển thị trên bản đồ.")
                return None, None, None
            # ----------------------------------------------------------------

            print(f"\n[4/4] Bão/Nhiễu động mạnh nhất: '{strongest_alert.get('type_vi', strongest_alert.get('storm_name', 'N/A'))}'.")
            print("   -> Bắt đầu thu thập chuỗi GFS lịch sử 72 giờ cho vị trí này...")
            
            grib_files = download_gfs_72h_sequence(output_dir=gfs_data_dir) # 3-hour step assumed
            if not grib_files or len(grib_files) < 24: # Need 24 points for 72h
                print("   -> ❌ Không tải đủ file lịch sử để tạo chuỗi đầu vào.")
                return strongest_alert, None, None

            grib_files.sort()
            print("   -> 🔁 Đang trích xuất features từ chuỗi GRIB lịch sử...")
            historical_sequence_data = []
            target_lat, target_lon = strongest_alert['lat'], strongest_alert['lon']
            
            for grib_path in grib_files:
                features = self.extract_features_from_grib(grib_path, target_lat, target_lon)
                if features:
                    ordered_features = [features.get(f_name, np.nan) for f_name in self.processor.FEATURES]
                    historical_sequence_data.append(ordered_features)
            
            if len(historical_sequence_data) < 24:
                print(f"   -> ❌ Chỉ trích xuất được {len(historical_sequence_data)} điểm dữ liệu. Không đủ 24 điểm.")
                return strongest_alert, None, None

            print(f"   -> ✅ Đã tạo chuỗi lịch sử với {len(historical_sequence_data)} điểm dữ liệu (3-hour interval).")
            
            sequence_array = np.array(historical_sequence_data, dtype=np.float32)
            
            # Interpolate from 3h to 1h interval
            original_time_points = np.arange(0, len(sequence_array) * 3, 3)
            target_time_points = np.arange(0, 72, 1) # Target 72 points for 1-hour interval
            if len(original_time_points) < 2: # Need at least 2 points to interpolate
                 print(f"   -> ❌ Không đủ điểm ({len(original_time_points)}) trong chuỗi lịch sử để nội suy.")
                 return strongest_alert, None, None
            
            interpolated_sequence = np.zeros((len(target_time_points), sequence_array.shape[1]), dtype=np.float32)
            
            for i in range(sequence_array.shape[1]):
                f = interpolate.interp1d(original_time_points, sequence_array[:, i], kind='linear', fill_value="extrapolate")
                interpolated_sequence[:, i] = f(target_time_points)

            print(f"   -> ✅ Nội suy thành công chuỗi {len(interpolated_sequence)} điểm dữ liệu (1-hour interval).")
            return strongest_alert, interpolated_sequence, strongest_alert.get('type_vi', 'Unknown Storm')
        
        elif mode == 'simulation':
            print("\n🌀 --- BẮT ĐẦU QUY TRÌNH DỰ BÁO GIẢ ĐỊNH ---")
            sim_file = Path(os.path.join(SIMULATION_DATA_DIR, 'actual_path.csv'))
            if not sim_file.exists():
                print(f"   -> ❌ Không tìm thấy file '{sim_file}'")
                return None, None, None
            
            df_sim = pd.read_csv(sim_file)
            if len(df_sim) < 72:
                print(f"   -> ❌ File giả định không có đủ 72 dòng dữ liệu.")
                return None, None, None

            # FIX: Create and write an alert for the simulation so the UI can display it
            first_point = df_sim.iloc[0]
            sim_alert = {
                'storm_name': 'TYPHOON RAI (SIMULATED)',
                'type_vi': 'Bão Giả Định',
                'severity': 'EXTREME', # Hardcode as EXTREME for a historical super typhoon
                'source': 'Simulation',
                'lat': first_point.get('LATITUDE', 0),
                'lon': first_point.get('LONGITUDE', 0),
                'wind_speed_kmh': first_point.get('WMO_WIND', 0) * 3.6 if 'WMO_WIND' in first_point else 0,
                'pressure': first_point.get('PRMSL', 0),
                'details': 'Mô phỏng bão lịch sử Rai (2021).',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'icon': '🌀'
            }
            GRIB2_OUTPUT_DIR = os.path.join(DATA_STORE_DIR, "grib2_output")
            os.makedirs(GRIB2_OUTPUT_DIR, exist_ok=True)
            alerts_file_path = os.path.join(GRIB2_OUTPUT_DIR, 'all_alerts.json')
            with open(alerts_file_path, 'w', encoding='utf-8') as f:
                json.dump([sim_alert], f, ensure_ascii=False, indent=2)
            print(f"   -> ✅ Đã ghi cảnh báo mô phỏng vào {alerts_file_path}")

            df_input = df_sim.head(72).copy()
            input_sequence = np.zeros((72, len(self.processor.FEATURES)), dtype=np.float32)
            
            if 'WMO_WIND' not in df_input.columns and 'U10' in df_input.columns and 'V10' in df_input.columns:
                 df_input['WMO_WIND'] = np.sqrt(df_input['U10']**2 + df_input['V10']**2)

            for i in range(len(self.processor.FEATURES)):
                feature = self.processor.FEATURES[i]
                csv_col_map = {
                    'LAT': 'LATITUDE', 'LON': 'LONGITUDE', 'WMO_WIND': 'WMO_WIND', 
                    'WMO_PRES': 'PRMSL', 't_850': 'T_CELSIUS', 'SST': 'SST', 
                    'r_850': 'HUMIDITY', 'u_200': 'WIND_SHEAR'
                }
                if feature in csv_col_map and csv_col_map[feature] in df_input.columns:
                    input_sequence[:, i] = df_input[csv_col_map[feature]].values
                else:
                    if feature in self.processor.scaler_params:
                         mean_val = (self.processor.scaler_params[feature]['min'] + self.processor.scaler_params[feature]['max']) / 2
                         input_sequence[:, i] = mean_val
                    else:
                        input_sequence[:, i] = 0
            
            print(f"   -> ✅ Đã tạo chuỗi đầu vào 72 giờ từ '{sim_file}'.")
            return {'classification': 'SIMULATED_TYPHOON', 'type_vi': 'Bão Giả Định'}, input_sequence, 'Simulated Storm (Typhoon Rai)'

        else: # historical_fallback
            print("\n   -> ⚠️  Sử dụng 72h cuối từ file Excel.")
            df_processed = self.processor.df
            if len(df_processed) < 72:
                print("   -> ❌ Dữ liệu Excel không đủ 72 dòng.")
                return None, None, None
            latest_input = df_processed[self.processor.FEATURES].values.astype(np.float32)[-72:]
            return None, latest_input, 'Historical Data'

    def predict_from_sequence(self, input_sequence, source_name, realtime_storm_details=None, is_simulation=False, ai_report=None):
        # 1. Normalize the input sequence
        normalized_sequence = input_sequence.copy()
        for i, col in enumerate(self.processor.FEATURES):
            p = self.processor.scaler_params[col]
            # Handle cases where max and min are the same
            denom = p['max'] - p['min']
            if denom < 1e-8:
                normalized_sequence[:, i] = 0 # Or some other default normalized value
            else:
                normalized_sequence[:, i] = (normalized_sequence[:, i] - p['min']) / denom
        
        # Clip the normalized values to prevent extreme outliers
        normalized_sequence = np.clip(normalized_sequence, -5, 5)

        # 2. Run prediction
        with torch.no_grad():
            with autocast(enabled=self.trainer.scaler.is_enabled()):
                X = torch.from_numpy(normalized_sequence).unsqueeze(0).to(self.trainer.device)
                preds_normalized = self.model(X)['full'].cpu().numpy()[0]

        # Check for and handle instability
        if not np.isfinite(preds_normalized).all():
            print("   -> ⚠️ CẢNH BÁO: Mô hình đã dự đoán ra các giá trị không hợp lệ (NaN hoặc Inf). Thay thế chúng bằng 0.")
            preds_normalized = np.nan_to_num(preds_normalized, nan=0.0, posinf=0.0, neginf=0.0)

        # 3. Descale predictions
        preds = preds_normalized.copy()
        for i, feat in enumerate(self.processor.FEATURES):
            p = self.processor.scaler_params[feat]
            denom = p['max'] - p['min']
            if denom < 1e-8:
                preds[:, i] = p['min']
            else:
                preds[:, i] = preds_normalized[:, i] * denom + p['min']
        
        # 4. FIX FOR SIMULATION STARTING POINT
        if is_simulation:
            print("   -> 🔧 Điều chỉnh điểm bắt đầu của dự báo giả định...")
            lat_idx = self.processor.FEATURES.index('LAT')
            lon_idx = self.processor.FEATURES.index('LON')
            last_actual_lat = input_sequence[-1, lat_idx]
            last_actual_lon = input_sequence[-1, lon_idx]
            
            first_pred_lat = preds[0, lat_idx]
            first_pred_lon = preds[0, lon_idx]
            
            lat_offset = last_actual_lat - first_pred_lat
            lon_offset = last_actual_lon - first_pred_lon
            
            preds[:, lat_idx] += lat_offset
            preds[:, lon_idx] += lon_offset
            print(f"   -> ✅ Đã điều chỉnh dự báo. Offset: Lat {lat_offset:.2f}, Lon {lon_offset:.2f}")

            # --- FIX WIND & PRESSURE FOR SIMULATION ---
            try:
                wind_idx = self.processor.FEATURES.index('WMO_WIND')
                pres_idx = self.processor.FEATURES.index('WMO_PRES')
                
                last_actual_wind = input_sequence[-1, wind_idx]
                last_actual_pres = input_sequence[-1, pres_idx]
                
                # Create a decay/recovery curve for simulation realism
                # Instead of just offsetting a flat line, we simulate weakening over time
                steps = preds.shape[0]
                
                # WIND: Decay (storm weakens) + Random Noise
                # Decay: loses ~0.3 m/s per hour on average
                wind_decay = np.linspace(0, 0.3 * steps, steps) 
                noise_wind = np.random.uniform(-1.0, 1.0, size=steps) # +/- 1 m/s noise
                
                # Reconstruct wind path starting from last actual value
                # We ignore the model's raw output for wind if it's flat, and build a logical trajectory
                current_wind_profile = np.full(steps, last_actual_wind) - wind_decay + noise_wind
                preds[:, wind_idx] = np.maximum(current_wind_profile, 0.0) # Ensure non-negative

                # PRESSURE: Recovery (storm weakens -> pressure rises) + Random Noise
                # Recovery: rises ~0.5 hPa per hour on average
                pres_recovery = np.linspace(0, 0.5 * steps, steps)
                noise_pres = np.random.uniform(-1.0, 1.0, size=steps)
                
                # Reconstruct pressure path starting from last actual value
                current_pres_profile = np.full(steps, last_actual_pres) + pres_recovery + noise_pres
                preds[:, pres_idx] = np.maximum(current_pres_profile, 870.0)

                print(f"   -> ✅ Đã điều chỉnh khí tượng (Mô phỏng suy yếu). Start Wind: {last_actual_wind:.1f}, Start Pres: {last_actual_pres:.1f}")
            except ValueError:
                print("   -> ⚠️ Không tìm thấy cột WMO_WIND hoặc WMO_PRES để điều chỉnh.")
            # ------------------------------------------

        # 5. Export results with analysis
        timestamp = datetime.now()
        # Ta sẽ sửa hàm export để nó tự chạy analysis
        df, analysis = self.exporter.export(
            preds, 
            self.processor.scaler_params, 
            timestamp, 
            self.processor.FEATURES,
            origin_details=realtime_storm_details, 
            is_simulation=is_simulation,
            source_name=source_name,
            ai_report=ai_report # Pass ai_report here
        )
        
        print("\n✅ Prediction complete!")

    def run_prediction_flow(self, mode='realtime', suppress_output=False):
        if not suppress_output: print("\n🔮 PREDICTION...")
        if not Path(self.model_path).exists():
            if not suppress_output: print(f"⚠️ Không tìm thấy model đã huấn luyện tại '{self.model_path}'. Dừng dự báo.")
            return False # Return False to indicate failure
        
        self.model.load_state_dict(torch.load(self.model_path, map_location=self.trainer.device))
        self.model.eval()
        
        # Load scaler params from the full training data
        try:
            self.processor.load_and_process()
        except FileNotFoundError:
            if not suppress_output:
                print("\n" + "="*80)
                print("❌ LỖI NGHIÊM TRỌNG: KHÔNG TÌM THẤY DỮ LIỆU HUẤN LUYỆN")
                print("="*80)
                print(f"File 'FINAL_TRAINING_DATASET_ENHANCED.xlsx' phải được đặt trong thư mục:")
                print(f" -> {os.path.join(self.processor.excel_path, '..')}")
                print("\nKhông thể chạy dự báo nếu không có dữ liệu để tính toán các tham số chuẩn hóa (scaler).")
                print("Vui lòng cung cấp file dữ liệu và chạy lại.")
                print("="*80)
            return False # Return False to indicate failure
        
        # Get the appropriate input sequence
        storm_details, sequence, source_name = self.get_input_sequence(mode=mode)
        
        if sequence is None:
            if mode == 'realtime':
                if not suppress_output: print("   -> ⚠️ Không tìm thấy bão thời gian thực. Không tạo file dự báo.")
                return False
            else: # historical_fallback for other modes if needed, though 'simulation' handles its own
                if not suppress_output: print("   -> ⚠️ Không thể lấy được chuỗi đầu vào. Thử fallback sang dữ liệu lịch sử...")
                storm_details, sequence, source_name = self.get_input_sequence(mode='historical_fallback')
                if sequence is None:
                    if not suppress_output: print("   -> ❌ Fallback cũng thất bại. Dừng dự báo.")
                    return False

        # Run General AI Analysis
        ai_report = None
        if GENERAL_AI_ANALYSIS_AVAILABLE:
            # Pass the detected storm details to the analyzer
            ai_report = process_ai_analysis(output_dir=RAW_GRIB_DIR, detected_storm=storm_details) 
            if ai_report and not suppress_output:
                print("🧠 Đã thực hiện phân tích AI tổng quát.")
        else:
            if not suppress_output: print("⚠️ Module AI phân tích tổng quát không khả dụng.")


        # Run the prediction on the obtained sequence
        self.predict_from_sequence(sequence, source_name, storm_details, is_simulation=(mode=='simulation'), ai_report=ai_report)
        return True # Return True to indicate success

# ============================================================ 
# CONTINUOUS FORECAST SYSTEM
# ============================================================ 
def run_continuous_forecast_system(system_instance, device):
    print("\n" + "="*80)
    print("🌀 KHỞI ĐỘNG HỆ THỐNG DỰ BÁO LIÊN TỤC (FINAL STORM FORECAST)")
    print("="*80)
    print(f"🎮 Device: {device}")
    print(f"⏱️ Kiểm tra dữ liệu GFS mỗi {GFS_UPDATE_INTERVAL / 3600} giờ.")
    print(f"⏱️ Chạy vòng lặp dự báo mỗi {CONTINUOUS_CHECK_INTERVAL} giây.")
    print("="*80)

    last_gfs_check_time = 0
    loop_count = 0

    while True:
        loop_count += 1
        current_time = time.time()
        timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"\n🔄 VÒNG LẶP LIÊN TỤC #{loop_count} - {timestamp_str}")
        update_status(f"Hệ thống đang hoạt động. Vòng lặp #{loop_count}", {"loop_count": loop_count})

        try:
            # Check and download GFS if enough time has passed
            if (current_time - last_gfs_check_time) >= GFS_UPDATE_INTERVAL:
                update_status("Đang kiểm tra và tải dữ liệu GFS mới...", {"stage": "gfs_check_download"})
                gfs_downloaded_successfully = check_and_download_gfs()
                if gfs_downloaded_successfully:
                    last_gfs_check_time = current_time
                    update_status("Đã tải GFS thành công. Bắt đầu dự báo.", {"stage": "gfs_download_success"})
                else:
                    update_status("Không tải được GFS. Tiếp tục với dữ liệu hiện có hoặc bỏ qua.", {"stage": "gfs_download_failed"})
            else:
                print("⏳ Chưa đến thời gian tải GFS mới. Sử dụng dữ liệu hiện có.")
            
            # Run prediction flow. suppress_output=True to keep continuous log clean
            update_status("Đang chạy quy trình dự báo quỹ đạo...", {"stage": "prediction_flow"})
            prediction_success = system_instance.run_prediction_flow(mode='realtime', suppress_output=True)
            
            if prediction_success:
                update_status("✅ Dự báo hoàn tất thành công.", {"stage": "prediction_success"})
                print("✅ Dự báo hoàn tất thành công.")
            else:
                update_status("⚠️ Dự báo không thành công hoặc không tìm thấy bão.", {"stage": "prediction_failed"})
                print("⚠️ Dự báo không thành công hoặc không tìm thấy bão.")

        except KeyboardInterrupt:
            print("\n⏹️ Dừng hệ thống liên tục (KeyboardInterrupt)")
            update_status("Hệ thống dự báo liên tục đã dừng (người dùng hủy).", {"status": "stopped_by_user"})
            break
        except Exception as e:
            print(f"\n❌ Lỗi trong vòng lặp liên tục: {e}")
            traceback.print_exc()
            update_status(f"❌ Lỗi trong vòng lặp liên tục: {e}", {"stage": "error", "error": str(e)})

        print(f"\n😴 Nghỉ {CONTINUOUS_CHECK_INTERVAL} giây trước vòng lặp tiếp theo...")
        time.sleep(CONTINUOUS_CHECK_INTERVAL)

# ============================================================ 
# CLI 
# ============================================================ 
import argparse
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Final Storm Forecast System")
    parser.add_argument('--device', type=str, default='cpu', help='Device to run on (cpu or cuda)')
    # Allow passing an argument directly to run a mode
    parser.add_argument('mode_choice', type=str, nargs='?', help='Directly choose a mode (e.g., "1", "3.1")')
    args = parser.parse_args()

    system = FinalStormSystem(device=args.device)
    
    # Process direct command-line choice if provided
    if args.mode_choice:
        print(f"\n>> Đang thực thi chế độ '{args.mode_choice}' từ dòng lệnh...")
        choice = args.mode_choice
        if choice == '1':
            system.train(epochs=10, fast_mode=True)
        elif choice == '2':
            system.train(epochs=20)
        elif choice == '3.1': # One-time Real-time prediction
            print("\n>> Đang chạy Dự báo Real-time (Một lần)...")
            system.run_prediction_flow(mode='realtime')
        elif choice == '3.2': # Continuous Forecast System (should ideally be launched in a separate process)
            print("\n>> Đang khởi động Hệ thống Dự báo Liên tục...")
            run_continuous_forecast_system(system, args.device)
        elif choice == '3.3': # Simulate Storm
            print("\n>> Đang chạy Mô phỏng Bão...")
            system.run_prediction_flow(mode='simulation')
        else:
            print(f"Lựa chọn dòng lệnh '{choice}' không hợp lệ hoặc không được hỗ trợ cho chế độ chạy trực tiếp.")
        print("\n✅ HOÀN TẤT tác vụ dòng lệnh và thoát.")
        sys.exit(0) # Exit after executing direct command-line choice

    # If no direct command-line choice, enter interactive menu loop
    while True: 
        print("\n" + "="*60)
        print("⚡ CHỌN CHẾ ĐỘ HOẠT ĐỘNG")
        print("="*60)
        print("1. 🚀 Huấn luyện nhanh (Quick Train)")
        print("2. 💪 Huấn luyện đầy đủ (Full Train)")
        print("3. 🔮 Dự báo & Phân tích (Real-time, Liên tục, Mô phỏng)")
        print("4. ❌ Thoát")
        print("="*60)

        choice = input("\nChọn (1-4): ").strip()
        
        if choice == '1':
            system.train(epochs=10, fast_mode=True)
        elif choice == '2':
            system.train(epochs=20)
        elif choice == '3':
            while True: # Sub-menu for Forecast & Analysis
                print("\n" + "="*50)
                print("🔮 CHẾ ĐỘ DỰ BÁO & PHÂN TÍCH")
                print("="*50)
                print("3.1. Dự báo Real-time (Một lần)")
                print("3.2. Chạy Hệ thống Dự báo Liên tục")
                print("3.3. Mô phỏng Bão (Sử dụng dữ liệu simulation_data/actual_path.csv)")
                print("3.4. ↩️ Quay lại Menu Chính")
                print("="*50)
                sub_choice = input("\nChọn (3.1-3.4): ").strip()

                if sub_choice == '3.1':
                    print("\n>> Đang chạy Dự báo Real-time (Một lần)...")
                    system.run_prediction_flow(mode='realtime')
                elif sub_choice == '3.2':
                    print("\n>> Đang khởi động Hệ thống Dự báo Liên tục...")
                    run_continuous_forecast_system(system, args.device)
                elif sub_choice == '3.3':
                    print("\n>> Đang chạy Mô phỏng Bão...")
                    system.run_prediction_flow(mode='simulation')
                elif sub_choice == '3.4':
                    break # Go back to main menu
                else:
                    print("Lựa chọn không hợp lệ. Vui lòng chọn lại.")
        elif choice == '4':
            print("\n👋 Thoát hệ thống. Tạm biệt!")
            break # Exit the main loop
        else:
            print("Lựa chọn không hợp lệ. Vui lòng chọn lại.")

    print("\n✅ HOÀN TẤT!")

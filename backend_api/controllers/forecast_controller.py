# backend_api/controllers/forecast_controller.py
# Xử lý các route cho trang Dự báo và API thời tiết.

from flask import Blueprint, render_template, request, jsonify
import sys
import os
import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
import glob
import xarray as xr
import cfgrib
from services.storm_prediction_service.analysis_modules import TrajectoryAnalyzer
import warnings

# Suppress specific UserWarning from cfgrib about index files globally in this module
warnings.filterwarnings("ignore", message=".*Ignoring index file.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*Your GRIB data does not have a valid index.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*variable named 't2m'.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*In a future version, xarray will not decode timedelta values.*", category=FutureWarning)


# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend_api.models.weather_model import Provinces
from data_pipeline.data_storage import connect_to_db
from services.forecast_ml.predictor import predict_storm

forecast_bp = Blueprint('forecast_bp', __name__)

@forecast_bp.route('/forecast', endpoint='forecast_page')
def route_forecast():
    """Phục vụ trang dự báo."""
    return render_template('forecast.html', nav_active='forecast')

# --- CẤU HÌNH DATABASE CHO CONTROLLER ---
# Lưu ý: Thay 'password' bằng mật khẩu thực của bạn
# DB_URI = "postgresql://postgres:password@localhost:5432/weather_db"
# db_engine = create_engine(DB_URI)

@forecast_bp.route('/api/provinces')
def api_get_provinces():
    """API lấy danh sách 63 tỉnh (mocked data)."""
    # Dữ liệu tỉnh được hardcode vì không có DB
    provinces_data = [
        {'province_id': 1, 'name': 'Hà Nội', 'latitude': 21.0285, 'longitude': 105.8542},
        {'province_id': 2, 'name': 'TP. Hồ Chí Minh', 'latitude': 10.8231, 'longitude': 106.6297},
        {'province_id': 3, 'name': 'Đà Nẵng', 'latitude': 16.0544, 'longitude': 108.2022},
        {'province_id': 4, 'name': 'Hải Phòng', 'latitude': 20.8449, 'longitude': 106.6881},
        {'province_id': 5, 'name': 'Cần Thơ', 'latitude': 10.0452, 'longitude': 105.7468},
        {'province_id': 6, 'name': 'Huế', 'latitude': 16.4637, 'longitude': 107.5909},
        {'province_id': 7, 'name': 'Nha Trang', 'latitude': 12.2388, 'longitude': 109.1967},
        {'province_id': 8, 'name': 'Vũng Tàu', 'latitude': 10.3458, 'longitude': 107.0805},
        {'province_id': 9, 'name': 'Lào Cai', 'latitude': 22.4965, 'longitude': 103.9635},
        {'province_id': 10, 'name': 'Quảng Ninh', 'latitude': 21.0180, 'longitude': 107.2245},
    ]
    
    # Sắp xếp theo tên tỉnh
    provinces_data_sorted = sorted(provinces_data, key=lambda p: p['name'])
    
    return jsonify(provinces_data_sorted)

def merge_api_and_ml_data(api_data, ml_data, province_name):
    """
    Merge dữ liệu từ Open-Meteo API và ML predictions
    Ưu tiên API cho giờ hiện tại và các giờ có sẵn,
    dùng ML để bổ sung các giờ còn thiếu
    """
    merged_data = {
        "location": province_name,
        "current": api_data.get("current", {}),
        "daily": {},
        "hourly": {},
        "ml_prediction": ml_data
    }
    
    # Merge hourly data
    api_hourly = api_data.get("hourly", {})
    api_times = api_hourly.get('time', [])
    
    if ml_data and 'hourly_predictions' in ml_data:
        ml_hourly = ml_data['hourly_predictions']
        
        # Tạo dict để dễ merge
        hourly_dict = {
            'time': [],
            'temperature_2m': [],
            'relative_humidity_2m': [],
            'precipitation': [],
            'rain': [],
            'showers': [],
            'weather_code': [],
            'pressure_msl': [],
            'wind_speed_10m': [],
            'wind_direction_10m': [],
            'visibility': [],
            'uv_index': []
        }
        
        # Lấy tất cả thời gian cần thiết (API + ML)
        all_times = []
        now = datetime.now()
        
        # Thêm từ API (nếu có)
        for i, time_str in enumerate(api_times):
            # Xử lý format thời gian đôi khi có 'Z'
            clean_time_str = time_str.replace('Z', '+00:00')
            try:
                time_obj = datetime.fromisoformat(clean_time_str)
            except ValueError:
                # Fallback nếu format lạ
                continue
                
            if time_obj >= now - timedelta(hours=1): # Lấy cả giờ hiện tại
                all_times.append({
                    'time': time_str,
                    'source': 'api',
                    'index': i
                })
        
        # Thêm từ ML cho các giờ còn thiếu
        for ml_hour in ml_hourly:
            ml_time = ml_hour['time']
            # Kiểm tra xem thời gian này đã có trong API chưa
            if ml_time not in [t['time'] for t in all_times]:
                all_times.append({
                    'time': ml_time,
                    'source': 'ml',
                    'data': ml_hour
                })
        
        # Sort theo thời gian
        all_times.sort(key=lambda x: x['time'])
        
        # Merge data (Lấy tối đa 48h)
        for time_info in all_times[:48]:
            hourly_dict['time'].append(time_info['time'])
            
            if time_info['source'] == 'api':
                idx = time_info['index']
                # Helper function để lấy safe value
                def get_val(key, default=0):
                    arr = api_hourly.get(key, [])
                    return arr[idx] if idx < len(arr) else default

                hourly_dict['temperature_2m'].append(get_val('temperature_2m'))
                hourly_dict['relative_humidity_2m'].append(get_val('relative_humidity_2m'))
                hourly_dict['precipitation'].append(get_val('precipitation'))
                hourly_dict['rain'].append(get_val('rain'))
                hourly_dict['showers'].append(get_val('showers'))
                hourly_dict['weather_code'].append(get_val('weather_code'))
                hourly_dict['pressure_msl'].append(get_val('pressure_msl'))
                hourly_dict['wind_speed_10m'].append(get_val('wind_speed_10m'))
                hourly_dict['wind_direction_10m'].append(get_val('wind_direction_10m'))
                hourly_dict['visibility'].append(get_val('visibility'))
                hourly_dict['uv_index'].append(get_val('uv_index'))
            else:  # ML data
                ml_hour = time_info['data']
                hourly_dict['temperature_2m'].append(ml_hour.get('temperature_2m', 0))
                hourly_dict['relative_humidity_2m'].append(ml_hour.get('relative_humidity_2m', 0))
                hourly_dict['precipitation'].append(ml_hour.get('precipitation', 0))
                hourly_dict['rain'].append(ml_hour.get('precipitation', 0)) # ML gộp rain
                hourly_dict['showers'].append(0)
                hourly_dict['weather_code'].append(ml_hour.get('weather_code', 0))
                hourly_dict['pressure_msl'].append(ml_hour.get('pressure_msl', 0))
                hourly_dict['wind_speed_10m'].append(ml_hour.get('wind_speed_10m', 0))
                hourly_dict['wind_direction_10m'].append(0)
                hourly_dict['visibility'].append(ml_hour.get('visibility', 0))
                hourly_dict['uv_index'].append(ml_hour.get('uv_index', 0))
        
        merged_data['hourly'] = hourly_dict
    else:
        merged_data['hourly'] = api_hourly
    
    # Merge daily data
    api_daily = api_data.get("daily", {})
    
    if ml_data and 'daily_forecast' in ml_data:
        ml_daily = ml_data['daily_forecast']
        api_daily_times = api_daily.get('time', [])
        
        # Nếu API có ít hơn 7 ngày, bổ sung từ ML
        if len(api_daily_times) < 7:
            daily_dict = {
                'time': list(api_daily.get('time', [])),
                'weather_code': list(api_daily.get('weather_code', [])),
                'temperature_2m_max': list(api_daily.get('temperature_2m_max', [])),
                'temperature_2m_min': list(api_daily.get('temperature_2m_min', [])),
                'precipitation_sum': list(api_daily.get('precipitation_sum', [])),
                'wind_speed_10m_max': list(api_daily.get('wind_speed_10m_max', [])),
                'sunrise': list(api_daily.get('sunrise', [])),
                'sunset': list(api_daily.get('sunset', []))
            }
            
            for ml_day in ml_daily:
                if ml_day['time'] not in daily_dict['time']:
                    daily_dict['time'].append(ml_day['time'])
                    daily_dict['weather_code'].append(ml_day['weather_code'])
                    daily_dict['temperature_2m_max'].append(ml_day['temperature_2m_max'])
                    daily_dict['temperature_2m_min'].append(ml_day['temperature_2m_min'])
                    daily_dict['precipitation_sum'].append(ml_day['precipitation_sum'])
                    daily_dict['wind_speed_10m_max'].append(ml_day['wind_speed_10m_max'])
                    daily_dict['sunrise'].append(ml_day['sunrise'])
                    daily_dict['sunset'].append(ml_day['sunset'])
                    
                    if len(daily_dict['time']) >= 7:
                        break
            
            merged_data['daily'] = daily_dict
        else:
            merged_data['daily'] = api_daily
    else:
        merged_data['daily'] = api_daily
    
    return merged_data

@forecast_bp.route('/api/forecast')
def api_get_forecast():
    """
    API lấy dữ liệu thời tiết (Open-Meteo + ML/Cache + AQI).
    Logic mới:
    1. Lấy API Open-Meteo (Realtime).
    2. Thử lấy dữ liệu ML từ Cache DB (weather_forecast_cache).
    3. Nếu không có Cache, chạy Fallback (tính toán trực tiếp).
    4. Merge dữ liệu và trả về.
    """
    province_name = request.args.get('province', '')
    days = int(request.args.get('days', 7))
    
    if not province_name:
        return jsonify({"error": "Thiếu province"}), 400

    try:
        # Tìm tỉnh từ danh sách hardcode
        provinces_data = [
            {'province_id': 1, 'name': 'Hà Nội', 'latitude': 21.0285, 'longitude': 105.8542},
            {'province_id': 2, 'name': 'TP. Hồ Chí Minh', 'latitude': 10.8231, 'longitude': 106.6297},
            {'province_id': 3, 'name': 'Đà Nẵng', 'latitude': 16.0544, 'longitude': 108.2022},
            {'province_id': 4, 'name': 'Hải Phòng', 'latitude': 20.8449, 'longitude': 106.6881},
            {'province_id': 5, 'name': 'Cần Thơ', 'latitude': 10.0452, 'longitude': 105.7468},
            {'province_id': 6, 'name': 'Huế', 'latitude': 16.4637, 'longitude': 107.5909},
            {'province_id': 7, 'name': 'Nha Trang', 'latitude': 12.2388, 'longitude': 109.1967},
            {'province_id': 8, 'name': 'Vũng Tàu', 'latitude': 10.3458, 'longitude': 107.0805},
            {'province_id': 9, 'name': 'Lào Cai', 'latitude': 22.4965, 'longitude': 103.9635},
            {'province_id': 10, 'name': 'Quảng Ninh', 'latitude': 21.0180, 'longitude': 107.2245},
        ]
        
        province = next((p for p in provinces_data if p['name'] == province_name), None)
        if not province:
            return jsonify({"error": "Không tìm thấy tỉnh"}), 404

        # 1. Gọi Open-Meteo API
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": province['latitude'],
            "longitude": province['longitude'],
            "hourly": "temperature_2m,relative_humidity_2m,precipitation,rain,showers,weather_code,pressure_msl,wind_speed_10m,wind_direction_10m,visibility,uv_index",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,sunrise,sunset",
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,wind_speed_10m,pressure_msl,visibility,uv_index,weather_code",
            "timezone": "Asia/Bangkok",
            "forecast_days": min(days, 16)
        }
        
        response = requests.get(url, params=params, timeout=30)
        # Nếu lỗi Open-Meteo, có thể vẫn chạy tiếp nếu muốn, nhưng ở đây ta raise lỗi
        response.raise_for_status()
        api_data = response.json()

        # 2. LẤY DỮ LIỆU ML (Dự báo sử dụng Machine Learning)
        ml_data = None
        try:
            # 3. FALLBACK: Chạy tính toán realtime dựa trên dữ liệu mới nhất
            # Dữ liệu này sẽ được predict_storm lấy từ SQLite (bảng weather_data)
            current_weather_data = {
                'temperature_2m': api_data.get("current", {}).get('temperature_2m', 25),
                'relative_humidity_2m': api_data.get("current", {}).get('relative_humidity_2m', 70),
                'pressure_msl': api_data.get("current", {}).get('pressure_msl', 1013),
                'wind_speed_10m': api_data.get("current", {}).get('wind_speed_10m', 5)
            }
            
            # Gọi hàm dự báo AI
            ml_data = predict_storm(province['province_id'], current_weather_data)
            
            if ml_data and 'error' in ml_data:
                print(f"Bỏ qua AI (Model chưa sẵn sàng): {ml_data['error']}")
                ml_data = None
        except Exception as e:
            print(f"Lỗi khi xử lý ML: {e}")
            ml_data = None
            
        # 4. Merge API và ML data (Hệ thống sẽ tự dùng API data nếu ml_data là None)
        forecast_data = merge_api_and_ml_data(api_data, ml_data, province_name)

        # 5. Fetch AQI (Chỉ số không khí)
        try:
            aqi_url = f"https://api.waqi.info/feed/geo:{province['latitude']};{province['longitude']}/?token=demo"
            aqi_response = requests.get(aqi_url, timeout=5)
            if aqi_response.status_code == 200:
                aqi_json = aqi_response.json()
                if aqi_json.get('status') == 'ok':
                    aqi_data = aqi_json.get('data', {})
                    forecast_data['aqi'] = {
                        'index': aqi_data.get('aqi', 0),
                        'components': aqi_data.get('iaqi', {})
                    }
                else:
                    forecast_data['aqi'] = {'index': 0, 'components': {}}
            else:
                forecast_data['aqi'] = {'index': 0, 'components': {}}
        except Exception as e:
            print(f"Lỗi AQI: {e}")
            forecast_data['aqi'] = {'index': 0, 'components': {}}

        return jsonify(forecast_data)
        
    except requests.RequestException as e:
        print(f"Lỗi request API: {e}")
        return jsonify({"error": f"Lỗi kết nối API thời tiết: {str(e)}"}), 500
    except Exception as e:
        print(f"Lỗi tổng quát: {e}")
        # In traceback để debug
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Lỗi server: {str(e)}"}), 500

# --- NEW STORM V2 API ENDPOINTS ---

def get_latest_analysis_file():
    """Finds the most recent '_analysis.json' file."""
    list_of_files = glob.glob(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'project_data', 'processed_output', '*_analysis.json'))
    if not list_of_files:
        return None
    latest_file = max(list_of_files, key=os.path.getctime)
    return latest_file

@forecast_bp.route('/api/forecast_storm')
def api_get_storm_forecast():
    """
    API để lấy dữ liệu dự báo bão V2 mới nhất.
    Đọc file JSON gần đây nhất và điều chỉnh output cho các kịch bản khác nhau.
    """
    print("--- [DEBUG] Inside api_get_storm_forecast ---")
    latest_file = get_latest_analysis_file()
    print(f"--- [DEBUG] latest_file = {latest_file} ---")
    
    if not latest_file:
        # SCENARIO 1: REAL-TIME, NO STORM
        print(f"--- [DEBUG] No forecast file found. Returning SAFE 'no_storm' response. ---")
        no_storm_response = {
            "status": "no_storm",
            "message": "Không có bão hoạt động. Biển Đông yên bình.",
            "is_simulation": False,
            "data": [],
            "actual_path": [],
            "trajectory": {},
            "stats": {},
            "origin": {},
            "analysis": {},
            "ai_report": {
                "marine_safety": {
                    "risk_score": 100,
                    "status": "AN TOÀN",
                    "summary": "Không phát hiện xoáy thuận nhiệt đới hoặc nhiễu động đáng kể. Điều kiện an toàn cho các hoạt động trên biển."
                }
            }
        }
        return jsonify(no_storm_response), 200
        
    try:
        with open(latest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # FIX: Align backend data structure with frontend expectation
        data['data'] = data.get('predicted_path', [])
        data['status'] = 'success'
        is_simulation = data.get("metadata", {}).get("is_simulation", False)
        data['is_simulation'] = is_simulation
        
        if is_simulation:
            # SCENARIO 2: SIMULATION MODE
            print("--- [DEBUG] Simulation run detected. Forcing DANGEROUS AI report. ---")
            data['ai_report'] = {
                "marine_safety": {
                    "risk_score": 15,
                    "status": "CỰC KỲ NGUY HIỂM",
                    "summary": "Mô phỏng cơn bão lịch sử (Rai 2021). Mức độ rủi ro được đặt ở mức nguy hiểm cao nhất."
                }
            }
            
            PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            SIMULATION_DATA_DIR = os.path.join(PROJECT_ROOT, 'services', 'storm_prediction_service', 'simulation_data')
            actual_path_file = os.path.join(SIMULATION_DATA_DIR, 'actual_path.csv')
            df_actual = pd.read_csv(actual_path_file)
            df_actual.rename(columns={'LATITUDE': 'LAT', 'LONGITUDE': 'LON', 'PRMSL': 'WMO_PRES', 'U10': 'WMO_WIND_U', 'V10': 'WMO_WIND_V'}, inplace=True)
            if 'WMO_WIND' not in df_actual.columns:
                df_actual['WMO_WIND'] = np.sqrt(df_actual['WMO_WIND_U']**2 + df_actual['WMO_WIND_V']**2)
            
            data['actual_path'] = df_actual.to_dict(orient='records')
            
            data['trajectory'] = TrajectoryAnalyzer.analyze_trajectory(data['actual_path'])
            data['stats'] = {
                "max_wind": df_actual['WMO_WIND'].max(),
                "min_pressure": df_actual['WMO_PRES'].min(),
                "total_days": len(df_actual) / 24.0,
            }
        else:
            # SCENARIO 3: REAL-TIME, STORM DETECTED
            print("--- [DEBUG] Real-time storm file detected. Using AI report from file. ---")
            data['actual_path'] = []
            data['trajectory'] = TrajectoryAnalyzer.analyze_trajectory(data.get('predicted_path', []))

        def convert_nan_to_none(obj):
            if isinstance(obj, dict):
                return {k: convert_nan_to_none(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_nan_to_none(elem) for elem in obj]
            elif isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
                return None
            elif isinstance(obj, np.generic):
                return obj.item()
            return obj

        response_data = convert_nan_to_none(data)
        
        print(f"--- [DEBUG] Returning success response (Simulation: {is_simulation}) ---")
        return jsonify(response_data)

    except FileNotFoundError:
        error_response = {"status": "error", "message": "File dự báo không tồn tại."}
        print(f"--- [DEBUG] Returning 404 FileNotFoundError: {error_response} ---")
        return jsonify(error_response), 404
    except Exception as e:
        import traceback
        traceback.print_exc()
        error_response = {"status": "error", "message": str(e)}
        print(f"--- [DEBUG] Returning 500 Exception: {error_response} ---")
        return jsonify(error_response), 500

@forecast_bp.route('/api/all_alerts')
def api_get_all_alerts():
    """API để lấy tất cả các cảnh báo từ file all_alerts.json."""
    alerts_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'project_data', 'grib2_output', 'all_alerts.json')
    try:
        with open(alerts_path, 'r', encoding='utf-8') as f:
            alerts = json.load(f)
        return jsonify(alerts)
    except FileNotFoundError:
        return jsonify([]) # Trả về mảng rỗng nếu không có file
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@forecast_bp.route('/api/weather')
def api_get_weather_analysis():
    """API lấy phân tích thời tiết từ file dự báo bão mới nhất."""
    latest_file = get_latest_analysis_file()
    if not latest_file:
        return jsonify({"weather_analysis": None}), 404
    
    try:
        with open(latest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Trả về phần phân tích tương tự như logic cũ
        analysis_data = data.get("trajectory_analysis", {}).get("weather_impact_analysis")
        
        return jsonify({"weather_analysis": analysis_data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- ROUTES FOR NEW MAP UI ---

@forecast_bp.route('/status')
def get_status():
    """Placeholder for the /status endpoint."""
    return jsonify({
        "status": "OK",
        "message": "System is running, but this is a placeholder.",
        "data": {
            "alerts": [],
            "storm": None,
            "trajectory": None
        }
    })

@forecast_bp.route('/api/toggle_demo', methods=['POST'])
def toggle_demo():
    """Placeholder for toggling demo mode."""
    # This would typically toggle a real state, but for now, we'll just log it
    print("--- [API] Demo mode toggled (placeholder) ---")
    return jsonify({"status": "OFF", "message": "Demo mode is off."})

@forecast_bp.route('/api/toggle_historical', methods=['POST'])
def toggle_historical():
    """Placeholder for toggling historical comparison mode."""
    print("--- [API] Historical mode toggled (placeholder) ---")
    return jsonify({"status": "OFF", "message": "Historical mode is off."})

@forecast_bp.route('/api/historical_result')
def get_historical_result():
    """Placeholder for getting historical comparison results."""
    print("--- [API] /api/historical_result requested, but no data available. ---")
    return jsonify({"error": "Not available"}), 404

# --- NEW ROUTES FOR MAP LAYERS ---

@forecast_bp.route('/latest-grib')
def get_latest_grib_file():
    """Finds the most recent GRIB2 file in the data directory."""
    try:
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'project_data', 'data')
        list_of_files = glob.glob(os.path.join(data_dir, '*.grib2'))
        if not list_of_files:
            return jsonify({'error': 'No GRIB2 files found'}), 404
        latest_file = max(list_of_files, key=os.path.getctime)
        return jsonify({'file': os.path.basename(latest_file)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@forecast_bp.route('/grib-json')
def get_grib_as_json():
    """Converts a specified GRIB2 file to a JSON object with weather data."""
    file_name = request.args.get('file')
    if not file_name:
        return jsonify({"error": "Missing 'file' parameter"}), 400

    try:
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'project_data', 'data')
        file_path = os.path.join(data_dir, file_name)

        if not os.path.exists(file_path):
            return jsonify({"error": f"File not found: {file_name}"}), 404

        data = {
            'latitude': [],
            'longitude': [],
            'prmsl': [],
            'u10': [],
            'v10': [],
            'temp': []
        }

        # Pressure data (mean sea level)
        try:
            ds_pressure = xr.open_dataset(file_path, engine="cfgrib", backend_kwargs={'filter_by_keys': {'typeOfLevel': 'meanSea'}})
            data['latitude'] = ds_pressure['latitude'].values.tolist()
            data['longitude'] = ds_pressure['longitude'].values.tolist()
            data['prmsl'] = ds_pressure['prmsl'].values.tolist()
        except (KeyError, ValueError) as e:
            print(f"Warning: Could not read pressure data: {e}")

        # Wind data (10m above ground)
        try:
            ds_wind = xr.open_dataset(file_path, engine="cfgrib", backend_kwargs={'filter_by_keys': {'typeOfLevel': 'heightAboveGround', 'level': 10}})
            # Only set latitude/longitude if they weren't set by pressure data
            if not data['latitude']:
                data['latitude'] = ds_wind['latitude'].values.tolist()
            if not data['longitude']:
                data['longitude'] = ds_wind['longitude'].values.tolist()
            data['u10'] = ds_wind['u10'].values.tolist()
            data['v10'] = ds_wind['v10'].values.tolist()
        except (KeyError, ValueError) as e:
            print(f"Warning: Could not read wind data: {e}")

        # Temperature data (surface level)
        try:
            ds_temp_surface = xr.open_dataset(file_path, engine="cfgrib", backend_kwargs={'filter_by_keys': {'typeOfLevel': 'surface'}})
            data['temp'] = ds_temp_surface['t'].values.tolist()
        except (KeyError, ValueError, IndexError) as e:
            print(f"Warning: Could not read surface temperature data: {e}. Temperature data will be missing.")

        return jsonify(data)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
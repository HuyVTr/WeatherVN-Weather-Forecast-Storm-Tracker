import os
import sys
import numpy as np
import torch
import pandas as pd
from torch.cuda.amp import autocast

# Setup paths
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR) # Assuming script is in weather_project/tests/ or root
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from services.storm_prediction_service.final_storm_forecast import FinalStormSystem
from services.storm_prediction_service.data_processor import FinalDataProcessor

def haversine_np(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees) - Vectorized
    """
    R = 6371.0 # Earth radius in kilometers

    lat1_r = np.radians(lat1)
    lon1_r = np.radians(lon1)
    lat2_r = np.radians(lat2)
    lon2_r = np.radians(lon2)

    dlon = lon2_r - lon1_r
    dlat = lat2_r - lat1_r

    a = np.sin(dlat / 2)**2 + np.cos(lat1_r) * np.cos(lat2_r) * np.sin(dlon / 2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

    distance = R * c
    return distance

def calculate_reliability():
    print("\n" + "="*80)
    print("📊 BẮT ĐẦU ĐÁNH GIÁ ĐỘ TIN CẬY MÔ HÌNH (FINAL STORM FORECAST)")
    print("="*80)

    # 1. Initialize System and Load Data
    system = FinalStormSystem(device='cpu') # Use CPU for evaluation to be safe
    print("\n[1/5] Đang tải và xử lý dữ liệu kiểm tra (Test Set)...")
    
    # Force reload data
    system.processor.load_and_process()
    
    # Create sequences (Train/Val/Test)
    # Note: We only care about X_test and y_test
    _, _, _, _, X_test, y_test = system.processor.create_sequences(seq_len=72, forecast_horizon=168)
    
    if X_test is None or len(X_test) == 0:
        print("❌ Lỗi: Không có dữ liệu kiểm tra (Test Set).")
        return

    print(f"   -> Số lượng mẫu kiểm tra: {len(X_test)} mẫu bão (mỗi mẫu dài 168 giờ).")

    # 2. Run Predictions
    print("\n[2/5] Đang chạy mô hình trên tập Test...")
    system.model.load_state_dict(torch.load(system.model_path, map_location='cpu'))
    system.model.eval()

    predictions = []
    batch_size = 32
    
    with torch.no_grad():
        for i in range(0, len(X_test), batch_size):
            batch_X = torch.from_numpy(X_test[i:i+batch_size])
            outputs = system.model(batch_X)
            predictions.append(outputs['full'].numpy())
            
    predictions = np.concatenate(predictions, axis=0)
    
    # 3. Denormalize Data (Convert back to Real Units)
    print("\n[3/5] Đang giải mã dữ liệu (Denormalization)...")
    
    def denormalize(data_tensor):
        # data_tensor shape: (samples, time_steps, features)
        denorm_data = data_tensor.copy()
        for idx, feat in enumerate(system.processor.FEATURES):
            p = system.processor.scaler_params[feat]
            mn, mx = p['min'], p['max']
            denom = mx - mn if (mx - mn) > 1e-8 else 1.0
            denorm_data[:, :, idx] = data_tensor[:, :, idx] * denom + mn
        return denorm_data

    y_true_real = denormalize(y_test)
    y_pred_real = denormalize(predictions)

    # 4. Calculate Metrics
    print("\n[4/5] Đang tính toán các chỉ số sai số (Metrics)...")
    
    # Indices of features
    lat_idx = system.processor.FEATURES.index('LAT')
    lon_idx = system.processor.FEATURES.index('LON')
    wind_idx = system.processor.FEATURES.index('WMO_WIND')
    pres_idx = system.processor.FEATURES.index('WMO_PRES')

    # Calculate errors per time step for all samples
    # Shapes: (Num_Samples, 168)
    lat_true, lon_true = y_true_real[:, :, lat_idx], y_true_real[:, :, lon_idx]
    lat_pred, lon_pred = y_pred_real[:, :, lat_idx], y_pred_real[:, :, lon_idx]
    
    wind_true, wind_pred = y_true_real[:, :, wind_idx], y_pred_real[:, :, wind_idx]
    pres_true, pres_pred = y_true_real[:, :, pres_idx], y_pred_real[:, :, pres_idx]

    # Haversine Error (km)
    position_errors = haversine_np(lat_true, lon_true, lat_pred, lon_pred)
    
    # R2 Score Calculation Function
    def r2_score_np(y_true, y_pred):
        ss_res = np.sum((y_true - y_pred) ** 2, axis=0)
        ss_tot = np.sum((y_true - np.mean(y_true, axis=0)) ** 2, axis=0)
        # Avoid division by zero
        with np.errstate(divide='ignore', invalid='ignore'):
            r2 = 1 - (ss_res / ss_tot)
        r2[ss_tot == 0] = 0 # If variance is 0, R2 is 0
        return np.mean(r2) # Mean R2 across all samples for that time step

    # --- Calculate MAE/MSE/RMSE for Lat/Lon (Previously missing) ---
    lat_errors_mae = np.abs(lat_true - lat_pred)
    lon_errors_mae = np.abs(lon_true - lon_pred)
    lat_mse = (lat_true - lat_pred) ** 2
    lon_mse = (lon_true - lon_pred) ** 2
    
    # --- Calculate Wind/Pressure Errors ---
    wind_errors_mae = np.abs(wind_true - wind_pred)
    wind_mse = (wind_true - wind_pred) ** 2
    pres_errors_mae = np.abs(pres_true - pres_pred)
    pres_mse = (pres_true - pres_pred) ** 2

    # --- Prepare for Detailed Reporting ---
    lead_times = [24, 48, 72] # Focus on 3 key milestones
    
    report_lines = []
    report_lines.append("====================================================================================================")
    report_lines.append(f"{'ĐẶC TRƯNG':<12} | {'MỐC':<5} | {'MAE':<12} | {'MSE':<12} | {'RMSE':<12} | {'R² (0-1)':<10}")
    report_lines.append("----------------------------------------------------------------------------------------------------")

    for t in lead_times:
        if t > position_errors.shape[1]: continue
        idx = t - 1

        # 1. LATITUDE
        l_mae = np.mean(lat_errors_mae[:, idx])
        l_mse = np.mean(lat_mse[:, idx])
        l_rmse = np.sqrt(l_mse)
        l_r2 = r2_score_np(lat_true[:, idx:idx+1], lat_pred[:, idx:idx+1])
        report_lines.append(f"{'LATITUDE':<12} | {t}h   | {l_mae:<12.4f} | {l_mse:<12.4f} | {l_rmse:<12.4f} | {l_r2:<10.4f}")

        # 2. LONGITUDE
        lo_mae = np.mean(lon_errors_mae[:, idx])
        lo_mse = np.mean(lon_mse[:, idx])
        lo_rmse = np.sqrt(lo_mse)
        lo_r2 = r2_score_np(lon_true[:, idx:idx+1], lon_pred[:, idx:idx+1])
        report_lines.append(f"{'LONGITUDE':<12} | {t}h   | {lo_mae:<12.4f} | {lo_mse:<12.4f} | {lo_rmse:<12.4f} | {lo_r2:<10.4f}")

        # 3. WIND SPEED
        w_mae = np.mean(wind_errors_mae[:, idx])
        w_mse = np.mean(wind_mse[:, idx])
        w_rmse = np.sqrt(w_mse)
        w_r2 = r2_score_np(wind_true[:, idx:idx+1], wind_pred[:, idx:idx+1])
        report_lines.append(f"{'WIND SPEED':<12} | {t}h   | {w_mae:<12.4f} | {w_mse:<12.4f} | {w_rmse:<12.4f} | {w_r2:<10.4f}")

        # 4. PRESSURE
        p_mae = np.mean(pres_errors_mae[:, idx])
        p_mse = np.mean(pres_mse[:, idx])
        p_rmse = np.sqrt(p_mse)
        p_r2 = r2_score_np(pres_true[:, idx:idx+1], pres_pred[:, idx:idx+1])
        report_lines.append(f"{'PRESSURE':<12} | {t}h   | {p_mae:<12.4f} | {p_mse:<12.4f} | {p_rmse:<12.4f} | {p_r2:<10.4f}")
        
        report_lines.append("- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -")

    report_lines.append("====================================================================================================")
    
    # Calculate MPE Summary separately
    report_lines.append("\n\n*** SAI SỐ VỊ TRÍ TỔNG HỢP (MPE - Mean Position Error) ***")
    report_lines.append(f"{'MỐC':<5} | {'MPE (km)':<15}")
    report_lines.append("---------------------")
    for t in lead_times:
         idx = t - 1
         mpe = np.mean(position_errors[:, idx])
         report_lines.append(f"{t}h   | {mpe:<15.4f}")

    # Print to console
    full_report = "\n".join(report_lines)
    print(full_report)

    # Save to file
    out_file = "BANG_KET_QUA_CHI_TIET.txt"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(full_report)
    print(f"\n✅ Đã lưu bảng kết quả chi tiết vào file: {out_file}")
    
    # Overall Summary
    avg_pos_72h = np.mean(position_errors[:, :72])
    print(f"\n📊 TỔNG KẾT (Trung bình 3 ngày đầu):")
    print(f"   -> Sai số vị trí trung bình: {avg_pos_72h:.2f} km")
    print(f"   -> Sai số gió trung bình:    {np.mean(wind_errors_mae[:, :72]):.2f} m/s")
    print(f"   -> Sai số khí áp trung bình: {np.mean(pres_errors_mae[:, :72]):.2f} hPa")

    # Benchmarking (Comparison with Reference)
    print("\n⚖️  SO SÁNH VỚI CHUẨN QUỐC TẾ (Tham khảo):")
    print("   (Lưu ý: Các trung tâm lớn như JTWC/ECMWF thường có sai số 24h ~ 80km, 48h ~ 150km)")
    
    if 24 in metrics_summary:
        err_24 = metrics_summary[24]['pos']
        rating = "TỐT" if err_24 < 100 else "KHÁ" if err_24 < 150 else "TRUNG BÌNH" if err_24 < 200 else "CẦN CẢI THIỆN"
        print(f"   -> Đánh giá mô hình tại 24h: {rating} ({err_24:.1f} km)")

if __name__ == "__main__":
    calculate_reliability()

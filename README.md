# 🌀 WeatherVN - Hệ thống Dự báo và Theo dõi Bão (Storm Forecast & Tracking)

Chào mừng bạn đến với **WeatherVN**, một hệ thống ứng dụng Trí tuệ Nhân tạo (Machine Learning) để dự báo quỹ đạo, cường độ và phân tích các cơn bão trong khu vực Biển Đông và lân cận. Hệ thống sử dụng dữ liệu thời gian thực từ GFS (NCEP) và GDACS để đưa ra các nhận định chính xác nhất.

## 🚀 Tính năng chính

*   **Dự báo Real-time**: Tự động quét và phát hiện các nhiễu động nhiệt đới hoặc bão đang hoạt động.
*   **Dự báo liên tục (24/7)**: Chế độ tự động tải dữ liệu GFS mới nhất mỗi 6 giờ và cập nhật dự báo hàng phút.
*   **Mô phỏng bão lịch sử**: Cho phép chạy lại các kịch bản bão lớn (như siêu bão Rai 2021) để kiểm tra độ chính xác của mô hình.
*   **Phân tích AI tổng quát**: Tích hợp các module phân tích sự hình thành, quỹ đạo và các chỉ số khí tượng chi tiết.
*   **Giao diện Web trực quan**: Bản đồ hiển thị vị trí bão, đường đi dự báo và các trạm quan trắc thời tiết.

---

## 🛠 Hướng dẫn Cài đặt

### 1. Yêu cầu hệ thống
*   **Python**: 3.9 trở lên.
*   **Database**: PostgreSQL (Tên database: `weather_project`).
*   **Cấu hình**: CPU mạnh hoặc GPU (NVIDIA Cuda) để huấn luyện mô hình nhanh hơn.

### 2. Cài đặt môi trường
Mở terminal tại thư mục gốc của dự án và chạy các lệnh sau:

```bash
# Tạo môi trường ảo
python -m venv venv

# Kích hoạt môi trường ảo (Windows)
venv\Scripts\activate

# Cài đặt các thư viện cần thiết
pip install -r requirements.txt
```

### 3. Cấu hình Database
Đảm bảo bạn đã cài đặt PostgreSQL và tạo một database tên là `weather_project`. 
- Mặc định hệ thống dùng user `postgres` và mật khẩu `123456`.
- Bạn có thể thay đổi mật khẩu bằng cách đặt biến môi trường: `set DB_PASSWORD=your_password`.

---

## 📊 Dữ liệu Huấn luyện (Training Data)

Để hệ thống có thể hoạt động và dự báo chính xác, bạn cần tải file dữ liệu huấn luyện và đặt đúng vị trí.

*   **Link tải file CSV**: [Tải tại Google Drive](https://drive.google.com/file/d/1IOJGnnwfp2rSxfh0GtSfbSJXT2EOGGc8/view?usp=sharing)
*   **Tên file**: `FINAL_TRAINING_DATASET_ENHANCED.csv`
*   **Vị trí đặt file**: 
    Bạn cần tạo thư mục theo đường dẫn sau (nếu chưa có) và copy file vào:
    `project_data/data_train/FINAL_TRAINING_DATASET_ENHANCED.csv`

---

## 🚦 Hướng dẫn Sử dụng

Để khởi động hệ thống một cách dễ dàng nhất, hãy chạy file `START.bat` từ thư mục gốc. Một menu lựa chọn sẽ hiện ra:

1.  **Chế độ dự báo liên tục + Web Server**: Phù hợp để treo máy theo dõi bão thời gian thực.
2.  **Dự báo Real-time một lần + Web Server**: Chạy dự báo ngay lập tức và mở web xem kết quả.
3.  **Huấn luyện nhanh (Quick Train)**: Cập nhật mô hình ML với một phần dữ liệu (chạy nhanh).
4.  **Huấn luyện đầy đủ (Full Train)**: Huấn luyện mô hình chuyên sâu trên toàn bộ tập dữ liệu.
5.  **Mô phỏng bão Rai**: Chạy thử nghiệm hệ thống với dữ liệu bão lịch sử.

### Cách truy cập Giao diện Web:
Sau khi khởi động Web Server, hãy mở trình duyệt và truy cập:
👉 `http://127.0.0.1:8000`

---

## 📁 Cấu trúc thư mục chính

*   `app.py`: File chính khởi chạy Flask Web Server.
*   `START.bat`: Công cụ điều khiển hệ thống nhanh.
*   `services/`: Chứa các dịch vụ lõi về dự báo, xử lý dữ liệu GRIB2 và ML.
*   `backend_api/`: Chứa logic xử lý API, Models (SQLAlchemy), Templates và Static files (Giao diện).
*   `project_data/`: Nơi lưu trữ dữ liệu GFS tải về và các file kết quả dự báo.

---

## 📝 Ghi chú
- Hệ thống yêu cầu kết nối Internet để tải dữ liệu GFS từ server NCEP.
- Nếu bạn có GPU NVIDIA, hệ thống sẽ tự động sử dụng `cuda` để tăng tốc độ xử lý.

---
*Phát triển bởi 🚀 HuyVTr & Team*

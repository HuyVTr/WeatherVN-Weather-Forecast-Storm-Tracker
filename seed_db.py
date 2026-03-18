from app import create_app  # type: ignore
from backend_api.models import db  # type: ignore
from backend_api.models.weather_model import Provinces  # type: ignore

def seed_provinces():
    app = create_app()
    with app.app_context():
        # Danh sách các tỉnh thành Việt Nam (tên, vĩ độ, kinh độ)
        vietnam_provinces = [
            ("Hà Nội", 21.0285, 105.8542),
            ("TP. Hồ Chí Minh", 10.8231, 106.6297),
            ("Đà Nẵng", 16.0544, 108.2022),
            ("Hải Phòng", 20.8449, 106.6881),
            ("Cần Thơ", 10.0452, 105.7469),
            ("An Giang", 10.5216, 105.1259),
            ("Bà Rịa - Vũng Tàu", 10.4114, 107.1360),
            ("Bắc Giang", 21.2731, 106.1946),
            ("Bắc Kạn", 22.1470, 105.8327),
            ("Bạc Liêu", 9.2940, 105.7274),
            ("Bắc Ninh", 21.1861, 106.0763),
            ("Bến Tre", 10.2425, 106.3768),
            ("Bình Định", 13.7820, 109.2193),
            ("Bình Dương", 11.0855, 106.7131),
            ("Bình Phước", 11.7516, 106.8407),
            ("Bình Thuận", 10.9333, 108.0999),
            ("Cà Mau", 9.1769, 105.1501),
            ("Cao Bằng", 22.6664, 106.2629),
            ("Đắk Lắk", 12.6667, 108.0500),
            ("Đắk Nông", 12.0000, 107.6667),
            ("Điện Biên", 21.3857, 103.0210),
            ("Đồng Nai", 10.9574, 106.8166),
            ("Đồng Tháp", 10.4574, 105.6375),
            ("Gia Lai", 13.9833, 108.0000),
            ("Hà Giang", 22.8233, 104.9836),
            ("Hà Nam", 20.5847, 105.9131),
            ("Hà Tĩnh", 18.3333, 105.9000),
            ("Hải Dương", 20.9389, 106.3142),
            ("Hậu Giang", 9.7844, 105.4700),
            ("Hòa Bình", 20.8133, 105.3383),
            ("Hưng Yên", 20.6464, 106.0511),
            ("Khánh Hòa", 12.2467, 109.1917),
            ("Kiên Giang", 10.0114, 105.0809),
            ("Kon Tum", 14.3508, 108.0003),
            ("Lai Châu", 22.3956, 103.4686),
            ("Lâm Đồng", 11.9404, 108.4583),
            ("Lạng Sơn", 21.8542, 106.7625),
            ("Lào Cai", 22.4856, 103.9706),
            ("Long An", 10.5333, 106.4167),
            ("Nam Định", 20.4200, 106.1683),
            ("Nghệ An", 18.6667, 105.6667),
            ("Ninh Bình", 20.2531, 105.9750),
            ("Ninh Thuận", 11.5622, 108.9903),
            ("Phú Thọ", 21.3200, 105.4053),
            ("Phú Yên", 13.0886, 109.3108),
            ("Quảng Bình", 17.4700, 106.6300),
            ("Quảng Nam", 15.5667, 108.4833),
            ("Quảng Ngãi", 15.1200, 108.8000),
            ("Quảng Ninh", 21.0000, 107.5000),
            ("Quảng Trị", 16.7500, 107.1667),
            ("Sóc Trăng", 9.6000, 105.9700),
            ("Sơn La", 21.3289, 103.9211),
            ("Tây Ninh", 11.3117, 106.0983),
            ("Thái Bình", 20.4500, 106.3333),
            ("Thái Nguyên", 21.5928, 105.8442),
            ("Thanh Hóa", 19.8075, 105.7764),
            ("Thừa Thiên Huế", 16.4633, 107.5908),
            ("Tiền Giang", 10.3500, 106.3500),
            ("Trà Vinh", 9.9328, 106.3380),
            ("Tuyên Quang", 21.8156, 105.2131),
            ("Vĩnh Long", 10.2500, 105.9667),
            ("Vĩnh Phúc", 21.3089, 105.6033),
            ("Yên Bái", 21.7228, 104.9114),
        ]

        # Xóa dữ liệu cũ nếu muốn làm mới hoàn toàn (tùy chọn)
        # db.session.query(Provinces).delete()
        
        print(">> Đang nạp danh sách Tỉnh/Thành Việt Nam...")
        for name, lat, lon in vietnam_provinces:
            if not Provinces.query.filter_by(name=name).first():
                new_province = Provinces(name=name, latitude=lat, longitude=lon)
                db.session.add(new_province)
        
        db.session.commit()
        print(f">> Thành công! Đã nạp {len(vietnam_provinces)} tỉnh thành vào SQLite.")

if __name__ == "__main__":
    seed_provinces()

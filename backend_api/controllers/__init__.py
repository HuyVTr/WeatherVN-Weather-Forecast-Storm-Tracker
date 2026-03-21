from flask import Flask, request

def register_blueprints(app: Flask):
    
    # Context processor to globally handle active nav state
    @app.context_processor
    def inject_nav():
        endpoint = request.endpoint or ""
        nav_map = {
            'main_bp.route_home': 'home',
            'main_bp.route_news': 'news',
            'main_bp.about': 'about',
            'main_bp.contact': 'contact',
            'main_bp.route_weather_map': 'weather_map',
            'forecast_bp.forecast_page': 'forecast',
            'chart_bp.route_chart': 'chart'
        }
        return {'nav_active': nav_map.get(endpoint, '')}

    # main_bp – luôn có
    from .main_controller import main_bp
    app.register_blueprint(main_bp)
    print("Đã đăng ký: main_bp")

    # forecast_bp – có thể chưa hoàn thiện
    try:
        from .forecast_controller import forecast_bp
        app.register_blueprint(forecast_bp)
        print("Đã đăng ký: forecast_bp")
    except Exception as e:
        print(f"Chưa đăng ký forecast_bp: {e}")

    # chart_bp – CHẮC CHẮN PHẢI CÓ
    try:
        from .chart_controller import chart_bp
        app.register_blueprint(chart_bp)
        print("ĐÃ ĐĂNG KÝ THÀNH CÔNG: chart_bp → /chart hoạt động!")
    except Exception as e:
        print(f"LỖI KHÔNG ĐĂNG KÝ ĐƯỢC chart_bp: {e}")

    
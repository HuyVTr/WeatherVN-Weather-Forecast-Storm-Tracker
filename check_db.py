from app import create_app
from backend_api.models.weather_model import Provinces

app = create_app()
with app.app_context():
    count = Provinces.query.count()
    print(f"Province count: {count}")
    if count == 0:
        print("Empty database!")
    else:
        for p in Provinces.query.limit(5).all():
            print(f"- {p.name}: {p.latitude}, {p.longitude}")

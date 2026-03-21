# Coding Style and Conventions

## Python
- **Naming**: Use `snake_case` for functions, variables, and modules. Use `PascalCase` for classes (e.g., `Provinces`, `WeatherData`).
- **Docstrings**: Use triple double quotes `"""` for function and class docstrings. Many existing docstrings are in Vietnamese.
- **Comments**: Comments are encouraged and often written in Vietnamese to explain logic, especially in complex ML or data processing sections.
- **Imports**: Group imports into three sections:
    1. Standard library imports.
    2. Third-party library imports.
    3. Local application imports.
- **Patterns**: The Flask application follows the Application Factory pattern (`create_app()` in `app.py`). Blueprints are used for modularizing controllers (`backend_api/controllers/`).

## Frontend
- **CSS**: Vanilla CSS is preferred. No heavy frameworks like Tailwind are used in the core project.
- **JavaScript**: Vanilla JS with libraries like Leaflet/MapLibre (inferred from map functionality) for interactive elements.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api.endpoints.map import campus, building, floor, room, segment, connection, outdoor_segment, route
from app.api.endpoints.users import auth
from app.users.dependencies import security

app = FastAPI(
    swagger_ui_init_oauth={
        "clientId": "admin",
        "appName": "Admin API",
    },
)

# Встроенный JavaScript-код, который вставит токен из куков в Swagger
SWAGGER_SCRIPT = """
window.onload = function() {
    fetch('/get-token').then(response => response.json()).then(data => {
        if (data.token) {
            ui.preauthorizeApiKey("bearerAuth", data.token);
        }
    }).catch(err => console.log("Не удалось получить токен:", err));
};
"""

# Добавляем кастомный Swagger UI с нашим скриптом

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://map.sereosly.ru"],
    allow_credentials=True,  # Разрешает отправку cookie (включая HttpOnly)
    allow_methods=["*"],     # Разрешает все HTTP-методы (GET, POST, PUT, DELETE и т.д.)
    allow_headers=["*"],     # Разрешает все заголовки
)

# Подключаем статические файлы
app.mount("/static", StaticFiles(directory="static"), name="static")

# Подключаем маршруты
app.include_router(campus.router)
app.include_router(building.router)
app.include_router(floor.router)
app.include_router(room.router)
app.include_router(segment.router)
app.include_router(connection.router)
app.include_router(outdoor_segment.router)
app.include_router(auth.router)
app.include_router(route.router)


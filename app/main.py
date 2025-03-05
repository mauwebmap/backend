from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api.endpoints.map import campus, building, floor, room, segment, connection, outdoor_segment, route

app = FastAPI()

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
app.include_router(route.router)
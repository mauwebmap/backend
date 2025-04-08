# main.py
import logging
import logging.handlers
import queue
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pathlib import Path
import markdown
import os
from starlette.responses import Response

# Настройка очереди для логов
log_queue = queue.Queue(-1)  # Неограниченная очередь
queue_handler = logging.handlers.QueueHandler(log_queue)

# Форматтер для логов
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')

# Обработчик для записи в файл и stdout
file_handler = logging.FileHandler("/var/log/myapp.log")
file_handler.setFormatter(formatter)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

# Listener для обработки логов из очереди
listener = logging.handlers.QueueListener(log_queue, file_handler, stream_handler)
listener.start()

# Настройка корневого логгера
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
# Удаляем все существующие обработчики
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)
root_logger.addHandler(queue_handler)

# Настройка логгеров FastAPI и Uvicorn
logging.getLogger("fastapi").handlers = [queue_handler]
logging.getLogger("uvicorn").handlers = [queue_handler]
logging.getLogger("uvicorn.access").handlers = [queue_handler]

logger = logging.getLogger(__name__)

app = FastAPI(
    swagger_ui_init_oauth={
        "clientId": "admin",
        "appName": "Admin API",
    },
)

# Путь к README.md (относительно расположения main.py)
README_PATH = Path(__file__).parent.parent / "readme.md"

# Кеширование содержимого
cached_content = None
last_modified = None

def get_readme_html():
    global cached_content, last_modified
    current_modified = os.path.getmtime(README_PATH)

    if not cached_content or current_modified != last_modified:
        try:
            with open(README_PATH, "r", encoding="utf-8") as f:
                content = f.read()
                cached_content = markdown.markdown(content, extensions=['fenced_code', 'tables'])
                last_modified = current_modified
        except FileNotFoundError:
            cached_content = "<h1>Документация не найдена</h1>"
    return cached_content

# Добавляем middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://dev.sereosly.ru",
        "https://map.sereosly.ru",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Set-Cookie"]
)

# Создаем директорию static, если её нет
static_dir = Path("static")
static_dir.mkdir(exist_ok=True)

# Подключаем статические файлы
@app.get("/static/{path:path}")
async def serve_static(path: str, request: Request):
    file_path = static_dir / path
    if not file_path.exists():
        return Response(status_code=404, content="File not found")

    response = FileResponse(file_path)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response

# Главная страница с README
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    content = get_readme_html()
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Документация проекта</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.2.0/github-markdown.min.css">
        <style>
            @font-face {{
                font-family: 'Truin';
                src: url('/static/Truin-Regular.ttf?v=1') format('truetype');
                font-weight: normal;
                font-style: normal;
            }}

            * {{
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }}
            body {{
                background-color: #0d1117;
            }}
            .markdown-body {{
                font-family: 'Truin', sans-serif;
                font-size: 26px;
                letter-spacing: 0.12em;
                min-width: 200px;
                max-width: 980px;
                margin: 0 auto;
                padding: 45px;
            }}
            @media (max-width: 767px) {{
                .markdown-body {{
                    padding: 20px;
                }}
            }}
        </style>
    </head>
    <body>
        <article class="markdown-body">
            {content}
        </article>
    </body>
    </html>
    """

# Подключаем маршруты
from app.api.endpoints.map import campus, building, floor, room, segment, connection, outdoor_segment, route, enum
from app.api.endpoints.users import auth

app.include_router(campus.router)
app.include_router(building.router)
app.include_router(floor.router)
app.include_router(room.router)
app.include_router(segment.router)
app.include_router(connection.router)
app.include_router(outdoor_segment.router)
app.include_router(auth.router)
app.include_router(route.router)
app.include_router(enum.router)

logger.info("Application started successfully")
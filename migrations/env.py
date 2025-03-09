import os
import sys

# Добавляем абсолютный путь к проекту в sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from logging.config import fileConfig
from sqlalchemy import create_engine
from alembic import context

# Импортируем настройки
from app.database.config.settings import settings

# Импортируем модели
from backend.app.map.models.campus import Campus
from backend.app.map.models.building import Building
from backend.app.map.models.floor import Floor
from backend.app.map.models.room import Room
from backend.app.map.models.segment import Segment
from backend.app.map.models.connection import Connection
from backend.app.map.models.outdoor_segment import OutdoorSegment
from backend.app.users.models import *

config = context.config

# Настройка логгера
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Указываем URL базы данных
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Используем метаданные из Base
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = create_engine(settings.DATABASE_URL)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
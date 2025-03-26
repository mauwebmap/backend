from pydantic_settings import BaseSettings
import socket


class Settings(BaseSettings):
    # Автодетект окружения
    ENV: str = "prod" if not socket.gethostname().lower().startswith("local") else "dev"

    # Настройки PostgreSQL
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "mapping_app"

    # Настройки безопасности
    SECRET_KEY: str = "dev-secret-key"
    REFRESH_SECRET_KEY: str = "dev-refresh-secret"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE: int = 30  # minutes
    REFRESH_TOKEN_EXPIRE: int = 7  # days

    # Настройки cookies
    @property
    def COOKIE_CONFIG(self):
        return {
            # "secure": True,  # HTTPS True только в prod
            # "samesite": "lax",
            # "domain": ".sereosly.ru"  # Общий домен для всех поддоменов
            "secure": False,
            "samesite": "None",
            "domain": None
        }

    # Строка подключения к БД
    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+psycopg2://"
            f"{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/"
            f"{self.POSTGRES_DB}"
        )


settings = Settings()
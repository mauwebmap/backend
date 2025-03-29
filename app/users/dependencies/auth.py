from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import HTTPException, Request, Response, Depends
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.database.config.settings import settings
from app.users.models import Admin
from passlib.context import CryptContext
from typing import Optional

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_token(data: dict, is_refresh: bool = False) -> str:
    """Создает токен (access или refresh)."""
    secret = settings.REFRESH_SECRET_KEY if is_refresh else settings.SECRET_KEY
    expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE) if is_refresh else timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE)

    return jwt.encode(
        {
            **data,
            "exp": datetime.utcnow() + expires,
            "type": "refresh" if is_refresh else "access"
        },
        secret,
        algorithm=settings.ALGORITHM
    )

def set_auth_cookies(response: Response, access: str, refresh: str):
    """Устанавливает куки для токенов."""
    response.set_cookie(
        key="access_token",
        value=access,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE * 60,
        **settings.COOKIE_CONFIG
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh,
        httponly=True,
        max_age=settings.REFRESH_TOKEN_EXPIRE * 24 * 3600,
        path="/",  # Доступен для всех маршрутов
        **settings.COOKIE_CONFIG
    )

async def get_token(request: Request) -> str | None:
    """Получает access_token из куки или заголовка."""
    return request.cookies.get("access_token") or \
           (request.headers.get("Authorization") or "").replace("Bearer ", "") or None

async def refresh_access_token(request: Request, response: Response, db: Session) -> str:
    """Обновляет access_token и refresh_token по refresh_token, возвращает новый access_token."""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Отсутствует refresh_token")

    try:
        payload = jwt.decode(refresh_token, settings.REFRESH_SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Неверный тип токена")

        admin = db.query(Admin).filter(Admin.username == payload.get("sub")).first()
        if not admin:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        if not admin.is_admin:
            raise HTTPException(status_code=403, detail="Требуются права администратора")

        new_access = create_token({"sub": admin.username, "is_admin": admin.is_admin})
        new_refresh = create_token({"sub": admin.username}, is_refresh=True)
        set_auth_cookies(response, new_access, new_refresh)
        return new_access
    except JWTError:
        raise HTTPException(status_code=401, detail="Недействительный refresh_token")

async def admin_required(request: Request, response: Response, db: Session = Depends(get_db)) -> Optional[str]:
    """Проверяет токены и права админа, обновляет токены только если access_token отсутствует."""
    if request.method == "GET":
        return None  # GET-запросы не требуют авторизации

    token = await get_token(request)
    if not token:  # Если access_token отсутствует
        new_access_token = await refresh_access_token(request, response, db)
        return new_access_token  # Возвращаем новый токен

    # Если access_token присутствует, проверяем его
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Неверный тип токена")
        if not payload.get("is_admin", False):
            raise HTTPException(status_code=403, detail="Требуются права администратора")
        return None  # Токен валиден, обновление не требуется
    except JWTError:  # Если токен истёк или недействителен
        raise HTTPException(status_code=401, detail="Недействительный или истёкший access_token")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет пароль."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Хеширует пароль."""
    return pwd_context.hash(password)
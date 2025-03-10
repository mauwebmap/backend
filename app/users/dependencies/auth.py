from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import HTTPException, Request, Response, Depends
from app.database.config.settings import settings
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_token(data: dict, is_refresh: bool = False) -> str:
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
        path="/auth/refresh",
        **settings.COOKIE_CONFIG
    )

async def get_token(request: Request):
    token = request.cookies.get("access_token") or \
            (request.headers.get("Authorization") or "").replace("Bearer ", "")
    if not token:
        raise HTTPException(status_code=401, detail="Токен не найден")
    return token

async def admin_required(token: str = Depends(get_token)):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Неверный тип токена")

        if not payload.get("is_admin", False):
            raise HTTPException(status_code=403, detail="Требуются права администратора")

        return payload

    except JWTError:
        raise HTTPException(status_code=401, detail="Ошибка токена")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

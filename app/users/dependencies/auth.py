from typing import Optional

from fastapi import Request, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os
from passlib.context import CryptContext

# Конфигурация
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
REFRESH_SECRET_KEY = os.getenv("REFRESH_SECRET_KEY", "your-refresh-secret-key") or "your-refresh-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 схема для Swagger (для "замочков")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token", scopes={"admin": "Admin access"})

# Для `security` в main.py (визуальные "замочки")
security = [{"bearerAuth": ["admin"]}]

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, REFRESH_SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str, secret_key: str):
    try:
        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        print(f"JWT verification failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Неверный токен")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

async def get_token(request: Request):
    # Проверяем токен из заголовка Authorization
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split("Bearer ")[1]
    # Проверяем токен из cookie
    token = request.cookies.get("access_token")
    if token:
        return token
    raise HTTPException(status_code=401, detail="Токен не найден")

async def admin_required(token: str = Depends(get_token)):
    try:
        print(f"Verifying token: {token[:10]}...")
        payload = verify_token(token, SECRET_KEY)
        print(f"Token payload: {payload}")
        username: str = payload.get("sub")
        is_admin: bool = payload.get("is_admin", False)
        if username is None or not is_admin:
            print(f"Invalid admin status: username={username}, is_admin={is_admin}")
            raise HTTPException(status_code=403, detail="Требуются права администратора")
        return {"username": username, "is_admin": is_admin}
    except JWTError as e:
        print(f"JWT Error: {str(e)}")
        raise HTTPException(status_code=401, detail="Неверный токен")
from typing import Optional

from fastapi import Request, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os
from passlib.context import CryptContext

# Конфигурация
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 схема для Swagger
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/token",
    scopes={"admin": "Admin access"}
)

# Для `security` в FastAPI
security = [{"bearerAuth": ["admin"]}]

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Неверный токен")

async def admin_required(request: Request, token: Optional[str] = Depends(oauth2_scheme)):
    # Проверяем наличие токена в заголовке Authorization или в cookies
    if not token:
        token = request.cookies.get("access_token")  # Пробуем взять из cookies

    if not token:
        print(f"No access token found in Authorization or cookies for {request.url}")
        raise HTTPException(status_code=401, detail="Не авторизован")

    try:
        print(f"Verifying token for {request.url}: {token[:10]}...")
        payload = verify_token(token, SECRET_KEY)
        print(f"Token payload: {payload}")

        username: str = payload.get("sub")
        is_admin: bool = payload.get("is_admin", False)

        if username is None or not is_admin:
            print(f"Invalid admin status: username={username}, is_admin={is_admin}")
            raise HTTPException(status_code=403, detail="Требуются права администратора")

        request.state.admin = {"username": username, "is_admin": is_admin}
        print(f"Admin check passed for {username}")
        return request.state.admin

    except JWTError as e:
        print(f"JWT Error: {str(e)}")
        raise HTTPException(status_code=401, detail="Неверный токен")

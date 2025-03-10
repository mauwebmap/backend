from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from jose import jwt, JWTError
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.users.models import Admin
from app.users.dependencies.auth import (
    create_token,
    set_auth_cookies,
    verify_password
)
from app.database.config.settings import settings

router = APIRouter(tags=["Authentication"])

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user_data: dict

@router.post("/token", response_model=TokenResponse)
async def login(response: Response, credentials: LoginRequest, db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.username == credentials.username).first()

    if not admin or not verify_password(credentials.password, admin.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверные учетные данные"
        )

    access_token = create_token({"sub": admin.username, "is_admin": admin.is_admin})
    refresh_token = create_token({"sub": admin.username}, is_refresh=True)

    set_auth_cookies(response, access_token, refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE),
        user_data={"username": admin.username, "is_admin": admin.is_admin}
    )

@router.post("/auth/refresh")
async def refresh_token(request: Request, response: Response, db: Session = Depends(get_db)):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Отсутствует refresh token")

    try:
        payload = jwt.decode(refresh_token, settings.REFRESH_SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Неверный тип токена")

        admin = db.query(Admin).filter(Admin.username == payload.get("sub")).first()
        if not admin:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        new_access = create_token({"sub": admin.username, "is_admin": admin.is_admin})
        set_auth_cookies(response, new_access, refresh_token)

        return {"access_token": new_access, "token_type": "bearer"}
    except JWTError:
        raise HTTPException(status_code=401, detail="Недействительный refresh token")

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Response
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

    # Создаем токены
    access_token = create_token({"sub": admin.username, "is_admin": admin.is_admin})
    refresh_token = create_token({"sub": admin.username}, is_refresh=True)

    # Устанавливаем куки
    set_auth_cookies(response, access_token, refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE),
        user_data={"username": admin.username, "is_admin": admin.is_admin}
    )
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
    verify_password,
    admin_required
)
from app.database.config.settings import settings

from app.api.endpoints.base import logger

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


class ErrorResponse(BaseModel):
    detail: str
    error_type: str


@router.post("/token")
async def login(
        response: Response,
        credentials: LoginRequest,
        db: Session = Depends(get_db)
):
    try:
        logger.info(f"Login attempt for user: {credentials.username}")

        admin = db.query(Admin).filter(
            Admin.username == credentials.username
        ).first()

        if not admin:
            logger.warning(f"User not found: {credentials.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"detail": "Неверные учетные данные", "error_type": "AUTH_ERROR"}
            )

        if not verify_password(credentials.password, admin.hashed_password):
            logger.warning(f"Invalid password for user: {credentials.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"detail": "Неверные учетные данные", "error_type": "AUTH_ERROR"}
            )

        access_token = create_token({
            "sub": admin.username,
            "is_admin": admin.is_admin
        })

        refresh_token = create_token({
            "sub": admin.username
        }, is_refresh=True)

        set_auth_cookies(response, access_token, refresh_token)

        logger.info(f"Successful login for user: {credentials.username}")

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_at": datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE),
            "user_data": {
                "username": admin.username,
                "is_admin": admin.is_admin
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Внутренняя ошибка сервера", "error_type": "SERVER_ERROR"}
        )

@router.post("/auth/refresh")
async def refresh_token(
        request: Request,
        response: Response,
        db: Session = Depends(get_db)
):
    try:
        refresh_token = request.cookies.get("refresh_token")
        if not refresh_token:
            raise HTTPException(status_code=401, detail="Отсутствует refresh token")

        payload = jwt.decode(
            refresh_token,
            settings.REFRESH_SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Неверный тип токена")

        admin = db.query(Admin).filter(
            Admin.username == payload.get("sub")
        ).first()

        if not admin:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        new_access = create_token({
            "sub": admin.username,
            "is_admin": admin.is_admin
        })

        response.set_cookie(
            key="access_token",
            value=new_access,
            httponly=True,
            max_age=settings.ACCESS_TOKEN_EXPIRE * 60,
            **settings.COOKIE_CONFIG
        )

        return {
            "access_token": new_access,
            "token_type": "bearer",
            "expires_at": datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE),
            "user_data": {
                "username": admin.username,
                "is_admin": admin.is_admin
            }
        }

    except JWTError:
        raise HTTPException(status_code=401, detail="Недействительный refresh token")
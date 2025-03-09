from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from typing import Optional
from app.users.dependencies.auth import (
    create_access_token,
    create_refresh_token,
    verify_password,
    verify_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    REFRESH_SECRET_KEY
)
from app.users.models import Admin
from app.database.database import get_db
from sqlalchemy.orm import Session

router = APIRouter(tags=["Authentication"])

# Модели запросов
class LoginData(BaseModel):
    username: str = Field(..., example="admin")
    password: str = Field(..., example="password123")

class RefreshData(BaseModel):
    refresh_token: str = Field(..., example="")

# Модели ответов
class TokenResponse(BaseModel):
    access_token: str = Field(
        default="",
        example="",
        description="JWT токен для доступа к защищенным ресурсам"
    )
    refresh_token: Optional[str] = Field(
        default="",
        example="",
        description="Токен для обновления access token (только для /token)"
    )
    token_type: str = Field(
        default="bearer",
        example="bearer",
        description="Тип токена"
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        example="2024-01-01T00:00:00Z",
        description="Время истечения токена"
    )
    user_data: Optional[dict] = Field(
        default={},
        example={"username": "admin", "is_admin": True},
        description="Данные пользователя"
    )

class ErrorResponse(BaseModel):
    detail: str = Field(..., example="Ошибка аутентификации")
    error_type: str = Field(..., example="AUTH_ERROR")

# Примеры для Swagger
SWAGGER_LOGIN_RESPONSE = {
    "example": {
        "access_token": "",
        "refresh_token": "",
        "token_type": "bearer",
        "expires_at": "2024-01-01T00:00:00Z",
        "user_data": {"username": "", "is_admin": False}
    }
}

SWAGGER_REFRESH_RESPONSE = {
    "example": {
        "access_token": "",
        "token_type": "bearer",
        "expires_at": "2024-01-01T00:00:00Z",
        "user_data": {"username": "", "is_admin": False}
    }
}

ERROR_EXAMPLES = {
    "invalid_credentials": {
        "summary": "Неверные учетные данные",
        "value": {"detail": "Неверное имя пользователя или пароль", "error_type": "AUTH_ERROR"}
    },
    "invalid_token": {
        "summary": "Неверный токен",
        "value": {"detail": "Недействительный токен", "error_type": "AUTH_ERROR"}
    },
    "server_error": {
        "summary": "Ошибка сервера",
        "value": {"detail": "Внутренняя ошибка сервера", "error_type": "SERVER_ERROR"}
    }
}

@router.post(
    "/token",
    response_model=TokenResponse,
    responses={
        200: {"content": {"application/json": {"examples": SWAGGER_LOGIN_RESPONSE}}},
        401: {"model": ErrorResponse, "content": {"application/json": {"examples": ERROR_EXAMPLES}}},
        500: {"model": ErrorResponse}
    }
)
async def login(
    response: Response,
    login_data: LoginData,
    db: Session = Depends(get_db)
):
    try:
        admin = db.query(Admin).filter(Admin.username == login_data.username).first()

        if not admin or not verify_password(login_data.password, admin.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"detail": "Неверное имя пользователя или пароль", "error_type": "AUTH_ERROR"}
            )

        access_token = create_access_token(data={"sub": admin.username, "is_admin": True})
        refresh_token = create_refresh_token(data={"sub": admin.username, "is_admin": True})
        expires_at = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_at": expires_at,
            "user_data": {
                "username": admin.username,
                "is_admin": admin.is_admin
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Внутренняя ошибка сервера", "error_type": "SERVER_ERROR"}
        )

@router.post(
    "/refresh",
    response_model=TokenResponse,
    responses={
        200: {"content": {"application/json": {"examples": SWAGGER_REFRESH_RESPONSE}}},
        401: {"model": ErrorResponse, "content": {"application/json": {"examples": ERROR_EXAMPLES}}},
        500: {"model": ErrorResponse}
    }
)
async def refresh_token(
    response: Response,
    refresh_data: RefreshData,
    db: Session = Depends(get_db)
):
    try:
        payload = verify_token(refresh_data.refresh_token, REFRESH_SECRET_KEY)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"detail": "Неверный refresh токен", "error_type": "AUTH_ERROR"}
            )

        admin = db.query(Admin).filter(Admin.username == payload.get("sub")).first()
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"detail": "Пользователь не найден", "error_type": "AUTH_ERROR"}
            )

        new_access_token = create_access_token(data={"sub": admin.username, "is_admin": True})
        expires_at = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        response.set_cookie(
            key="access_token",
            value=new_access_token,
            httponly=True,
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

        return {
            "access_token": new_access_token,
            "token_type": "bearer",
            "expires_at": expires_at,
            "user_data": {
                "username": admin.username,
                "is_admin": admin.is_admin
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Внутренняя ошибка сервера", "error_type": "SERVER_ERROR"}
        )
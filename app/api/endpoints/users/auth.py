from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel
from app.users.dependencies.auth import create_access_token, create_refresh_token, verify_password, verify_token,ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS, REFRESH_SECRET_KEY
from app.users.models import Admin
from app.database.database import get_db
from sqlalchemy.orm import Session

router = APIRouter(tags=["Authentication"])

class LoginData(BaseModel):
    username: str
    password: str

class RefreshData(BaseModel):
    refresh_token: str

@router.post("/token")
async def login(
    response: Response,
    login_data: LoginData,  # Принимаем JSON
    db: Session = Depends(get_db)
):
    try:
        print(f"Attempting login for username: {login_data.username}")
        admin = db.query(Admin).filter(Admin.username == login_data.username).first()

        if not admin:
            print("Admin not found")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password"
            )

        if not verify_password(login_data.password, admin.hashed_password):
            print("Password mismatch")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password"
            )

        access_token = create_access_token(data={"sub": login_data.username, "is_admin": True, "scope": "admin"})
        refresh_token = create_refresh_token(data={"sub": login_data.username, "is_admin": True})
        print(f"Generated access token: {access_token}")
        print(f"Generated refresh token: {refresh_token}")

        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    except HTTPException as e:
        print(f"HTTP Exception in login: {str(e)}")
        raise
    except Exception as e:
        print(f"Unexpected error in login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/refresh")
async def refresh_token(
    response: Response,
    refresh_data: RefreshData,  # Принимаем JSON
    db: Session = Depends(get_db)
):
    try:
        print(f"Verifying refresh token: {refresh_data.refresh_token[:10]}...")
        payload = verify_token(refresh_data.refresh_token, REFRESH_SECRET_KEY)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Неверный refresh токен")

        username: str = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Неверные данные токена")

        admin = db.query(Admin).filter(Admin.username == username).first()
        if not admin:
            raise HTTPException(status_code=401, detail="Пользователь не найден")

        new_access_token = create_access_token(data={"sub": username, "is_admin": True, "scope": "admin"})
        print(f"Generated new access token: {new_access_token}")

        response.set_cookie(
            key="access_token",
            value=new_access_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

        return {"access_token": new_access_token, "token_type": "bearer"}
    except HTTPException as e:
        print(f"HTTP Exception in refresh: {str(e)}")
        raise
    except Exception as e:
        print(f"Unexpected error in refresh: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
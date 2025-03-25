from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, Form, File, Request, Response
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.map.schemas.campus import CampusResponse
from app.map.crud.campus import get_all_campuses, get_campus, create_campus, update_campus, delete_campus
from app.users.dependencies.auth import admin_required

router = APIRouter(prefix="/campuses", tags=["Campuses"])


@router.get("/", response_model=List[CampusResponse])
def read_campuses(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Получить список всех кампусов. Без авторизации."""
    return get_all_campuses(db, skip, limit)


@router.get("/{campus_id}", response_model=CampusResponse)
def read_campus(
    campus_id: int,
    db: Session = Depends(get_db)
):
    """Получить информацию о кампусе по ID. Без авторизации."""
    campus = get_campus(db, campus_id)
    if not campus:
        raise HTTPException(status_code=404, detail="Campus not found")
    return campus


@router.post("/", response_model=CampusResponse, dependencies=[Depends(admin_required)])
async def create_campus_endpoint(
    request: Request,
    response: Response,
    name: str = Form(..., description="Название кампуса"),
    description: Optional[str] = Form(None, description="Описание кампуса"),
    svg_file: Optional[UploadFile] = File(None, description="SVG-файл кампуса"),
    db: Session = Depends(get_db)
):
    """Создать новый кампус. Требуются права администратора."""
    try:
        return await create_campus(db, name, description, svg_file)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при создании кампуса: {str(e)}")


@router.put("/{campus_id}", response_model=CampusResponse, dependencies=[Depends(admin_required)])
async def update_campus_endpoint(
    campus_id: int,
    request: Request,
    response: Response,
    name: Optional[str] = Form(None, description="Новое название кампуса"),
    description: Optional[str] = Form(None, description="Новое описание кампуса"),
    svg_file: Optional[UploadFile] = File(None, description="Новый SVG-файл кампуса"),
    db: Session = Depends(get_db)
):
    """Обновить информацию о кампусе. Требуются права администратора."""
    try:
        update_data = {
            key: value for key, value in {
                "name": name,
                "description": description
            }.items() if value is not None
        }
        return await update_campus(db, campus_id, update_data, svg_file)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при обновлении кампуса: {str(e)}")


@router.delete("/{campus_id}", response_model=CampusResponse, dependencies=[Depends(admin_required)])
def delete_campus_endpoint(
    campus_id: int,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """Удалить кампус по ID. Требуются права администратора."""
    try:
        return delete_campus(db, campus_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при удалении кампуса: {str(e)}")
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, Form, File, Request, Response
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.map.schemas.building import BuildingResponse
from app.map.crud.building import (
    get_all_buildings,
    get_building,
    create_building,
    update_building,
    delete_building
)
from app.users.dependencies.auth import admin_required

router = APIRouter(prefix="/buildings", tags=["Buildings"])

@router.get("/", response_model=List[BuildingResponse])
def read_buildings(
    campus_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Получить список всех зданий, опционально отфильтрованных по campus_id. Без авторизации."""
    return get_all_buildings(db, campus_id=campus_id, skip=skip, limit=limit)

@router.get("/{building_id}", response_model=BuildingResponse)
def read_building(
    building_id: int,
    db: Session = Depends(get_db)
):
    """Получить информацию о здании по ID. Без авторизации."""
    building = get_building(db, building_id)
    if not building:
        raise HTTPException(status_code=404, detail="Building not found")
    return building

@router.post("/", response_model=BuildingResponse)
async def create_building_endpoint(
    request: Request,
    response: Response,
    campus_id: int = Form(..., description="ID кампуса, к которому относится здание"),
    name: str = Form(..., description="Название здания"),
    x: float = Form(..., description="Координата X входа"),
    y: float = Form(..., description="Координата Y входа"),
    description: Optional[str] = Form(None, description="Описание здания"),
    svg_file: Optional[UploadFile] = File(None, description="SVG-файл здания"),
    db: Session = Depends(get_db),
    new_access_token: Optional[str] = Depends(admin_required)
):
    """Создать новое здание в указанном кампусе. Требуются права администратора."""
    try:
        building_data = {
            "campus_id": campus_id,
            "name": name,
            "x": x,
            "y": y,
            "description": description
        }
        result = await create_building(db, building_data, svg_file)
        if new_access_token:
            response.headers["X-New-Access-Token"] = new_access_token
        return result
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при создании здания: {str(e)}")

@router.put("/{building_id}", response_model=BuildingResponse)
async def update_building_endpoint(
    building_id: int,
    request: Request,
    response: Response,
    campus_id: Optional[int] = Form(None, description="Новый ID кампуса"),
    name: Optional[str] = Form(None, description="Новое название здания"),
    description: Optional[str] = Form(None, description="Новое описание здания"),
    svg_file: Optional[UploadFile] = File(None, description="Новый SVG-файл здания"),
    db: Session = Depends(get_db),
    new_access_token: Optional[str] = Depends(admin_required)
):
    """Обновить информацию о здании. Требуются права администратора."""
    try:
        update_data = {
            key: value for key, value in {
                "campus_id": campus_id,
                "name": name,
                "description": description
            }.items() if value is not None
        }
        updated_building = await update_building(db, building_id, update_data, svg_file)
        if not updated_building:
            raise HTTPException(status_code=404, detail="Building not found")
        if new_access_token:
            response.headers["X-New-Access-Token"] = new_access_token
        return updated_building
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при обновлении здания: {str(e)}")

@router.delete("/{building_id}", response_model=BuildingResponse)
def delete_building_endpoint(
    building_id: int,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    new_access_token: Optional[str] = Depends(admin_required)
):
    """Удалить здание по ID. Требуются права администратора."""
    try:
        deleted_building = delete_building(db, building_id)
        if not deleted_building:
            raise HTTPException(status_code=404, detail="Building not found")
        if new_access_token:
            response.headers["X-New-Access-Token"] = new_access_token
        return deleted_building
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при удалении здания: {str(e)}")
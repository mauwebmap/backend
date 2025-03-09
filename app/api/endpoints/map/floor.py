from fastapi import Depends, Form, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from app.database.database import get_db
from app.map.schemas.floor import FloorResponse
from app.map.crud.floor import (
    get_all_floors,
    get_floor,
    create_floor,
    update_floor,
    delete_floor
)
from app.users.dependencies.auth import admin_required
from app.api.endpoints.base import SecureRouter, ProtectedMethodsRoute

router = SecureRouter(
    version=2,
    prefix="/floors",
    tags=["Floors"],
    route_class=ProtectedMethodsRoute,
    default_dependencies=[Depends(admin_required)]
)

@router.get("/", response_model=list[FloorResponse])
def read_floors(
    building_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Получить список всех этажей, опционально отфильтрованных по building_id.
    """
    return get_all_floors(db, building_id=building_id, skip=skip, limit=limit)

@router.get("/{floor_id}", response_model=FloorResponse)
def read_floor(
    floor_id: int,
    db: Session = Depends(get_db)
):
    """
    Получить информацию об этаже по его ID.
    """
    floor = get_floor(db, floor_id)
    if not floor:
        raise HTTPException(status_code=404, detail="Floor not found")
    return floor

@router.post("/", response_model=FloorResponse)
async def create_floor_endpoint(
    building_id: int = Form(...),
    level: int = Form(...),
    description: Optional[str] = Form(None),
    svg_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """
    Создать новый этаж в указанном здании.
    Требуются права администратора.
    """
    try:
        return await create_floor(db, building_id, level, description, svg_file)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put("/{floor_id}", response_model=FloorResponse)
async def update_floor_endpoint(
    floor_id: int,
    building_id: Optional[int] = Form(None),
    level: Optional[int] = Form(None),
    description: Optional[str] = Form(None),
    svg_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """
    Обновить информацию об этаже.
    Требуются права администратора.
    """
    update_data = {}
    if building_id is not None:
        update_data["building_id"] = building_id
    if level is not None:
        update_data["level"] = level
    if description is not None:
        update_data["description"] = description
    file_to_process = svg_file if svg_file and svg_file.filename else None
    try:
        updated_floor = await update_floor(db, floor_id, update_data, file_to_process)
        if not updated_floor:
            raise HTTPException(status_code=404, detail="Floor not found")
        return updated_floor
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete("/{floor_id}", response_model=FloorResponse)
def delete_floor_endpoint(
    floor_id: int,
    db: Session = Depends(get_db)
):
    """
    Удалить этаж по его ID.
    Требуются права администратора.
    """
    deleted_floor = delete_floor(db, floor_id)
    if not deleted_floor:
        raise HTTPException(status_code=404, detail="Floor not found")
    return deleted_floor
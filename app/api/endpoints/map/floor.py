from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.map.crud.floor import (
    get_floor,
    get_all_floors,
    create_floor_with_connections,
    update_floor,
    delete_floor
)
from app.map.schemas.floor import FloorCreate, FloorResponse
from app.database.database import get_db
from app.users.dependencies.auth import admin_required

router = APIRouter(prefix="/floors", tags=["Floors"])

# Получить список всех этажей
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

# Получить этаж по ID
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

# Создать этаж
@router.post("/", response_model=FloorResponse, dependencies=[Depends(admin_required)])
def create_floor_endpoint(
    floor_data: FloorCreate,
    db: Session = Depends(get_db)
):
    """
    Создать новый этаж с возможными соединениями.
    Требуются права администратора.
    """
    try:
        return create_floor_with_connections(db, floor_data)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при создании этажа: {str(e)}"
        )

# Обновить этаж
@router.put("/{floor_id}", response_model=FloorResponse, dependencies=[Depends(admin_required)])
def update_floor_endpoint(
    floor_id: int,
    floor_data: FloorCreate,
    db: Session = Depends(get_db)
):
    """
    Обновить информацию об этаже.
    Требуются права администратора.
    """
    try:
        return update_floor(db, floor_id, floor_data)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при обновлении этажа: {str(e)}"
        )

# Удалить этаж
@router.delete("/{floor_id}", response_model=FloorResponse, dependencies=[Depends(admin_required)])
def delete_floor_endpoint(
    floor_id: int,
    db: Session = Depends(get_db)
):
    """
    Удалить этаж по его ID.
    Требуются права администратора.
    """
    try:
        return delete_floor(db, floor_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER
        )
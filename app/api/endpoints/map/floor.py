from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, Form, File
from sqlalchemy.orm import Session
from app.map.crud.floor import (
    get_floor,
    get_all_floors,
    create_floor_with_connections,
    update_floor,
    delete_floor,
    get_unique_floor_numbers_by_campus,
    get_floors_by_campus_and_number
)
from app.map.schemas.floor import FloorResponse, FloorNumbersResponse
from app.database.database import get_db
from app.users.dependencies.auth import admin_required

router = APIRouter(prefix="/floors", tags=["Floors"])


@router.get("/", response_model=List[FloorResponse])
def read_floors(
    building_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Получить список всех этажей.
    Можно фильтровать по building_id.
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


@router.get("/campus/{campus_id}/floor-numbers", response_model=FloorNumbersResponse)
def read_unique_floor_numbers_by_campus(
    campus_id: int,
    db: Session = Depends(get_db),
):
    """
    Получить уникальные номера этажей в выбранном кампусе.
    """
    floor_numbers = get_unique_floor_numbers_by_campus(db, campus_id)
    if not floor_numbers:
        raise HTTPException(status_code=404, detail="No floors found for this campus")
    return {"floor_numbers": floor_numbers}


@router.get("/campus/{campus_id}/floors/{floor_number}", response_model=List[FloorResponse])
def read_floors_by_campus_and_number(
    campus_id: int,
    floor_number: int,
    db: Session = Depends(get_db),
):
    """
    Получить все этажи с указанным номером, принадлежащие указанному кампусу.
    """
    floors = get_floors_by_campus_and_number(db, campus_id, floor_number)
    if not floors:
        raise HTTPException(status_code=404, detail="No floors found for the given campus and number")
    return floors


@router.post("/", response_model=FloorResponse, dependencies=[Depends(admin_required)])
async def create_floor_endpoint(
    building_id: int = Form(..., description="ID здания, к которому относится этаж"),
    floor_number: int = Form(..., description="Номер этажа"),
    description: Optional[str] = Form(None, description="Описание этажа"),
    svg_file: Optional[UploadFile] = File(None, description="SVG-файл этажа"),
    db: Session = Depends(get_db)
):
    """
    Создать новый этаж.
    Требуются права администратора.
    """
    try:
        # Вызываем CRUD-функцию для создания этажа
        return await create_floor_with_connections(
            db=db,
            floor_data={
                "building_id": building_id,
                "floor_number": floor_number,
                "description": description,
                "connections": []  # Пустой список соединений, если они не передаются
            },
            svg_file=svg_file
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при создании этажа: {str(e)}"
        )


@router.put("/{floor_id}", response_model=FloorResponse, dependencies=[Depends(admin_required)])
async def update_floor_endpoint(
    floor_id: int,
    building_id: Optional[int] = Form(None, description="ID здания, к которому относится этаж"),
    floor_number: Optional[int] = Form(None, description="Номер этажа"),
    description: Optional[str] = Form(None, description="Описание этажа"),
    svg_file: Optional[UploadFile] = File(None, description="SVG-файл этажа"),
    db: Session = Depends(get_db)
):
    """
    Обновить информацию об этаже.
    Требуются права администратора.
    """
    try:
        # Собираем данные для обновления
        update_data = {}
        if building_id is not None:
            update_data["building_id"] = building_id
        if floor_number is not None:
            update_data["floor_number"] = floor_number
        if description is not None:
            update_data["description"] = description

        # Вызываем CRUD-функцию для обновления этажа
        return update_floor(
            db=db,
            floor_id=floor_id,
            floor_data=update_data,
            svg_file=svg_file
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при обновлении этажа: {str(e)}"
        )


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
        # Вызываем CRUD-функцию для удаления этажа
        return delete_floor(db, floor_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при удалении этажа: {str(e)}"
        )
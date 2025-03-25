from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, Form, File
from sqlalchemy.orm import Session
from app.map.crud.room import (
    get_room,
    get_rooms,
    create_room_with_connections,
    update_room_with_connections,
    delete_room,
    get_rooms_by_floor_and_campus
)
from app.map.schemas.room import RoomResponse
from app.database.database import get_db
from app.users.dependencies.auth import admin_required

router = APIRouter(prefix="/rooms", tags=["Rooms"])


@router.get("/", response_model=List[RoomResponse])
def read_rooms(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Получить список всех комнат.
    """
    return get_rooms(db, skip=skip, limit=limit)


@router.get("/{room_id}", response_model=RoomResponse)
def read_room(
    room_id: int,
    db: Session = Depends(get_db)
):
    """
    Получить информацию о комнате по её ID.
    """
    room = get_room(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room

@router.get("/campus/{campus_id}/floors/{floor_id}/rooms", response_model=List[RoomResponse])
def read_rooms_by_floor_and_campus(
    campus_id: int,
    floor_id: int,
    db: Session = Depends(get_db),
):
    """
    Получить все комнаты на указанном этаже, принадлежащем указанному кампусу.
    """
    rooms = get_rooms_by_floor_and_campus(db, floor_id, campus_id)
    if not rooms:
        raise HTTPException(status_code=404, detail="No rooms found for the given floor and campus")
    return rooms


@router.post("/", response_model=RoomResponse, dependencies=[Depends(admin_required)])
async def create_room_endpoint(
    building_id: int = Form(..., description="ID здания, к которому относится комната"),
    floor_id: int = Form(..., description="ID этажа, к которому относится комната"),
    name: str = Form(..., description="Название комнаты"),
    cab_id: str = Form(..., description="Кабинетный номер"),
    description: Optional[str] = Form(None, description="Описание комнаты"),
    image_file: Optional[UploadFile] = File(None, description="Изображение комнаты"),
    db: Session = Depends(get_db)
):
    """
    Создать новую комнату.
    Требуются права администратора.
    """
    try:
        # Собираем данные для создания комнаты
        room_data = {
            "building_id": building_id,
            "floor_id": floor_id,
            "name": name,
            "cab_id": cab_id,
            "description": description,
            "connections": []  # Пустой список соединений, если они не передаются
        }

        # Вызываем CRUD-функцию для создания комнаты
        return await create_room_with_connections(
            db=db,
            room_data=room_data,
            image_file=image_file
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при создании комнаты: {str(e)}"
        )


@router.put("/{room_id}", response_model=RoomResponse, dependencies=[Depends(admin_required)])
async def update_room_endpoint(
    room_id: int,
    building_id: Optional[int] = Form(None, description="ID здания, к которому относится комната"),
    floor_id: Optional[int] = Form(None, description="ID этажа, к которому относится комната"),
    name: Optional[str] = Form(None, description="Название комнаты"),
    cab_id: Optional[str] = Form(None, description="Кабинетный номер"),
    description: Optional[str] = Form(None, description="Описание комнаты"),
    image_file: Optional[UploadFile] = File(None, description="Изображение комнаты"),
    db: Session = Depends(get_db)
):
    """
    Обновить информацию о комнате.
    Требуются права администратора.
    """
    try:
        # Собираем данные для обновления
        update_data = {}
        if building_id is not None:
            update_data["building_id"] = building_id
        if floor_id is not None:
            update_data["floor_id"] = floor_id
        if name is not None:
            update_data["name"] = name
        if cab_id is not None:
            update_data["cab_id"] = cab_id
        if description is not None:
            update_data["description"] = description

        # Вызываем CRUD-функцию для обновления комнаты
        return await update_room_with_connections(
            db=db,
            room_id=room_id,
            room_data=update_data,
            image_file=image_file
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при обновлении комнаты: {str(e)}"
        )


@router.delete("/{room_id}", response_model=RoomResponse, dependencies=[Depends(admin_required)])
def delete_room_endpoint(
    room_id: int,
    db: Session = Depends(get_db)
):
    """
    Удалить комнату по её ID.
    Требуются права администратора.
    """
    try:
        # Вызываем CRUD-функцию для удаления комнаты
        return delete_room(db, room_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при удалении комнаты: {str(e)}"
        )
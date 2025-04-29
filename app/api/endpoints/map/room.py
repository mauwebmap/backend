from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, Form, File, Request, Response
from sqlalchemy.orm import Session
from app.map.crud.room import (
    get_room,
    get_rooms,
    create_room,
    update_room,
    delete_room,
    get_rooms_by_floor_and_campus,
    search_rooms_by_name_or_cab_id
)
from app.map.crud.connection import create_connection
from app.map.schemas.room import RoomResponse, RoomCreate, RoomUpdate, Coordinates, RoomSearchResponse
from app.map.schemas.connection import ConnectionCreate
from app.database.database import get_db
from app.users.dependencies.auth import admin_required
import json
from app.map.models.building import Building

router = APIRouter(prefix="/rooms", tags=["Rooms"])

@router.get("/", response_model=List[RoomResponse])
def read_rooms(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Получить список всех комнат. Без авторизации."""
    return get_rooms(db, skip=skip, limit=limit)

@router.get("/search", response_model=List[RoomSearchResponse])
def search_rooms(
    query: str,
    campus_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Поиск комнат по названию (name) или номеру кабинета (cab_id) с учётом кампуса.
    Возвращает список комнат с названием здания.
    Без авторизации.
    """
    try:
        if not query:
            raise HTTPException(status_code=400, detail="Параметр query не может быть пустым")

        # Выполняем поиск
        rooms = search_rooms_by_name_or_cab_id(db, query, campus_id)

        if not rooms:
            return []

        # Формируем ответ с названием здания
        result = []
        for room in rooms:
            # Получаем название здания
            building = db.query(Building).filter(Building.id == room.building_id).first()
            building_name = building.name if building else "Неизвестное здание"

            room_response = RoomSearchResponse(
                id=room.id,
                name=room.name,
                cab_id=room.cab_id,
                building_id=room.building_id,
                building_name=building_name,
                floor_id=room.floor_id,
                cab_x=room.cab_x,
                cab_y=room.cab_y,
                description=room.description,
                image_path=room.image_path
            )
            result.append(room_response)

        return result
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при поиске комнат: {str(e)}")

@router.get("/{room_id}", response_model=RoomResponse)
def read_room(
    room_id: int,
    db: Session = Depends(get_db)
):
    """Получить информацию о комнате по ID. Без авторизации."""
    room = get_room(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room

@router.get("/campus/{campus_id}/floors/{floor_id}/rooms", response_model=List[RoomResponse])
def read_rooms_by_floor_and_campus(
    campus_id: int,
    floor_id: int,
    db: Session = Depends(get_db)
):
    """Получить все комнаты на указанном этаже в кампусе. Без авторизации."""
    rooms = get_rooms_by_floor_and_campus(db, floor_id, campus_id)
    if not rooms:
        raise HTTPException(status_code=404, detail="No rooms found for the given floor and campus")
    return rooms

@router.post("/", response_model=RoomResponse)
async def create_room_endpoint(
    request: Request,
    response: Response,
    building_id: int = Form(..., description="ID здания, к которому относится комната"),
    floor_id: int = Form(..., description="ID этажа, к которому относится комната"),
    name: str = Form(..., description="Название комнаты"),
    cab_id: str = Form(..., description="Кабинетный номер"),
    cab_x: Optional[float] = Form(None, description="Координата X входа в кабинет"),
    cab_y: Optional[float] = Form(None, description="Координата Y входа в кабинет"),
    description: Optional[str] = Form(None, description="Описание комнаты"),
    coordinates: Optional[str] = Form(None, description="Координаты комнаты (JSON-строка, [{'x': float, 'y': float}]"),
    connections: Optional[str] = Form(None, description="Список соединений (JSON-строка, [{'type': str, 'weight': float, 'segment_id': int}]"),
    image_file: Optional[UploadFile] = File(None, description="Изображение комнаты"),
    db: Session = Depends(get_db),
    new_access_token: Optional[str] = Depends(admin_required)
):
    """Создать новую комнату и опционально связать её с другими объектами. Требуются права администратора."""
    try:
        # Парсим coordinates из JSON-строки
        coordinates_list = [Coordinates(**coord) for coord in json.loads(coordinates)] if coordinates else None

        # Формируем объект RoomCreate
        room_data = RoomCreate(
            building_id=building_id,
            floor_id=floor_id,
            name=name,
            cab_id=cab_id,
            cab_x=cab_x,
            cab_y=cab_y,
            description=description,
            coordinates=coordinates_list,
            connections=[ConnectionCreate(**conn) for conn in json.loads(connections)] if connections else []
        )
        # Создаём комнату
        room = await create_room(db=db, room_data=room_data, image_file=image_file)
        if new_access_token:
            response.headers["X-New-Access-Token"] = new_access_token
        return room
    except ValueError as e:  # Ошибка валидации JSON или Pydantic
        raise HTTPException(status_code=400, detail=f"Неверный формат данных: {str(e)}")
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при создании комнаты: {str(e)}")

@router.put("/{room_id}", response_model=RoomResponse)
async def update_room_endpoint(
    room_id: int,
    request: Request,
    response: Response,
    building_id: Optional[int] = Form(None, description="Новый ID здания"),
    floor_id: Optional[int] = Form(None, description="Новый ID этажа"),
    name: Optional[str] = Form(None, description="Новое название комнаты"),
    cab_id: Optional[str] = Form(None, description="Новый кабинетный номер"),
    cab_x: Optional[float] = Form(None, description="Новая координата X входа"),
    cab_y: Optional[float] = Form(None, description="Новая координата Y входа"),
    description: Optional[str] = Form(None, description="Новое описание комнаты"),
    coordinates: Optional[str] = Form(None, description="Координаты комнаты (JSON-строка, [{'x': float, 'y': float}]"),
    connections: Optional[str] = Form(None, description="Список соединений (JSON-строка, [{'type': str, 'weight': float, 'segment_id': int}]"),
    image_file: Optional[UploadFile] = File(None, description="Новое изображение комнаты"),
    db: Session = Depends(get_db),
    new_access_token: Optional[str] = Depends(admin_required)
):
    """Обновить информацию о комнате. Требуются права администратора."""
    try:
        coordinates_list = [Coordinates(**coord) for coord in json.loads(coordinates)] if coordinates else None
        update_data = RoomUpdate(
            building_id=building_id,
            floor_id=floor_id,
            name=name,
            cab_id=cab_id,
            cab_x=cab_x,
            cab_y=cab_y,
            description=description,
            coordinates=coordinates_list,
            connections=[ConnectionCreate(**conn) for conn in json.loads(connections)] if connections else None
        )
        updated_room = await update_room(db=db, room_id=room_id, room_data=update_data, image_file=image_file)
        if not updated_room:
            raise HTTPException(status_code=404, detail="Room not found")
        if new_access_token:
            response.headers["X-New-Access-Token"] = new_access_token
        return updated_room
    except ValueError as e:  # Ошибка валидации JSON или Pydantic
        raise HTTPException(status_code=400, detail=f"Неверный формат данных: {str(e)}")
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при обновлении комнаты: {str(e)}")

@router.delete("/{room_id}", response_model=RoomResponse)
def delete_room_endpoint(
    room_id: int,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    new_access_token: Optional[str] = Depends(admin_required)
):
    """Удалить комнату. Требуются права администратора."""
    try:
        deleted_room = delete_room(db, room_id)
        if not deleted_room:
            raise HTTPException(status_code=404, detail="Room not found")
        if new_access_token:
            response.headers["X-New-Access-Token"] = new_access_token
        return deleted_room
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при удалении комнаты: {str(e)}")
import os
from typing import Optional, List
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_ , select
from app.map.models.room import Room
from app.map.models.building import Building
from app.map.models.floor import Floor
from app.map.schemas.room import RoomCreate, RoomUpdate
from app.map.models.connection import Connection
import mimetypes

ROOM_IMAGE_DIR = "static/images/rooms"
os.makedirs(ROOM_IMAGE_DIR, exist_ok=True)

def is_image_file(file: UploadFile):
    mime_type, _ = mimetypes.guess_type(file.filename)
    return mime_type and mime_type.startswith("image/")


def get_room(db: Session, room_id: int):
    try:
        # Выполняем SELECT с JOIN для получения floor_number
        query = (
            select(Room, Floor.floor_number)
            .join(Floor, Floor.id == Room.floor_id)
            .filter(Room.id == room_id)
        )
        result = db.execute(query).first()
        if not result:
            return None

        # Извлекаем объект Room и floor_number
        room, floor_number = result
        # Добавляем floor_number к объекту Room
        room.floor_number = floor_number
        return room
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении комнаты: {str(e)}")

def get_rooms(db: Session, skip: int = 0, limit: int = 100):
    try:
        # Выполняем JOIN таблиц rooms и floors
        query = (
            select(Room, Floor.floor_number)
            .join(Floor, Room.floor_id == Floor.id)
            .offset(skip)
            .limit(limit)
        )
        result = db.execute(query).all()
        # Формируем список объектов Room с добавленным floor_number
        rooms = [row[0] for row in result]
        for room, floor_number in result:
            room.floor_number = floor_number  # Добавляем floor_number к объекту Room
        return rooms
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении комнат: {str(e)}")

def get_rooms_by_floor_and_campus(db: Session, floor_number: int, campus_id: int):
    try:
        # Выполняем JOIN таблиц rooms, floors и buildings
        query = (
            select(Room, Floor.floor_number)
            .join(Floor, Floor.id == Room.floor_id)
            .join(Building, Building.id == Floor.building_id)
            .filter(Floor.floor_number == floor_number, Building.campus_id == campus_id)
        )
        result = db.execute(query).all()
        if not result:
            raise HTTPException(status_code=404, detail="Комнаты для указанного этажа и кампуса не найдены")
        # Формируем список объектов Room с добавленным floor_number
        rooms = [row[0] for row in result]
        for room, floor_number in result:
            room.floor_number = floor_number  # Добавляем floor_number к объекту Room
        return rooms
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении комнат: {str(e)}")

def search_rooms_by_name_or_cab_id(db: Session, query: str, campus_id: Optional[int] = None) -> List[Room]:
    """
    Ищет комнаты по названию (name) или номеру кабинета (cab_id) с учётом кампуса.
    Возвращает список комнат с JOIN на таблицы Floor и Building для получения номера этажа и имени здания.
    """
    try:
        # Разбиваем строку запроса на части (для поиска по словам)
        search_terms = query.strip().split()
        conditions = []

        # Формируем условия поиска: совпадение по name или cab_id
        for term in search_terms:
            term = f"%{term}%"  # Для частичного совпадения
            conditions.append(or_(
                Room.name.ilike(term),  # Поиск по имени (без учёта регистра)
                Room.cab_id.ilike(term)  # Поиск по номеру кабинета (без учёта регистра)
            ))

        # Формируем запрос с JOIN для получения floor_number и building_name
        query = (
            select(Room, Floor.floor_number, Building.name.label("building_name"))
            .join(Floor, Floor.id == Room.floor_id)
            .join(Building, Building.id == Floor.building_id)
        )

        # Добавляем фильтр по campus_id, если он указан
        if campus_id is not None:
            query = query.filter(Building.campus_id == campus_id)

        # Применяем условия поиска
        if conditions:
            query = query.filter(and_(*conditions))

        result = db.execute(query).all()
        if not result:
            return []

        # Формируем список объектов Room с добавленными floor_number и building_name
        rooms = [row[0] for row in result]
        for room, floor_number, building_name in result:
            room.floor_number = floor_number
            room.building_name = building_name

        return rooms
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при поиске комнат: {str(e)}")


async def create_room(db: Session, room_data: RoomCreate, image_file: Optional[UploadFile] = None):
    # Исключаем connections из словаря, так как это не поле модели Room
    room_dict = room_data.dict(exclude={"connections", "floor_number"})

    # Находим floor_id по building_id и floor_number
    floor = db.query(Floor).filter(
        Floor.building_id == room_data.building_id,
        Floor.floor_number == room_data.floor_number
    ).first()
    if not floor:
        raise HTTPException(status_code=400, detail="Этаж с указанным номером и зданием не найден")

    room_dict["floor_id"] = floor.id

    # Автоматическая генерация координат, если не переданы
    if not room_data.coordinates and room_data.cab_x is not None and room_data.cab_y is not None:
        cab_x = room_data.cab_x
        cab_y = room_data.cab_y
        room_dict["coordinates"] = [
            {"x": cab_x - 10, "y": cab_y - 10},  # Верхний левый
            {"x": cab_x + 10, "y": cab_y - 10},  # Верхний правый
            {"x": cab_x + 10, "y": cab_y + 10}, # Нижний правый
            {"x": cab_x - 10, "y": cab_y + 10}  # Нижний левый
        ]
    elif room_data.coordinates:
        room_dict["coordinates"] = [coord.dict() for coord in room_data.coordinates]

    # Обрабатываем image_file
    if image_file:
        if not is_image_file(image_file):
            raise HTTPException(status_code=400, detail="Файл должен быть изображением.")
        image_filename = f"room_{room_data.cab_id}_{image_file.filename}"
        image_path = os.path.join(ROOM_IMAGE_DIR, image_filename)
        os.makedirs(ROOM_IMAGE_DIR, exist_ok=True)
        with open(image_path, "wb") as buffer:
            content = image_file.file.read()  # Без await
            if not content:
                raise HTTPException(status_code=400, detail="Файл изображения пустой")
            buffer.write(content)
        room_dict["image_path"] = f"/{image_path}"

    # Создаем комнату
    db_room = Room(**room_dict)
    db.add(db_room)
    db.flush()

    # Обрабатываем connections
    if room_data.connections:
        for connection_data in room_data.connections:
            if connection_data.segment_id is not None:
                db_connection = Connection(
                    room_id=db_room.id,
                    segment_id=connection_data.segment_id,
                    type=connection_data.type.value,
                    weight=connection_data.weight
                )
                db.add(db_connection)
            else:
                raise HTTPException(status_code=400, detail="Соединения комнаты должны иметь segment_id")

    db.commit()
    db.refresh(db_room)

    # Добавляем floor_number к объекту для соответствия RoomResponse
    db_room.floor_number = floor.floor_number
    return db_room

async def update_room(db: Session, room_id: int, room_data: RoomUpdate, image_file: Optional[UploadFile] = None):
    db_room = db.query(Room).filter(Room.id == room_id).first()
    if not db_room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Обновляем только переданные поля комнаты
    update_data = room_data.dict(exclude_unset=True, exclude={"connections"})

    # Обрабатываем coordinates
    if room_data.coordinates is not None:
        update_data["coordinates"] = [coord.dict() for coord in room_data.coordinates] if room_data.coordinates else None

    # Обрабатываем image_file
    if image_file:
        if not is_image_file(image_file):
            raise HTTPException(status_code=400, detail="Файл должен быть изображением.")
        image_filename = f"room_{db_room.cab_id}_{image_file.filename}"
        image_path = os.path.join(ROOM_IMAGE_DIR, image_filename)
        os.makedirs(ROOM_IMAGE_DIR, exist_ok=True)
        with open(image_path, "wb") as buffer:
            content = image_file.file.read()  # Без await
            if not content:
                raise HTTPException(status_code=400, detail="Файл изображения пустой")
            buffer.write(content)
        update_data["image_path"] = f"/{image_path}"

    # Применяем обновления
    for key, value in update_data.items():
        setattr(db_room, key, value)

    # Обрабатываем connections (удаляем старые и добавляем новые)
    if room_data.connections is not None:
        # Удаляем существующие связи
        db.query(Connection).filter(Connection.room_id == room_id).delete()
        # Добавляем новые связи
        for connection_data in room_data.connections:
            if connection_data.segment_id is not None:
                db_connection = Connection(
                    room_id=db_room.id,
                    segment_id=connection_data.segment_id,
                    type=connection_data.type.value,
                    weight=connection_data.weight
                )
                db.add(db_connection)
            else:
                raise HTTPException(status_code=400, detail="Соединения комнаты должны иметь segment_id")

    db.commit()
    db.refresh(db_room)
    return db_room

def delete_room(db: Session, room_id: int):
    db_room = get_room(db, room_id)
    if not db_room:
        raise HTTPException(status_code=404, detail="Room not found")
    if db_room.image_path and os.path.exists(db_room.image_path[1:]):
        os.remove(db_room.image_path[1:])
    db.delete(db_room)
    db.commit()
    return db_room
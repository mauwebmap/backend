import os
from typing import Optional
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from app.map.models.room import Room
from app.map.models.connection import Connection
from app.map.schemas.room import RoomCreate, RoomUpdate
import mimetypes

# Директория для фотографий комнат
ROOM_IMAGE_DIR = "static/images/rooms"
os.makedirs(ROOM_IMAGE_DIR, exist_ok=True)

# Проверка, является ли файл изображением
def is_image_file(file: UploadFile):
    mime_type, _ = mimetypes.guess_type(file.filename)
    return mime_type and mime_type.startswith("image/")

# Получить комнату по ID
def get_room(db: Session, room_id: int):
    return db.query(Room).filter(Room.id == room_id).first()

# Получить все комнаты
def get_rooms(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Room).offset(skip).limit(limit).all()

# Создать комнату с соединениями
async def create_room_with_connections(db: Session, room_data: RoomCreate, image_file: Optional[UploadFile] = None):
    try:
        # Создаем комнату
        room_dict = room_data.dict()
        if image_file:
            if not is_image_file(image_file):
                raise HTTPException(status_code=400, detail="Файл должен быть изображением (JPEG, PNG).")

            image_filename = f"room_{room_data.name}_{image_file.filename}"
            image_path = os.path.join(ROOM_IMAGE_DIR, image_filename)
            with open(image_path, "wb") as buffer:
                await image_file.copy(buffer)
            room_dict["image_path"] = f"/{image_path}"

        db_room = Room(**room_dict)
        db.add(db_room)
        db.flush()  # Фиксируем комнату в базе, чтобы получить ID

        # Создаем соединения
        for connection_data in room_data.connections:
            db_connection = Connection(
                room_id=db_room.id,
                segment_id=connection_data.segment_id,
                type=connection_data.type.value,  # Используем значение Enum
                weight=connection_data.weight
            )
            db.add(db_connection)

        db.commit()
        db.refresh(db_room)
        return db_room
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при создании комнаты и связей: {str(e)}")

# Обновить комнату с соединениями
async def update_room_with_connections(db: Session, room_id: int, room_data: RoomUpdate, image_file: Optional[UploadFile] = None):
    db_room = get_room(db, room_id)
    if not db_room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Обновляем основные данные комнаты
    update_data = room_data.dict(exclude_unset=True)
    if image_file:
        if not is_image_file(image_file):
            raise HTTPException(status_code=400, detail="Файл должен быть изображением (JPEG, PNG).")

        # Удаляем старый файл, если он существует
        if db_room.image_path and os.path.exists(db_room.image_path[1:]):
            os.remove(db_room.image_path[1:])

        image_filename = f"room_{db_room.name}_{image_file.filename}"
        image_path = os.path.join(ROOM_IMAGE_DIR, image_filename)
        with open(image_path, "wb") as buffer:
            await image_file.copy(buffer)
        update_data["image_path"] = f"/{image_path}"

    for key, value in update_data.items():
        setattr(db_room, key, value)

    # Удаляем старые соединения
    for connection in db_room.connections:
        db.delete(connection)

    # Создаем новые соединения
    for connection_data in room_data.connections or []:
        db_connection = Connection(
            room_id=db_room.id,
            segment_id=connection_data.segment_id,
            type=connection_data.type.value,
            weight=connection_data.weight
        )
        db.add(db_connection)

    db.commit()
    db.refresh(db_room)
    return db_room

# Удалить комнату
def delete_room(db: Session, room_id: int):
    db_room = get_room(db, room_id)
    if not db_room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Удаляем связанные соединения
    for connection in db_room.connections:
        db.delete(connection)

    # Удаляем файл изображения
    if db_room.image_path and os.path.exists(db_room.image_path[1:]):
        os.remove(db_room.image_path[1:])

    db.delete(db_room)
    db.commit()
    return db_room
import os
from typing import Optional
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
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
    return db.query(Room).filter(Room.id == room_id).first()

def get_rooms(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Room).offset(skip).limit(limit).all()

def get_rooms_by_floor_and_campus(db: Session, floor_id: int, campus_id: int):
    return (
        db.query(Room)
        .join(Floor, Floor.id == Room.floor_id)
        .join(Building, Building.id == Floor.building_id)
        .filter(Floor.id == floor_id, Building.campus_id == campus_id)
        .all()
    )

async def create_room(db: Session, room_data: RoomCreate, image_file: Optional[UploadFile] = None):
    try:
        # Преобразуем RoomCreate в словарь
        room_dict = room_data.dict(exclude={"connections"})  # Исключаем connections из основных данных
        if image_file:
            if not is_image_file(image_file):
                raise HTTPException(status_code=400, detail="Файл должен быть изображением (JPEG, PNG)")
            image_filename = f"room_{room_data.name}_{image_file.filename}"
            image_path = os.path.join(ROOM_IMAGE_DIR, image_filename)
            with open(image_path, "wb") as buffer:
                buffer.write(await image_file.read())
            room_dict["image_path"] = f"/{image_path}"

        db_room = Room(**room_dict)
        db.add(db_room)
        db.flush()  # Фиксируем комнату, чтобы получить ID

        # Создаём соединения
        for connection_data in room_data.connections:
            db_connection = Connection(
                from_room_id=db_room.id,
                to_segment_id=connection_data.segment_id,
                type=connection_data.type.value,
                weight=connection_data.weight
            )
            db.add(db_connection)

        db.commit()
        db.refresh(db_room)
        return db_room
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при создании комнаты: {str(e)}")

async def update_room(db: Session, room_id: int, room_data: RoomUpdate, image_file: Optional[UploadFile] = None):
    db_room = get_room(db, room_id)
    if not db_room:
        raise HTTPException(status_code=404, detail="Room not found")

    try:
        # Преобразуем RoomUpdate в словарь, исключая неустановленные поля
        update_data = room_data.dict(exclude_unset=True, exclude={"connections"})
        if image_file:
            if not is_image_file(image_file):
                raise HTTPException(status_code=400, detail="Файл должен быть изображением (JPEG, PNG)")
            if db_room.image_path and os.path.exists(db_room.image_path[1:]):
                os.remove(db_room.image_path[1:])
            image_filename = f"room_{db_room.name}_{image_file.filename}"
            image_path = os.path.join(ROOM_IMAGE_DIR, image_filename)
            with open(image_path, "wb") as buffer:
                buffer.write(await image_file.read())
            update_data["image_path"] = f"/{image_path}"

        # Обновляем поля комнаты
        for key, value in update_data.items():
            setattr(db_room, key, value)

        # Обновляем соединения, если переданы
        if room_data.connections is not None:
            # Удаляем старые соединения
            for conn in db_room.connections_from:
                db.delete(conn)
            # Создаём новые соединения
            for connection_data in room_data.connections:
                db_connection = Connection(
                    from_room_id=db_room.id,
                    to_segment_id=connection_data.segment_id,
                    type=connection_data.type.value,
                    weight=connection_data.weight
                )
                db.add(db_connection)

        db.commit()
        db.refresh(db_room)
        return db_room
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при обновлении комнаты: {str(e)}")

def delete_room(db: Session, room_id: int):
    db_room = get_room(db, room_id)
    if not db_room:
        raise HTTPException(status_code=404, detail="Room not found")
    if db_room.image_path and os.path.exists(db_room.image_path[1:]):
        os.remove(db_room.image_path[1:])
    db.delete(db_room)
    db.commit()
    return db_room
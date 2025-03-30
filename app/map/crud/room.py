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
    # Исключаем connections из словаря, так как это не поле модели Room
    room_dict = room_data.dict(exclude={"connections"})

    # Обрабатываем coordinates (они уже в формате List[Coordinates], преобразуем в JSON для хранения)
    if room_data.coordinates:
        room_dict["coordinates"] = [coord.dict() for coord in room_data.coordinates]

    # Обрабатываем image_file
    if image_file:
        if not is_image_file(image_file):
            raise HTTPException(status_code=400, detail="Файл должен быть изображением.")
        image_filename = f"room_{room_data.cab_id}_{image_file.filename}"
        image_path = os.path.join(ROOM_IMAGE_DIR, image_filename)
        os.makedirs(ROOM_IMAGE_DIR, exist_ok=True)
        with open(image_path, "wb") as buffer:
            content = image_file.file.read()  # Без await, как мы решили ранее
            if not content:
                raise HTTPException(status_code=400, detail="Файл изображения пустой")
            buffer.write(content)
        room_dict["image_path"] = f"/{image_path}"

    # Создаём комнату
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
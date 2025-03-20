import os
from typing import Optional
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from app.map.models.room import Room
from app.map.models.connection import Connection
from app.map.schemas.room import RoomCreate, RoomUpdate

SVG_DIR = "static/svg/rooms"
os.makedirs(SVG_DIR, exist_ok=True)

def get_room(db: Session, room_id: int):
    return db.query(Room).filter(Room.id == room_id).first()

def get_rooms(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Room).offset(skip).limit(limit).all()

async def create_room_with_connections(db: Session, room_data: RoomCreate, svg_file: Optional[UploadFile] = None):
    try:
        # Создаем комнату
        room_dict = room_data.dict()
        if svg_file:
            svg_filename = f"room_{room_data.name}_{svg_file.filename}"
            svg_path = os.path.join(SVG_DIR, svg_filename)
            with open(svg_path, "wb") as buffer:
                await svg_file.copy(buffer)
            room_dict["image_path"] = f"/{svg_path}"

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

async def update_room_with_connections(db: Session, room_id: int, room_data: RoomUpdate, svg_file: Optional[UploadFile] = None):
    db_room = get_room(db, room_id)
    if not db_room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Обновляем основные данные комнаты
    update_data = room_data.dict(exclude_unset=True)
    if svg_file:
        svg_filename = f"room_{db_room.name}_{svg_file.filename}"
        svg_path = os.path.join(SVG_DIR, svg_filename)
        with open(svg_path, "wb") as buffer:
            await svg_file.copy(buffer)
        update_data["image_path"] = f"/{svg_path}"

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
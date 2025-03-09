from typing import Optional
from sqlalchemy.orm import Session
from app.map.models.room import Room
from app.map.models.building import Building
from app.map.schemas.room import RoomCreate, RoomUpdate
import os
from fastapi import UploadFile
from shutil import copyfileobj

SVG_DIR = "static/svg/rooms"
os.makedirs(SVG_DIR, exist_ok=True)

def get_room(db: Session, room_id: int) -> Optional[Room]:
    """Получить комнату по ID."""
    return db.query(Room).filter(Room.id == room_id).first()

def get_rooms(db: Session, skip: int = 0, limit: int = 100) -> list[Room]:
    """Получить список комнат с пагинацией."""
    return db.query(Room).offset(skip).limit(limit).all()

async def create_room(db: Session, room: RoomCreate, svg_file: Optional[UploadFile] = None) -> Room:
    """Создать новую комнату."""
    room_dict = room.dict()
    if svg_file:
        building = db.query(Building).filter(Building.id == room.building_id).first()
        svg_filename = f"room_{room.name}_building_{building.name if building else room.building_id}_{svg_file.filename}"
        svg_path = os.path.join(SVG_DIR, svg_filename)
        with open(svg_path, "wb") as buffer:
            copyfileobj(svg_file.file, buffer)
        room_dict["image_path"] = f"/{svg_path}"

    db_room = Room(**room_dict)
    db.add(db_room)
    db.commit()
    db.refresh(db_room)
    return db_room

async def update_room(db: Session, room_id: int, room: RoomUpdate, svg_file: Optional[UploadFile] = None) -> Room | None:
    """Обновить существующую комнату."""
    db_room = get_room(db, room_id)
    if not db_room:
        return None

    update_data = room.dict(exclude_unset=True)  # Только переданные поля
    if svg_file:
        building = db.query(Building).filter(Building.id == db_room.building_id).first()
        svg_filename = f"room_{db_room.name}_building_{building.name if building else db_room.building_id}_{svg_file.filename}"
        svg_path = os.path.join(SVG_DIR, svg_filename)
        with open(svg_path, "wb") as buffer:
            copyfileobj(svg_file.file, buffer)
        update_data["image_path"] = f"/{svg_path}"

    for key, value in update_data.items():
        setattr(db_room, key, value)
    db.commit()
    db.refresh(db_room)
    return db_room

def delete_room(db: Session, room_id: int) -> Optional[Room]:
    """Удалить комнату."""
    db_room = get_room(db, room_id)
    if not db_room:
        return None
    if db_room.image_path and os.path.exists(db_room.image_path[1:]):  # Убираем начальный "/"
        os.remove(db_room.image_path[1:])
    db.delete(db_room)
    db.commit()
    return db_room
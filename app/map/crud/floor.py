from typing import Optional

from sqlalchemy.orm import Session
from app.map.models.floor import Floor
from app.map.schemas.floor import FloorCreate, FloorUpdate
import os
from fastapi import UploadFile
from shutil import copyfileobj

SVG_DIR = "static/svg/floors"
os.makedirs(SVG_DIR, exist_ok=True)

def get_floor(db: Session, floor_id: int):
    return db.query(Floor).filter(Floor.id == floor_id).first()

def get_floors(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Floor).offset(skip).limit(limit).all()

async def create_floor(db: Session, floor: FloorCreate, svg_file: Optional[UploadFile] = None):
    if svg_file:
        building = db.query(Building).filter(Building.id == floor.building_id).first()
        svg_path = f"{SVG_DIR}/floor_{floor.floor_number}_building_{building.name if building else floor.building_id}_{svg_file.filename}"
        with open(svg_path, "wb") as buffer:
            copyfileobj(svg_file.file, buffer)
        floor_dict = floor.dict()
        floor_dict["image_path"] = f"/{svg_path}"
    else:
        floor_dict = floor.dict()

    db_floor = Floor(**floor_dict)
    db.add(db_floor)
    db.commit()
    db.refresh(db_floor)
    return db_floor

async def update_floor(db: Session, floor_id: int, floor: FloorUpdate, svg_file: Optional[UploadFile] = None):
    db_floor = get_floor(db, floor_id)
    if not db_floor:
        return None

    update_data = floor.dict(exclude_unset=True)
    if svg_file:
        building = db.query(Building).filter(Building.id == db_floor.building_id).first()
        svg_path = f"{SVG_DIR}/floor_{db_floor.floor_number}_building_{building.name if building else db_floor.building_id}_{svg_file.filename}"
        with open(svg_path, "wb") as buffer:
            copyfileobj(svg_file.file, buffer)
        update_data["image_path"] = f"/{svg_path}"

    for key, value in update_data.items():
        setattr(db_floor, key, value)
    db.commit()
    db.refresh(db_floor)
    return db_floor

def delete_floor(db: Session, floor_id: int):
    db_floor = get_floor(db, floor_id)
    if not db_floor:
        return None
    if db_floor.image_path and os.path.exists(db_floor.image_path[1:]):
        os.remove(db_floor.image_path[1:])
    db.delete(db_floor)
    db.commit()
    return db_floor
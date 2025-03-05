from typing import Optional
from sqlalchemy.orm import Session
from app.map.models.building import Building
from app.map.schemas.building import BuildingCreate, BuildingUpdate
import os
from fastapi import UploadFile
from shutil import copyfileobj

SVG_DIR = "static/svg/buildings"
os.makedirs(SVG_DIR, exist_ok=True)

def get_building(db: Session, building_id: int):
    return db.query(Building).filter(Building.id == building_id).first()

def get_buildings(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Building).offset(skip).limit(limit).all()

async def create_building(db: Session, building: BuildingCreate, svg_file: Optional[UploadFile] = None):
    if svg_file:
        svg_path = f"{SVG_DIR}/building_{building.name}_{svg_file.filename}"
        with open(svg_path, "wb") as buffer:
            copyfileobj(svg_file.file, buffer)
        building_dict = building.dict()
        building_dict["image_path"] = f"/{svg_path}"
    else:
        building_dict = building.dict()

    db_building = Building(**building_dict)
    db.add(db_building)
    db.commit()
    db.refresh(db_building)
    return db_building

async def update_building(db: Session, building_id: int, building: BuildingUpdate, svg_file: Optional[UploadFile] = None):
    db_building = get_building(db, building_id)
    if not db_building:
        return None

    update_data = building.dict(exclude_unset=True)
    if svg_file:
        svg_path = f"{SVG_DIR}/building_{db_building.name}_{svg_file.filename}"
        with open(svg_path, "wb") as buffer:
            copyfileobj(svg_file.file, buffer)
        update_data["image_path"] = f"/{svg_path}"

    for key, value in update_data.items():
        setattr(db_building, key, value)
    db.commit()
    db.refresh(db_building)
    return db_building

def delete_building(db: Session, building_id: int):
    db_building = get_building(db, building_id)
    if not db_building:
        return None
    if db_building.image_path and os.path.exists(db_building.image_path[1:]):
        os.remove(db_building.image_path[1:])
    db.delete(db_building)
    db.commit()
    return db_building
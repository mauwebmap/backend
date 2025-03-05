from typing import Optional
from sqlalchemy.orm import Session
from app.map.models.campus import Campus
from app.map.schemas.campus import CampusCreate, CampusUpdate
import os
from fastapi import UploadFile
from shutil import copyfileobj

SVG_DIR = "static/svg/campuses"
os.makedirs(SVG_DIR, exist_ok=True)

def get_campus(db: Session, campus_id: int):
    return db.query(Campus).filter(Campus.id == campus_id).first()

def get_campuses(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Campus).offset(skip).limit(limit).all()

async def create_campus(db: Session, campus: CampusCreate, svg_file: Optional[UploadFile] = None):
    if svg_file:
        svg_path = f"{SVG_DIR}/campus_{campus.name}_{svg_file.filename}"
        with open(svg_path, "wb") as buffer:
            copyfileobj(svg_file.file, buffer)
        campus_dict = campus.dict()
        campus_dict["image_path"] = f"/{svg_path}"
    else:
        campus_dict = campus.dict()

    db_campus = Campus(**campus_dict)
    db.add(db_campus)
    db.commit()
    db.refresh(db_campus)
    return db_campus

async def update_campus(db: Session, campus_id: int, campus: CampusUpdate, svg_file: Optional[UploadFile] = None):
    db_campus = get_campus(db, campus_id)
    if not db_campus:
        return None

    update_data = campus.dict(exclude_unset=True)
    if svg_file:
        svg_path = f"{SVG_DIR}/campus_{db_campus.name}_{svg_file.filename}"
        with open(svg_path, "wb") as buffer:
            copyfileobj(svg_file.file, buffer)
        update_data["image_path"] = f"/{svg_path}"

    for key, value in update_data.items():
        setattr(db_campus, key, value)
    db.commit()
    db.refresh(db_campus)
    return db_campus

def delete_campus(db: Session, campus_id: int):
    db_campus = get_campus(db, campus_id)
    if not db_campus:
        return None
    if db_campus.image_path and os.path.exists(db_campus.image_path[1:]):
        os.remove(db_campus.image_path[1:])
    db.delete(db_campus)
    db.commit()
    return db_campus
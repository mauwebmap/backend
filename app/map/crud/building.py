import os
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import UploadFile, HTTPException, status
from shutil import copyfileobj
from uuid import uuid4
from app.map.models.building import Building

SVG_DIR = "static/svg/buildings"
os.makedirs(SVG_DIR, exist_ok=True)


def save_svg_file(file: UploadFile) -> str:
    if not file.filename.endswith(".svg"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only SVG files are allowed"
        )

    file_name = f"{uuid4()}.svg"
    file_path = os.path.join(SVG_DIR, file_name)

    with open(file_path, "wb") as buffer:
        copyfileobj(file.file, buffer)

    return f"/{file_path}"


def get_building(db: Session, building_id: int):
    return db.query(Building).filter(Building.id == building_id).first()

def get_all_buildings(db: Session, campus_id: Optional[int] = None, skip: int = 0, limit: int = 100):
    query = db.query(Building)
    if campus_id:
        query = query.filter(Building.campus_id == campus_id)
    return query.offset(skip).limit(limit).all()


def get_buildings(db: Session, campus_id: Optional[int] = None, skip: int = 0, limit: int = 100):
    query = db.query(Building)
    if campus_id:
        query = query.filter(Building.campus_id == campus_id)
    return query.offset(skip).limit(limit).all()


async def create_building(db: Session, building_data: dict, svg_file: Optional[UploadFile] = None):
    try:
        db_building = Building(**building_data)

        if svg_file:
            db_building.image_path = save_svg_file(svg_file)

        db.add(db_building)
        db.commit()
        db.refresh(db_building)
        return db_building
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


async def update_building(db: Session, building_id: int, update_data: dict, svg_file: Optional[UploadFile] = None):
    db_building = get_building(db, building_id)
    if not db_building:
        raise HTTPException(status_code=404, detail="Building not found")

    try:
        for key, value in update_data.items():
            setattr(db_building, key, value)

        if svg_file:
            if db_building.image_path and os.path.exists(db_building.image_path[1:]):
                os.remove(db_building.image_path[1:])
            db_building.image_path = save_svg_file(svg_file)

        db.commit()
        db.refresh(db_building)
        return db_building
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


def delete_building(db: Session, building_id: int):
    db_building = get_building(db, building_id)
    if not db_building:
        raise HTTPException(status_code=404, detail="Building not found")

    try:
        if db_building.image_path and os.path.exists(db_building.image_path[1:]):
            os.remove(db_building.image_path[1:])

        db.delete(db_building)
        db.commit()
        return db_building
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )
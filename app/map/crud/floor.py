import os
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import UploadFile, HTTPException, status
from shutil import copyfileobj
from uuid import uuid4
from app.map.models.floor import Floor

SVG_DIR = "static/svg/floors"
os.makedirs(SVG_DIR, exist_ok=True)

def get_floor(db: Session, floor_id: int):
    return db.query(Floor).filter(Floor.id == floor_id).first()

def get_all_floors(db: Session, building_id: Optional[int] = None, skip: int = 0, limit: int = 100):
    query = db.query(Floor)
    if building_id:
        query = query.filter(Floor.building_id == building_id)
    return query.offset(skip).limit(limit).all()

async def save_svg_file(file: UploadFile) -> str:
    """Сохраняет SVG-файл с уникальным именем."""
    if not file.filename.lower().endswith(".svg"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only SVG files are allowed"
        )

    unique_name = f"{uuid4().hex}.svg"
    file_path = os.path.join(SVG_DIR, unique_name)

    with open(file_path, "wb") as buffer:
        copyfileobj(file.file, buffer)

    return f"/{SVG_DIR}/{unique_name}"

async def create_floor(db: Session, floor: dict, svg_file: Optional[UploadFile] = None):
    try:
        # Проверяем существование здания
        building = db.query(Building).filter(Building.id == floor["building_id"]).first()
        if not building:
            raise HTTPException(status_code=404, detail="Building not found")

        # Сохраняем SVG, если он есть
        if svg_file:
            floor["image_path"] = await save_svg_file(svg_file)

        db_floor = Floor(**floor)
        db.add(db_floor)
        db.commit()
        db.refresh(db_floor)
        return db_floor
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )

async def update_floor(db: Session, floor_id: int, floor: dict, svg_file: Optional[UploadFile] = None):
    try:
        db_floor = get_floor(db, floor_id)
        if not db_floor:
            raise HTTPException(status_code=404, detail="Floor not found")

        # Обновляем данные
        update_data = {k: v for k, v in floor.items() if v is not None}
        if svg_file:
            if db_floor.image_path and os.path.exists(db_floor.image_path[1:]):
                os.remove(db_floor.image_path[1:])
            update_data["image_path"] = await save_svg_file(svg_file)

        for key, value in update_data.items():
            setattr(db_floor, key, value)

        db.commit()
        db.refresh(db_floor)
        return db_floor
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )

def delete_floor(db: Session, floor_id: int):
    try:
        db_floor = get_floor(db, floor_id)
        if not db_floor:
            raise HTTPException(status_code=404, detail="Floor not found")

        if db_floor.image_path and os.path.exists(db_floor.image_path[1:]):
            os.remove(db_floor.image_path[1:])

        db.delete(db_floor)
        db.commit()
        return db_floor
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )
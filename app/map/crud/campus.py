from typing import Optional
import uuid
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


async def create_campus(
        db: Session,
        name: str,
        description: str,
        svg_file: UploadFile = None
) -> Campus:
    image_path = None

    if svg_file:
        # Генерация имени с UUID
        file_ext = os.path.splitext(svg_file.filename)[-1]  # Получаем расширение (.svg)
        unique_filename = f"campus_{uuid.uuid4().hex}{file_ext}"  # Формат: campus_<uuid>.svg
        file_path = os.path.join(SVG_DIR, unique_filename)

        # Сохраняем файл
        contents = await svg_file.read()
        with open(file_path, "wb") as buffer:
            buffer.write(contents)

        image_path = f"/{file_path}"  # Путь в формате: /static/svg/campuses/campus_<uuid>.svg

    # Создаем объект в БД
    db_campus = Campus(
        name=name,
        description=description,
        image_path=image_path
    )

    db.add(db_campus)
    db.commit()
    db.refresh(db_campus)
    return db_campus


async def update_campus(
        db: Session,
        campus_id: int,
        campus: CampusUpdate,
        svg_file: Optional[UploadFile] = None
):
    db_campus = get_campus(db, campus_id)
    if not db_campus:
        return None

    update_data = campus.dict(exclude_unset=True)

    # Обновление SVG-файла с UUID
    if svg_file:
        # Удаляем старый файл
        if db_campus.image_path and os.path.exists(db_campus.image_path.lstrip('/')):
            os.remove(db_campus.image_path.lstrip('/'))

        # Генерируем уникальное имя как в create_campus
        file_ext = os.path.splitext(svg_file.filename)[-1]
        unique_name = f"{db_campus.name}_{uuid.uuid4().hex}{file_ext}"
        file_path = os.path.join(SVG_DIR, unique_name)

        # Асинхронное сохранение
        contents = await svg_file.read()
        with open(file_path, "wb") as buffer:
            buffer.write(contents)

        update_data["image_path"] = f"/{file_path}"

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
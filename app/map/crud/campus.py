import os
import uuid
from typing import Optional, Dict
from sqlalchemy.orm import Session
from fastapi import UploadFile, HTTPException
from app.map.models.campus import Campus

SVG_DIR = os.path.abspath("static/svg/campuses")
os.makedirs(SVG_DIR, exist_ok=True)

def get_campus(db: Session, campus_id: int):
    return db.query(Campus).filter(Campus.id == campus_id).first()

def get_all_campuses(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Campus).offset(skip).limit(limit).all()

async def save_svg(file: UploadFile) -> str:
    """Save SVG file with UUID name"""
    if not file.filename.lower().endswith(".svg"):
        raise HTTPException(400, "Only SVG files allowed")

    unique_name = f"{uuid.uuid4().hex}.svg"
    file_path = os.path.join(SVG_DIR, unique_name)

    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)

    return f"/static/svg/campuses/{unique_name}"

def check_name_exists(db: Session, name: str, exclude_id: Optional[int] = None):
    """Check for existing campus name"""
    query = db.query(Campus).filter(Campus.name == name)
    if exclude_id:
        query = query.filter(Campus.id != exclude_id)
    return query.first() is not None

async def create_campus(
    db: Session,
    name: str,
    description: Optional[str],
    svg_file: Optional[UploadFile]
) -> Campus:
    # Check for existing name
    if check_name_exists(db, name):
        raise HTTPException(400, "Campus name already exists")

    # Handle file upload
    image_path = await save_svg(svg_file) if svg_file else None

    # Create object
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
    update_data: dict,
    svg_file: Optional[UploadFile] = None
) -> Campus:
    campus = db.query(Campus).get(campus_id)
    if not campus:
        raise HTTPException(404, "Campus not found")

    # Удаляем None-значения
    update_data = {k: v for k, v in update_data.items() if v is not None}

    # Проверка имени
    if "name" in update_data:
        if check_name_exists(db, update_data["name"], exclude_id=campus_id):
            raise HTTPException(400, "Name already exists")
        campus.name = update_data["name"]

    # Обновление описания
    if "description" in update_data:
        campus.description = update_data["description"]

    # Обработка файла
    if svg_file:
        # Валидация расширения
        if not svg_file.filename.lower().endswith(".svg"):
            raise HTTPException(400, "Only SVG files allowed")

        # Удаление старого файла
        if campus.image_path:
            try:
                os.remove(campus.image_path.lstrip('/'))
            except FileNotFoundError:
                pass

        # Генерация нового имени
        unique_name = f"{uuid.uuid4().hex}.svg"
        file_path = os.path.join(SVG_DIR, unique_name)

        # Сохранение
        contents = await svg_file.read()
        with open(file_path, "wb") as f:
            f.write(contents)

        campus.image_path = f"/static/svg/campuses/{unique_name}"

    db.commit()
    db.refresh(campus)
    return campus

def delete_campus(db: Session, campus_id: int):
    db_campus = get_campus(db, campus_id)
    if not db_campus:
        return None

    # Удаляем связанный SVG-файл
    delete_svg(db_campus.image_path)
    db.delete(db_campus)
    db.commit()
    return db_campus

def delete_svg(file_path: str):
    """Удаляет SVG-файл по указанному пути, если он существует."""
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except FileNotFoundError:
            print(f"Файл {file_path} не найден для удаления.")
        except Exception as e:
            print(f"Ошибка при удалении файла {file_path}: {e}")
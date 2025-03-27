import os
from typing import Optional
from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session
from app.map.models.floor import Floor
from app.map.models.connection import Connection
from app.map.schemas.floor import FloorCreate, FloorUpdate
from app.map.models.building import Building
import mimetypes

# Директория для SVG-файлов этажей
SVG_DIR = "static/svg/floors"
os.makedirs(SVG_DIR, exist_ok=True)

# Проверка, является ли файл SVG
def is_svg_file(file: UploadFile):
    mime_type, _ = mimetypes.guess_type(file.filename)
    return mime_type == "image/svg+xml"

# Получить этаж по ID
def get_floor(db: Session, floor_id: int):
    return db.query(Floor).filter(Floor.id == floor_id).first()

# Получить все этажи
def get_all_floors(db: Session, building_id: Optional[int] = None, skip: int = 0, limit: int = 100):
    query = db.query(Floor)
    if building_id:
        query = query.filter(Floor.building_id == building_id)
    return query.offset(skip).limit(limit).all()

def get_unique_floor_numbers_by_campus(db: Session, campus_id: int):
    """
    Получить уникальные номера этажей в выбранном кампусе.
    """
    floors = (
        db.query(Floor.floor_number)
        .join(Building, Building.id == Floor.building_id)
        .filter(Building.campus_id == campus_id)
        .distinct()
        .order_by(Floor.floor_number.asc())
        .all()
    )
    # Преобразуем результат в плоский список
    return [floor[0] for floor in floors]

def get_floors_by_campus_and_number(db: Session, campus_id: int, floor_number: int):
    """
    Получить все этажи с указанным номером, принадлежащие указанному кампусу.
    """
    return (
        db.query(Floor)
        .join(Building, Building.id == Floor.building_id)
        .filter(Building.campus_id == campus_id, Floor.floor_number == floor_number)
        .all()
    )

# Создать этаж с соединениями
async def create_floor_with_connections(db: Session, floor_data: FloorCreate, svg_file: Optional[UploadFile] = None):
    floor_dict = floor_data.dict()
    if svg_file:
        if not is_svg_file(svg_file):
            raise HTTPException(status_code=400, detail="Файл должен быть SVG.")
        svg_filename = f"floor_{floor_data.floor_number}_{svg_file.filename}"
        svg_path = os.path.join(SVG_DIR, svg_filename)
        os.makedirs(SVG_DIR, exist_ok=True)
        with open(svg_path, "wb") as buffer:
            content = svg_file.file.read()  # Убрали await
            if not content:
                raise HTTPException(status_code=400, detail="SVG файл пустой")
            buffer.write(content)
        floor_dict["image_path"] = f"/{svg_path}"

    db_floor = Floor(**floor_dict)
    db.add(db_floor)
    db.flush()

    for connection_data in floor_data.connections:
        db_connection = Connection(
            from_floor_id=db_floor.id,
            to_floor_id=connection_data.to_floor_id,
            type=connection_data.type.value,
            weight=connection_data.weight
        )
        db.add(db_connection)

    db.commit()
    db.refresh(db_floor)
    return db_floor

# Обновить этаж
def update_floor(db: Session, floor_id: int, floor_data: FloorUpdate, svg_file: Optional[UploadFile] = None):
    db_floor = get_floor(db, floor_id)
    if not db_floor:
        raise HTTPException(status_code=404, detail="Floor not found")

    # Преобразуем FloorUpdate в словарь, исключая неустановленные поля
    update_data = floor_data.dict(exclude_unset=True)
    if svg_file:
        if not is_svg_file(svg_file):
            raise HTTPException(status_code=400, detail="Файл должен быть SVG.")

        # Удаляем старый файл, если он существует
        if db_floor.image_path and os.path.exists(db_floor.image_path[1:]):
            os.remove(db_floor.image_path[1:])

        svg_filename = f"floor_{db_floor.floor_number}_{svg_file.filename}"
        svg_path = os.path.join(SVG_DIR, svg_filename)
        with open(svg_path, "wb") as buffer:
            buffer.write(svg_file.file.read())
        update_data["image_path"] = f"/{svg_path}"

    # Обновляем только переданные поля
    for key, value in update_data.items():
        setattr(db_floor, key, value)

    # Обновляем connections, только если они переданы
    if floor_data.connections is not None:  # Проверяем, переданы ли связи
        # Удаляем старые соединения
        for connection in db_floor.connections_from:
            db.delete(connection)

        # Создаём новые соединения
        for connection_data in floor_data.connections:
            db_connection = Connection(
                from_floor_id=db_floor.id,
                to_floor_id=connection_data.to_floor_id,
                type=connection_data.type.value,
                weight=connection_data.weight
            )
            db.add(db_connection)

    db.commit()
    db.refresh(db_floor)
    return db_floor

# Удалить этаж
def delete_floor(db: Session, floor_id: int):
    db_floor = get_floor(db, floor_id)
    if not db_floor:
        raise HTTPException(status_code=404, detail="Floor not found")

    # Удаляем связанные соединения
    for connection in db_floor.connections_from:
        db.delete(connection)

    # Удаляем файл SVG
    if db_floor.image_path and os.path.exists(db_floor.image_path[1:]):
        os.remove(db_floor.image_path[1:])

    db.delete(db_floor)
    db.commit()
    return db_floor
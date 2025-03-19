from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.map.models.floor import Floor
from app.map.models.connection import Connection
from app.map.schemas.floor import FloorCreate

# Получить этаж по ID
def get_floor(db: Session, floor_id: int):
    return db.query(Floor).filter(Floor.id == floor_id).first()

# Получить все этажи
def get_all_floors(db: Session, building_id: Optional[int] = None, skip: int = 0, limit: int = 100):
    query = db.query(Floor)
    if building_id:
        query = query.filter(Floor.building_id == building_id)
    return query.offset(skip).limit(limit).all()

# Создать этаж с соединениями
def create_floor_with_connections(db: Session, floor_data: FloorCreate):
    try:
        # Создаем этаж
        db_floor = Floor(
            building_id=floor_data.building_id,
            floor_number=floor_data.floor_number,
            image_path=floor_data.image_path,
            description=floor_data.description
        )
        db.add(db_floor)
        db.flush()  # Фиксируем этаж в базе, чтобы получить ID

        # Создаем соединения
        for connection_data in floor_data.connections:
            db_connection = Connection(
                from_floor_id=db_floor.id,
                to_floor_id=connection_data.to_floor_id,
                type=connection_data.type.value,  # Используем значение Enum
                weight=connection_data.weight
            )
            db.add(db_connection)

        db.commit()
        db.refresh(db_floor)
        return db_floor
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при создании этажа и связей: {str(e)}"
        )

# Обновить этаж
def update_floor(db: Session, floor_id: int, floor_data: FloorCreate):
    db_floor = get_floor(db, floor_id)
    if not db_floor:
        raise HTTPException(status_code=404, detail="Floor not found")

    # Обновляем основные данные этажа
    db_floor.building_id = floor_data.building_id
    db_floor.floor_number = floor_data.floor_number
    db_floor.image_path = floor_data.image_path
    db_floor.description = floor_data.description

    # Удаляем старые соединения
    for connection in db_floor.connections_from:
        db.delete(connection)

    # Создаем новые соединения
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

    db.delete(db_floor)
    db.commit()
    return db_floor
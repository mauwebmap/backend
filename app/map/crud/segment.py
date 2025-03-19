from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.map.models.segment import Segment
from app.map.models.connection import Connection
from app.map.schemas.segment import SegmentCreate

# Получить сегмент по ID
def get_segment(db: Session, segment_id: int):
    return db.query(Segment).filter(Segment.id == segment_id).first()

# Получить все сегменты
def get_segments(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Segment).offset(skip).limit(limit).all()

# Создать сегмент с соединениями
def create_segment_with_connections(db: Session, segment_data: SegmentCreate):
    try:
        # Создаем сегмент
        db_segment = Segment(
            start_x=segment_data.start_x,
            start_y=segment_data.start_y,
            end_x=segment_data.end_x,
            end_y=segment_data.end_y,
            floor_id=segment_data.floor_id,
            building_id=segment_data.building_id
        )
        db.add(db_segment)
        db.flush()  # Фиксируем сегмент в базе, чтобы получить ID

        # Создаем соединения
        for connection_data in segment_data.connections:
            db_connection = Connection(
                segment_id=db_segment.id,
                to_segment_id=connection_data.to_segment_id,
                type=connection_data.type.value,  # Используем значение Enum
                weight=connection_data.weight
            )
            db.add(db_connection)

        db.commit()
        db.refresh(db_segment)
        return db_segment
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при создании сегмента и связей: {str(e)}"
        )

# Обновить сегмент
def update_segment(db: Session, segment_id: int, segment_data: SegmentCreate):
    db_segment = get_segment(db, segment_id)
    if not db_segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    # Обновляем основные данные сегмента
    db_segment.start_x = segment_data.start_x
    db_segment.start_y = segment_data.start_y
    db_segment.end_x = segment_data.end_x
    db_segment.end_y = segment_data.end_y
    db_segment.floor_id = segment_data.floor_id
    db_segment.building_id = segment_data.building_id

    # Удаляем старые соединения
    for connection in db_segment.connections:
        db.delete(connection)

    # Создаем новые соединения
    for connection_data in segment_data.connections:
        db_connection = Connection(
            segment_id=db_segment.id,
            to_segment_id=connection_data.to_segment_id,
            type=connection_data.type.value,
            weight=connection_data.weight
        )
        db.add(db_connection)

    db.commit()
    db.refresh(db_segment)
    return db_segment

# Удалить сегмент
def delete_segment(db: Session, segment_id: int):
    db_segment = get_segment(db, segment_id)
    if not db_segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    # Удаляем связанные соединения
    for connection in db_segment.connections:
        db.delete(connection)

    db.delete(db_segment)
    db.commit()
    return db_segment
from sqlalchemy.orm import Session
from app.map.models.outdoor_segment import OutdoorSegment
from app.map.schemas.outdoor_segment import OutdoorSegmentCreate, OutdoorSegmentUpdate
from fastapi import HTTPException

from app.map.models.connection import Connection


def get_outdoor_segment(db: Session, outdoor_segment_id: int):
    return db.query(OutdoorSegment).filter(OutdoorSegment.id == outdoor_segment_id).first()

def get_outdoor_segments(db: Session, skip: int = 0, limit: int = 100):
    return db.query(OutdoorSegment).offset(skip).limit(limit).all()

def get_outdoor_segments_by_campus(db: Session, campus_id: int, skip: int = 0, limit: int = 100):
    outdoor_segments = (
        db.query(OutdoorSegment)
        .filter(OutdoorSegment.campus_id == campus_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    if not outdoor_segments:
        raise HTTPException(status_code=404, detail="No outdoor segments found for the given campus")
    return outdoor_segments

def create_outdoor_segment(db: Session, outdoor_segment: OutdoorSegmentCreate):
    try:
        # Исключаем connections, если их нет
        segment_dict = outdoor_segment.dict(exclude_unset=True, exclude={"connections"})

        # Создаём уличный сегмент
        db_outdoor_segment = OutdoorSegment(**segment_dict)
        db.add(db_outdoor_segment)
        db.flush()  # Фиксируем в БД, чтобы получить ID

        # Если переданы connections, создаем их
        if outdoor_segment.connections:
            for connection_data in outdoor_segment.connections:
                db_connection = Connection(
                    from_outdoor_id=db_outdoor_segment.id,
                    **connection_data.dict()
                )
                db.add(db_connection)

        db.commit()
        db.refresh(db_outdoor_segment)
        return db_outdoor_segment
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при создании уличного сегмента: {str(e)}"
        )

def update_outdoor_segment(db: Session, outdoor_segment_id: int, outdoor_segment: OutdoorSegmentUpdate):
    db_outdoor_segment = get_outdoor_segment(db, outdoor_segment_id)
    if not db_outdoor_segment:
        raise HTTPException(status_code=404, detail="Outdoor segment not found")

    # Обновляем только переданные данные
    update_data = outdoor_segment.dict(exclude_unset=True, exclude={"connections"})
    for key, value in update_data.items():
        setattr(db_outdoor_segment, key, value)

    # Если connections переданы, удаляем старые и создаём новые
    if outdoor_segment.connections is not None:
        db.query(Connection).filter(
            (Connection.from_outdoor_id == db_outdoor_segment.id) |
            (Connection.to_outdoor_id == db_outdoor_segment.id)
        ).delete()

        for connection_data in outdoor_segment.connections:
            db_connection = Connection(
                from_outdoor_id=db_outdoor_segment.id,
                **connection_data.dict()
            )
            db.add(db_connection)

    db.commit()
    db.refresh(db_outdoor_segment)
    return db_outdoor_segment

def delete_outdoor_segment(db: Session, outdoor_segment_id: int):
    db_outdoor_segment = get_outdoor_segment(db, outdoor_segment_id)
    if not db_outdoor_segment:
        raise HTTPException(status_code=404, detail="Outdoor segment not found")

    # Удаляем связанные соединения
    db.query(Connection).filter(
        (Connection.from_outdoor_id == db_outdoor_segment.id) |
        (Connection.to_outdoor_id == db_outdoor_segment.id)
    ).delete()

    db.delete(db_outdoor_segment)
    db.commit()
    return db_outdoor_segment
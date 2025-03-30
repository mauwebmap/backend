from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.map.models.segment import Segment
from app.map.models.connection import Connection
from app.map.schemas.segment import SegmentCreate
from app.map.models.building import Building
from app.map.models.floor import Floor


# Получить сегмент по ID
def get_segment(db: Session, segment_id: int):
    return db.query(Segment).filter(Segment.id == segment_id).first()


# Получить все сегменты
def get_segments(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Segment).offset(skip).limit(limit).all()


def get_segments_by_floor_and_campus(db: Session, floor_id: int, campus_id: int):
    """
    Получить все сегменты на указанном этаже, принадлежащем указанному кампусу.
    """
    return (
        db.query(Segment)
        .join(Floor, Floor.id == Segment.floor_id)
        .join(Building, Building.id == Floor.building_id)
        .filter(Floor.id == floor_id, Building.campus_id == campus_id)
        .all()
    )


# Создать сегмент с соединениями
def create_segment_with_connections(db: Session, segment_data: SegmentCreate):
    try:
        # Исключаем connections из словаря, так как это не поле модели Segment
        segment_dict = segment_data.dict(exclude={"connections"})

        # Создаём сегмент
        db_segment = Segment(**segment_dict)
        db.add(db_segment)
        db.flush()  # Фиксируем сегмент в базе, чтобы получить ID

        # Если connections передан и не пустой, создаём соединения
        if segment_data.connections:
            for connection_data in segment_data.connections:
                db_connection = Connection(
                    from_segment_id=db_segment.id,  # Проставляем from_segment_id
                    to_segment_id=connection_data.to_segment_id,
                    from_floor_id=connection_data.from_floor_id,
                    to_floor_id=connection_data.to_floor_id,
                    type=connection_data.type.value,
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
    update_data = segment_data.dict(exclude_unset=True, exclude={"connections"})
    for key, value in update_data.items():
        if value is not None:  # Обновляем только те поля, которые переданы
            setattr(db_segment, key, value)

    # Обрабатываем connections, если они переданы
    if segment_data.connections:
        # Удаляем старые соединения
        db.query(Connection).filter(Connection.segment_id == db_segment.id).delete()
        # Создаём новые соединения
        for connection_data in segment_data.connections:
            db_connection = Connection(
                segment_id=db_segment.id,
                to_segment_id=connection_data.to_segment_id,
                from_floor_id=connection_data.from_floor_id,
                to_floor_id=connection_data.to_floor_id,
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
    db.query(Connection).filter(Connection.segment_id == db_segment.id).delete()

    db.delete(db_segment)
    db.commit()
    return db_segment
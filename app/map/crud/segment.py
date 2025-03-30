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
        # Создаем или обновляем сегмент
        segment_dict = segment_data.model_dump(exclude={"connections"})
        db_segment = Segment(**segment_dict)
        db.add(db_segment)
        db.flush()  # Получаем ID сегмента

        # Обрабатываем соединения
        if segment_data.connections:
            for connection_data in segment_data.connections:
                connection_dict = {}

                # Определяем тип соединения и заполняем соответствующие поля
                if connection_data.room_id is not None:
                    connection_dict = {
                        "room_id": connection_data.room_id,
                        "segment_id": db_segment.id,
                        "type": connection_data.type,
                        "weight": connection_data.weight
                    }
                elif connection_data.to_segment_id is not None:
                    connection_dict = {
                        "from_segment_id": db_segment.id,
                        "to_segment_id": connection_data.to_segment_id,
                        "type": connection_data.type,
                        "weight": connection_data.weight
                    }
                elif connection_data.from_floor_id is not None and connection_data.to_floor_id is not None:
                    connection_dict = {
                        "segment_id": db_segment.id,
                        "from_floor_id": connection_data.from_floor_id,
                        "to_floor_id": connection_data.to_floor_id,
                        "type": connection_data.type,
                        "weight": connection_data.weight
                    }
                else:
                    raise ValueError("Некорректные данные соединения")

                # Создаем соединение в базе данных
                db_connection = Connection(**connection_dict)
                db.add(db_connection)

        db.commit()
        db.refresh(db_segment)
        return db_segment
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при создании или обновлении сегмента: {str(e)}")

# Обновить сегмент
def update_segment(db: Session, segment_id: int, segment_data: SegmentCreate):
    db_segment = get_segment(db, segment_id)
    if not db_segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    # Обновляем только переданные поля сегмента
    update_data = segment_data.model_dump(exclude_unset=True, exclude={"connections"})
    for key, value in update_data.items():
        setattr(db_segment, key, value)

    # Обрабатываем connections, если они переданы
    if segment_data.connections is not None:
        # Удаляем старые соединения
        db.query(Connection).filter(
            (Connection.from_segment_id == db_segment.id) |
            (Connection.to_segment_id == db_segment.id) |
            (Connection.segment_id == db_segment.id)
        ).delete()

        # Создаём новые соединения
        for connection_data in segment_data.connections:
            connection_dict = {}

            if connection_data.room_id is not None:
                connection_dict = {
                    "room_id": connection_data.room_id,
                    "segment_id": db_segment.id,
                    "type": connection_data.type,
                    "weight": connection_data.weight
                }
            elif connection_data.to_segment_id is not None:
                connection_dict = {
                    "from_segment_id": db_segment.id,
                    "to_segment_id": connection_data.to_segment_id,
                    "type": connection_data.type,
                    "weight": connection_data.weight
                }
            elif connection_data.to_outdoor_id is not None:
                connection_dict = {
                    "from_segment_id": db_segment.id,
                    "to_outdoor_id": connection_data.to_outdoor_id,
                    "type": connection_data.type,
                    "weight": connection_data.weight
                }
            elif connection_data.from_floor_id is not None and connection_data.to_floor_id is not None:
                connection_dict = {
                    "segment_id": db_segment.id,
                    "from_floor_id": connection_data.from_floor_id,
                    "to_floor_id": connection_data.to_floor_id,
                    "type": connection_data.type,
                    "weight": connection_data.weight
                }
            else:
                raise ValueError("Некорректные данные соединения")

            db_connection = Connection(**connection_dict)
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
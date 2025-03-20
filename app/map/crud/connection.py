from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.map.models.connection import Connection
from app.map.schemas.connection import ConnectionCreate, ConnectionUpdate


def validate_connection_data(data: dict):
    """
    Валидация данных для создания или обновления соединения.
    Хотя бы одно из полей room_id, segment_id, from_floor_id, to_floor_id,
    from_outdoor_id, to_outdoor_id, from_segment_id, to_segment_id должно быть заполнено.
    """
    required_fields = [
        "room_id", "segment_id", "from_floor_id", "to_floor_id",
        "from_outdoor_id", "to_outdoor_id", "from_segment_id", "to_segment_id"
    ]
    if not any(data.get(field) is not None for field in required_fields):
        raise HTTPException(
            status_code=400,
            detail="At least one of the fields (room_id, segment_id, from_floor_id, to_floor_id, from_outdoor_id, to_outdoor_id, from_segment_id, to_segment_id) must be provided."
        )


def get_connection(db: Session, connection_id: int):
    return db.query(Connection).filter(Connection.id == connection_id).first()


def get_connections(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Connection).offset(skip).limit(limit).all()


def create_connection(db: Session, connection: ConnectionCreate):
    validate_connection_data(connection.dict())
    db_connection = Connection(**connection.dict())
    db.add(db_connection)
    db.commit()
    db.refresh(db_connection)
    return db_connection


def update_connection(db: Session, connection_id: int, connection: ConnectionUpdate):
    db_connection = get_connection(db, connection_id)
    if not db_connection:
        return None

    update_data = connection.dict(exclude_unset=True)
    validate_connection_data(update_data)

    for key, value in update_data.items():
        setattr(db_connection, key, value)

    db.commit()
    db.refresh(db_connection)
    return db_connection


def delete_connection(db: Session, connection_id: int):
    db_connection = get_connection(db, connection_id)
    if not db_connection:
        return None
    db.delete(db_connection)
    db.commit()
    return db_connection
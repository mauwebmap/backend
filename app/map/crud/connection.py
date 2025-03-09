from sqlalchemy.orm import Session
from app.map.models.connection import Connection
from app.map.schemas.connection import ConnectionCreate, ConnectionUpdate

def get_connection(db: Session, connection_id: int):
    return db.query(Connection).filter(Connection.id == connection_id).first()

def get_connections(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Connection).offset(skip).limit(limit).all()

def create_connection(db: Session, connection: ConnectionCreate):
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
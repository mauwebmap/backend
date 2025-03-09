from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.map.crud.connection import get_connection, get_connections, create_connection, update_connection, delete_connection
from app.map.schemas.connection import Connection, ConnectionCreate, ConnectionUpdate
from app.database.database import get_db

router = APIRouter(prefix="/connections", tags=["connections"])

@router.get("/{connection_id}", response_model=Connection)
def read_connection(connection_id: int, db: Session = Depends(get_db)):
    connection = get_connection(db, connection_id)
    if not connection: raise HTTPException(status_code=404, detail="Connection not found")
    return connection

@router.get("/", response_model=list[Connection])
def read_connections(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return get_connections(db, skip, limit)

@router.post("/", response_model=Connection)
def create_connection_endpoint(connection: ConnectionCreate, db: Session = Depends(get_db)):
    return create_connection(db, connection)

@router.put("/{connection_id}", response_model=Connection)
def update_connection_endpoint(connection_id: int, connection: ConnectionUpdate, db: Session = Depends(get_db)):
    updated_connection = update_connection(db, connection_id, connection)
    if not updated_connection: raise HTTPException(status_code=404, detail="Connection not found")
    return updated_connection

@router.delete("/{connection_id}", response_model=Connection)
def delete_connection_endpoint(connection_id: int, db: Session = Depends(get_db)):
    deleted_connection = delete_connection(db, connection_id)
    if not deleted_connection: raise HTTPException(status_code=404, detail="Connection not found")
    return deleted_connection
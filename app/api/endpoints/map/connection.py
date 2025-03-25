# app/endpoints/map/connections.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session
from app.map.crud.connection import (
    get_connection,
    get_connections,
    create_connection,
    update_connection,
    delete_connection
)
from app.map.schemas.connection import ConnectionResponse, ConnectionCreate, ConnectionUpdate
from app.database.database import get_db
from app.users.dependencies.auth import admin_required

router = APIRouter(prefix="/connections", tags=["Connections"])

@router.get("/", response_model=List[ConnectionResponse])
def read_connections(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Получить список всех соединений. Без авторизации."""
    return get_connections(db, skip=skip, limit=limit)

@router.get("/{connection_id}", response_model=ConnectionResponse)
def read_connection(
    connection_id: int,
    db: Session = Depends(get_db)
):
    """Получить информацию о соединении по ID. Без авторизации."""
    connection = get_connection(db, connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    return connection

@router.post("/", response_model=ConnectionResponse, dependencies=[Depends(admin_required)])
def create_connection_endpoint(
    request: Request,
    response: Response,
    connection: ConnectionCreate,
    db: Session = Depends(get_db)
):
    """Создать новое соединение между любыми объектами. Требуются права администратора."""
    try:
        return create_connection(db, connection)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при создании соединения: {str(e)}")

@router.put("/{connection_id}", response_model=ConnectionResponse, dependencies=[Depends(admin_required)])
def update_connection_endpoint(
    connection_id: int,
    request: Request,
    response: Response,
    connection: ConnectionUpdate,
    db: Session = Depends(get_db)
):
    """Обновить существующее соединение. Требуются права администратора."""
    try:
        updated_connection = update_connection(db, connection_id, connection)
        if not updated_connection:
            raise HTTPException(status_code=404, detail="Connection not found")
        return updated_connection
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при обновлении соединения: {str(e)}")

@router.delete("/{connection_id}", response_model=ConnectionResponse, dependencies=[Depends(admin_required)])
def delete_connection_endpoint(
    connection_id: int,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """Удалить соединение. Требуются права администратора."""
    try:
        deleted_connection = delete_connection(db, connection_id)
        if not deleted_connection:
            raise HTTPException(status_code=404, detail="Connection not found")
        return deleted_connection
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при удалении соединения: {str(e)}")
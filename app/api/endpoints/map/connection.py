from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.map.crud.connection import (
    get_connection,
    get_connections,
    create_connection,
    update_connection,
    delete_connection
)
from app.map.schemas.connection import ConnectionBase, ConnectionCreate, ConnectionUpdate, ConnectionResponse
from app.database.database import get_db
from app.users.dependencies.auth import admin_required

router = APIRouter(prefix="/connections", tags=["Connections"])

@router.get("/", response_model=list[ConnectionBase])
def read_connections(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Получить список всех соединений.
    """
    return get_connections(db, skip, limit)

@router.get("/{connection_id}", response_model=ConnectionBase)
def read_connection(
    connection_id: int,
    db: Session = Depends(get_db)
):
    """
    Получить информацию о соединении по его ID.
    """
    connection = get_connection(db, connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    return connection

@router.post("/", response_model=ConnectionBase, dependencies=[Depends(admin_required)])
def create_connection_endpoint(
    connection: ConnectionCreate,
    db: Session = Depends(get_db)
):
    """
    Создать новое соединение.
    Требуются права администратора.
    """
    try:
        return create_connection(db, connection)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при создании соединения: {str(e)}"
        )

@router.put("/{connection_id}", response_model=ConnectionBase, dependencies=[Depends(admin_required)])
def update_connection_endpoint(
    connection_id: int,
    connection: ConnectionUpdate,
    db: Session = Depends(get_db)
):
    """
    Обновить информацию о соединении.
    Требуются права администратора.
    """
    updated_connection = update_connection(db, connection_id, connection)
    if not updated_connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    return updated_connection

@router.delete("/{connection_id}", response_model=ConnectionBase, dependencies=[Depends(admin_required)])
def delete_connection_endpoint(
    connection_id: int,
    db: Session = Depends(get_db)
):
    """
    Удалить соединение по его ID.
    Требуются права администратора.
    """
    deleted_connection = delete_connection(db, connection_id)
    if not deleted_connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    return deleted_connection
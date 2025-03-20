from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile
from sqlalchemy.orm import Session
from app.map.crud.room import (
    read_room,
    get_rooms,
    create_room_with_connections,
    update_room_with_connections,
    delete_room
)
from app.map.schemas.room import RoomCreate, RoomUpdate, RoomResponse
from app.database.database import get_db
from app.users.dependencies.auth import admin_required

router = APIRouter(prefix="/rooms", tags=["Rooms"])

@router.get("/", response_model=list[RoomResponse])
def read_rooms(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Получить список всех комнат.
    """
    return get_rooms(db, skip=skip, limit=limit)

@router.get("/{room_id}", response_model=RoomResponse)
def read_room(room_id: int, db: Session = Depends(get_db)):
    """
    Получить информацию о комнате по её ID.
    """
    room = get_room(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room

@router.post("/", response_model=RoomResponse, dependencies=[Depends(admin_required)])
async def create_room_endpoint(
    room_data: RoomCreate,
    svg_file: Optional[UploadFile] = None,
    db: Session = Depends(get_db)
):
    """
    Создать новую комнату с возможными соединениями.
    Требуются права администратора.
    """
    try:
        return await create_room_with_connections(db, room_data, svg_file)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при создании комнаты: {str(e)}"
        )

@router.put("/{room_id}", response_model=RoomResponse, dependencies=[Depends(admin_required)])
async def update_room_endpoint(
    room_id: int,
    room_data: RoomUpdate,
    svg_file: Optional[UploadFile] = None,
    db: Session = Depends(get_db)
):
    """
    Обновить информацию о комнате.
    Требуются права администратора.
    """
    try:
        return await update_room_with_connections(db, room_id, room_data, svg_file)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при обновлении комнаты: {str(e)}"
        )

@router.delete("/{room_id}", response_model=RoomResponse, dependencies=[Depends(admin_required)])
def delete_room_endpoint(room_id: int, db: Session = Depends(get_db)):
    """
    Удалить комнату по её ID.
    Требуются права администратора.
    """
    try:
        return delete_room(db, room_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException
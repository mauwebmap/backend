from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from app.map.crud.room import get_room, get_rooms, create_room, update_room, delete_room
from app.map.schemas.room import RoomCreate, RoomUpdate, RoomResponse
from app.database.database import get_db
import os

router = APIRouter(prefix="/rooms", tags=["rooms"])

@router.get("/{room_id}", response_model=RoomResponse)
def read_room(room_id: int, db: Session = Depends(get_db)):
    """Получить комнату по ID."""
    room = get_room(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room

@router.get("/", response_model=list[RoomResponse])
def read_rooms(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Получить список комнат."""
    return get_rooms(db, skip=skip, limit=limit)

@router.post("/", response_model=RoomResponse)
async def create_room_endpoint(room: RoomCreate, svg_file: UploadFile | None = File(None), db: Session = Depends(get_db)):
    """Создать новую комнату."""
    return await create_room(db, room, svg_file)

@router.put("/{room_id}", response_model=RoomResponse)
async def update_room_endpoint(room_id: int, room: RoomUpdate, svg_file: UploadFile | None = File(None), db: Session = Depends(get_db)):
    """Обновить комнату."""
    updated_room = await update_room(db, room_id, room, svg_file)
    if not updated_room:
        raise HTTPException(status_code=404, detail="Room not found")
    return updated_room

@router.delete("/{room_id}", response_model=RoomResponse)
def delete_room_endpoint(room_id: int, db: Session = Depends(get_db)):
    """Удалить комнату."""
    deleted_room = delete_room(db, room_id)
    if not deleted_room:
        raise HTTPException(status_code=404, detail="Room not found")
    return deleted_room

@router.get("/{room_id}/svg")
async def get_room_svg(room_id: int, db: Session = Depends(get_db)):
    """Получить URL SVG-файла комнаты."""
    room = get_room(db, room_id)
    if not room or not room.image_path:
        raise HTTPException(status_code=404, detail="SVG not found")
    if not os.path.exists(room.image_path[1:]):
        raise HTTPException(status_code=404, detail="SVG file missing")
    return {"svg_url": room.image_path}
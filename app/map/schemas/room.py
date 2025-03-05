from pydantic import BaseModel
from typing import Optional, Dict

class RoomCreate(BaseModel):
    building_id: int
    floor_id: int
    name: str
    cab_id: str
    coordinates: Optional[Dict] = None
    description: Optional[str] = None

class RoomUpdate(BaseModel):
    building_id: Optional[int] = None
    floor_id: Optional[int] = None
    name: Optional[str] = None
    cab_id: Optional[str] = None
    coordinates: Optional[Dict] = None
    description: Optional[str] = None

class RoomResponse(BaseModel):
    id: int
    building_id: int
    floor_id: int
    name: str
    cab_id: str
    coordinates: Optional[Dict] = None
    description: Optional[str] = None
    image_path: Optional[str] = None

    class Config:
        orm_mode = True  # Для преобразования объекта SQLAlchemy в Pydantic
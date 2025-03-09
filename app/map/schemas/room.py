from pydantic import BaseModel, Field
from typing import List, Optional

class Coordinates(BaseModel):
    x: float
    y: float

class RoomBase(BaseModel):
    building_id: int
    floor_id: int
    name: str
    cab_id: str
    coordinates: Optional[List[Coordinates]] = Field(default=None)
    description: Optional[str] = None

class RoomCreate(RoomBase):
    image_path: Optional[str] = None

class RoomUpdate(RoomBase):
    building_id: Optional[int] = None
    floor_id: Optional[int] = None
    name: Optional[str] = None
    cab_id: Optional[str] = None
    coordinates: Optional[List[Coordinates]] = None
    description: Optional[str] = None
    image_path: Optional[str] = None

class RoomResponse(RoomBase):
    id: int
    image_path: Optional[str] = None

    class Config:
        from_attributes = True
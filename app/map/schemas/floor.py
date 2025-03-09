from pydantic import BaseModel
from typing import Optional

class FloorBase(BaseModel):
    building_id: int
    floor_number: int
    image_path: Optional[str] = None
    description: Optional[str] = None

class FloorCreate(FloorBase):
    pass

class FloorUpdate(BaseModel):
    building_id: Optional[int] = None
    floor_number: Optional[int] = None
    image_path: Optional[str] = None
    description: Optional[str] = None

    class Config:
        orm_mode = True

class FloorResponse(FloorBase):
    id: int
    image_path: Optional[str] = None

    class Config:
        orm_mode = True
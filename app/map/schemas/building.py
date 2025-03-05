from pydantic import BaseModel
from typing import Optional

class BuildingBase(BaseModel):
    campus_id: int
    name: str
    x: float
    y: float
    x_head: float
    y_head: float
    description: Optional[str] = None
    image_path: Optional[str] = None  # Путь к SVG-файлу

class BuildingCreate(BuildingBase):
    pass

class BuildingUpdate(BaseModel):
    campus_id: Optional[int] = None
    name: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    x_head: Optional[float] = None
    y_head: Optional[float] = None
    description: Optional[str] = None
    image_path: Optional[str] = None

class Building(BuildingBase):
    id: int

    class Config:
        orm_mode = True
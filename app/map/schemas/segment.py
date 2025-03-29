from pydantic import BaseModel, Field
from typing import List, Optional
from app.map.models.enums import ConnectionCreate, ConnectionResponse  # Импортируем перечисление типов соединений

class SegmentBase(BaseModel):
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    floor_id: int
    building_id: int

class SegmentCreate(SegmentBase):
    connections: List[ConnectionCreate] = Field(default_factory=list, description="Список соединений с другими сегментами")

class SegmentUpdate(BaseModel):
    start_x: Optional[float] = None
    start_y: Optional[float] = None
    end_x: Optional[float] = None
    end_y: Optional[float] = None
    floor_id: Optional[int] = None
    building_id: Optional[int] = None
    connections: Optional[List[ConnectionCreate]] = Field(default_factory=list, description="Список соединений с другими сегментами")

class Segment(SegmentBase):
    id: int
    connections: List[ConnectionResponse] = Field(default_factory=list, description="Список соединений с другими сегментами")

    class Config:
        from_attributes = True
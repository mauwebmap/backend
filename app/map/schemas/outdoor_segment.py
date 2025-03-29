from pydantic import BaseModel, Field
from typing import Optional, List
from app.map.schemas.connection import ConnectionCreate, ConnectionResponse

class OutdoorSegmentBase(BaseModel):
    type: str
    campus_id: int
    start_building_id: Optional[int] = None
    end_building_id: Optional[int] = None
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    weight: int

class OutdoorSegmentCreate(OutdoorSegmentBase):
    connections: List[ConnectionCreate] = Field(default_factory=list, description="Список соединений с другими уличными сегментами")

class OutdoorSegmentUpdate(BaseModel):
    type: Optional[str] = None
    campus_id: Optional[int] = None
    start_building_id: Optional[int] = None
    end_building_id: Optional[int] = None
    start_x: Optional[float] = None
    start_y: Optional[float] = None
    end_x: Optional[float] = None
    end_y: Optional[float] = None
    weight: Optional[int] = None
    connections: Optional[List[ConnectionCreate]] = Field(default_factory=list, description="Список соединений с другими уличными сегментами")

class OutdoorSegment(OutdoorSegmentBase):
    id: int
    connections: List[ConnectionResponse] = Field(default_factory=list, description="Список соединений с другими уличными сегментами")

    class Config:
        from_attributes = True
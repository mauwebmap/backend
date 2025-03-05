from pydantic import BaseModel
from typing import Optional

class SegmentBase(BaseModel):
    type: str
    building_id: int
    floor: int
    connection_type: str
    start_x: float
    start_y: float
    end_x: float
    end_y: float

class SegmentCreate(SegmentBase):
    pass

class SegmentUpdate(BaseModel):
    type: Optional[str] = None
    building_id: Optional[int] = None
    floor: Optional[int] = None
    connection_type: Optional[str] = None
    start_x: Optional[float] = None
    start_y: Optional[float] = None
    end_x: Optional[float] = None
    end_y: Optional[float] = None

class Segment(SegmentBase):
    id: int

    class Config:
        orm_mode = True
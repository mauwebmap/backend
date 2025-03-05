from pydantic import BaseModel
from typing import Optional

class OutdoorSegmentBase(BaseModel):
    type: str
    start_building_id: Optional[int] = None
    end_building_id: Optional[int] = None
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    weight: int

class OutdoorSegmentCreate(OutdoorSegmentBase):
    pass

class OutdoorSegmentUpdate(BaseModel):
    type: Optional[str] = None
    start_building_id: Optional[int] = None
    end_building_id: Optional[int] = None
    start_x: Optional[float] = None
    start_y: Optional[float] = None
    end_x: Optional[float] = None
    end_y: Optional[float] = None
    weight: Optional[int] = None

class OutdoorSegment(OutdoorSegmentBase):
    id: int

    class Config:
        orm_mode = True
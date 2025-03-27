from pydantic import BaseModel
from typing import Optional

class OutdoorSegmentBase(BaseModel):
    type: str
    campus_id: int
    start_building_id: Optional[int]
    end_building_id: Optional[int]
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    weight: int

class OutdoorSegmentCreate(OutdoorSegmentBase):
    pass

class OutdoorSegmentUpdate(BaseModel):
    type: Optional[str]
    campus_id: Optional[int]
    start_building_id: Optional[int]
    end_building_id: Optional[int]
    start_x: Optional[float]
    start_y: Optional[float]
    end_x: Optional[float]
    end_y: Optional[float]
    weight: Optional[int]

class OutdoorSegment(OutdoorSegmentBase):
    id: int

    class Config:
        from_attributes = True
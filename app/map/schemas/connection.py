from pydantic import BaseModel
from typing import Optional

class ConnectionBase(BaseModel):
    room_id: Optional[int] = None
    segment_id: Optional[int] = None
    type: str
    weight: int

class ConnectionCreate(ConnectionBase):
    pass

class ConnectionUpdate(BaseModel):
    room_id: Optional[int] = None
    segment_id: Optional[int] = None
    type: Optional[str] = None
    weight: Optional[int] = None

class Connection(ConnectionBase):
    id: int

    class Config:
        from_attributes = True
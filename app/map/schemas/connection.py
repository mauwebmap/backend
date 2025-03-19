from pydantic import BaseModel, Field
from typing import Optional

class ConnectionBase(BaseModel):
    room_id: Optional[int] = Field(None, description="ID комнаты, если соединение связано с комнатой")
    segment_id: Optional[int] = Field(None, description="ID сегмента, если соединение связано с сегментом")
    type: str = Field(..., description="Тип соединения (например, 'door', 'stair')")
    weight: int = Field(..., description="Вес соединения (например, время прохождения)")

class ConnectionCreate(ConnectionBase):
    pass

class ConnectionUpdate(BaseModel):
    room_id: Optional[int] = None
    segment_id: Optional[int] = None
    type: Optional[str] = None
    weight: Optional[int] = None

class ConnectionResponse(ConnectionBase):
    id: int = Field(..., description="Уникальный идентификатор соединения")

    class Config:
        from_attributes = True
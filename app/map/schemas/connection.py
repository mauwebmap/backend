from pydantic import BaseModel, Field
from typing import Optional

class ConnectionBase(BaseModel):
    room_id: Optional[int] = Field(None, description="ID комнаты, если соединение связано с комнатой")
    segment_id: Optional[int] = Field(None, description="ID коридора, если соединение связано с коридором")
    from_segment_id: Optional[int] = Field(None, description="ID начального коридора (если соединение между коридорами)")
    to_segment_id: Optional[int] = Field(None, description="ID конечного коридора (если соединение между коридорами)")
    from_outdoor_id: Optional[int] = Field(None, description="ID начального внешнего сегмента (если соединение с улицей)")
    to_outdoor_id: Optional[int] = Field(None, description="ID конечного внешнего сегмента (если соединение с улицей)")
    from_floor_id: Optional[int] = Field(None, description="ID начального этажа (если соединение между этажами)")
    to_floor_id: Optional[int] = Field(None, description="ID конечного этажа (если соединение между этажами)")
    type: Optional[str] = Field(None, description="Тип соединения (например, 'door', 'stairs', 'elevator')")
    weight: Optional[float] = Field(None, description="Вес соединения (например, время прохождения)")

class ConnectionCreate(ConnectionBase):
    pass

class ConnectionUpdate(BaseModel):
    room_id: Optional[int] = None
    segment_id: Optional[int] = None
    from_segment_id: Optional[int] = None
    to_segment_id: Optional[int] = None
    from_outdoor_id: Optional[int] = None
    to_outdoor_id: Optional[int] = None
    from_floor_id: Optional[int] = None
    to_floor_id: Optional[int] = None
    type: Optional[str] = None
    weight: Optional[float] = None

class ConnectionResponse(ConnectionBase):
    id: int = Field(..., description="Уникальный идентификатор соединения")

    class Config:
        from_attributes = True
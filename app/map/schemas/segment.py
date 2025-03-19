from pydantic import BaseModel, Field
from typing import List, Optional
from app.map.models.enums import ConnectionType  # Импортируем перечисление типов соединений

# Схема для создания соединений
class ConnectionCreate(BaseModel):
    type: ConnectionType = Field(..., description="Тип соединения (например, 'stairs', 'elevator')")
    weight: float = Field(..., description="Вес соединения (например, время прохождения)")
    to_segment_id: Optional[int] = Field(None, description="ID сегмента, куда ведет соединение")
    from_floor_id: Optional[int] = Field(None, description="ID этажа, откуда начинается соединение")
    to_floor_id: Optional[int] = Field(None, description="ID этажа, куда ведет соединение")

# Базовая схема для сегментов
class SegmentBase(BaseModel):
    start_x: float = Field(..., description="Координата X начала сегмента")
    start_y: float = Field(..., description="Координата Y начала сегмента")
    end_x: float = Field(..., description="Координата X конца сегмента")
    end_y: float = Field(..., description="Координата Y конца сегмента")
    floor_id: int = Field(..., description="ID этажа, к которому относится сегмент")
    building_id: int = Field(..., description="ID здания, к которому относится сегмент")

# Схема для создания сегмента
class SegmentCreate(SegmentBase):
    connections: List[ConnectionCreate] = Field([], description="Список соединений с другими сегментами или этажами")

# Схема для ответа
class SegmentResponse(SegmentBase):
    id: int = Field(..., description="Уникальный идентификатор сегмента")
    connections: List[ConnectionCreate] = Field([], description="Список соединений с другими сегментами или этажами")

    class Config:
        from_attributes = True
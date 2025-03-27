from pydantic import BaseModel, Field
from typing import List, Optional
from app.map.models.enums import ConnectionType  # Импортируем перечисление типов соединений

# Схема для создания соединений
class ConnectionCreate(BaseModel):
    segment_id: Optional[int] = Field(None, description="ID коридора, если соединение связано с коридором")
    from_floor_id: Optional[int] = Field(None, description="ID этажа, откуда начинается соединение")
    to_floor_id: Optional[int] = Field(None, description="ID этажа, куда ведет соединение")
    type: ConnectionType = Field(..., description="Тип соединения (например, 'stairs', 'elevator')")
    weight: float = Field(..., description="Вес соединения (например, время прохождения)")

# Базовая схема для этажей
class FloorBase(BaseModel):
    building_id: int = Field(..., description="ID здания, к которому относится этаж")
    floor_number: int = Field(..., description="Номер этажа")
    image_path: Optional[str] = Field(None, description="Путь к изображению этажа")
    description: Optional[str] = Field(None, description="Описание этажа")

# Схема для создания этажа
class FloorCreate(FloorBase):
    connections: List[ConnectionCreate] = Field([], description="Список соединений с другими этажами")

# Схема для обновления этажа
class FloorUpdate(FloorBase):
    building_id: Optional[int] = Field(None, description="ID здания, к которому относится этаж")
    floor_number: Optional[int] = Field(None, description="Номер этажа")
    image_path: Optional[str] = Field(None, description="Путь к изображению этажа")
    description: Optional[str] = Field(None, description="Описание этажа")
    connections: Optional[List[ConnectionCreate]] = Field(None, description="Список соединений с другими этажами")

# Схема для ответа
class FloorResponse(FloorBase):
    id: int = Field(..., description="Уникальный идентификатор этажа")
    connections: List[ConnectionCreate] = Field([], description="Список соединений с другими этажами")

    class Config:
        from_attributes = True

class FloorNumbersResponse(BaseModel):
    floor_numbers: List[int] = Field(..., description="Список уникальных номеров этажей в порядке возрастания")

    class Config:
        from_attributes = True
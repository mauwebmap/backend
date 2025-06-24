from pydantic import BaseModel, Field
from typing import List, Optional
from app.map.models.enums import ConnectionType

# Схема для координат
class Coordinates(BaseModel):
    x: float
    y: float

# Схема для создания соединений
class ConnectionCreate(BaseModel):
    segment_id: int = Field(..., description="ID коридора, с которым связана комната")
    type: ConnectionType = Field(..., description="Тип соединения (например, 'door', 'stairs')")
    weight: float = Field(..., description="Вес соединения (например, время прохождения)")

# Базовая схема для комнат
class RoomBase(BaseModel):
    building_id: int = Field(..., description="ID здания, к которому относится комната")
    name: str = Field(..., description="Название комнаты")
    cab_id: str = Field(..., description="Кабинетный номер")
    coordinates: Optional[List[Coordinates]] = Field(None, description="Координаты комнаты")
    cab_x: Optional[float] = Field(None, description="Координата X входа в кабинет")
    cab_y: Optional[float] = Field(None, description="Координата Y входа в кабинет")
    description: Optional[str] = Field(None, description="Описание комнаты")

# Схема для создания комнаты
class RoomCreate(RoomBase):
    floor_number: int = Field(..., description="Номер этажа, к которому относится комната")
    connections: List[ConnectionCreate] = Field([], description="Список соединений с коридорами")

# Схема для обновления комнаты
class RoomUpdate(RoomBase):
    building_id: Optional[int] = Field(None, description="ID здания, к которому относится комната")
    floor_number: Optional[int] = Field(None, description="Номер этажа, к которому относится комната")
    name: Optional[str] = Field(None, description="Название комнаты")
    cab_id: Optional[str] = Field(None, description="Кабинетный номер")
    coordinates: Optional[List[Coordinates]] = Field(None, description="Координаты комнаты")
    cab_x: Optional[float] = Field(None, description="Координата X входа в кабинет")
    cab_y: Optional[float] = Field(None, description="Координата Y входа в кабинет")
    description: Optional[str] = Field(None, description="Описание комнаты")
    connections: Optional[List[ConnectionCreate]] = Field(None, description="Список соединений с коридорами")

# Схема для ответа
class RoomResponse(RoomBase):
    id: int = Field(..., description="Уникальный идентификатор комнаты")
    floor_id: int = Field(..., description="ID этажа, к которому относится комната")
    floor_number: int = Field(..., description="Номер этажа, к которому относится комната")
    connections: List[ConnectionCreate] = Field([], description="Список соединений с коридорами")
    image_path: Optional[str] = Field(None, description="Путь к изображению комнаты")

    class Config:
        from_attributes = True

# Схема для поиска комнат
class RoomSearchResponse(BaseModel):
    id: int
    name: str
    cab_id: str
    building_id: int
    building_name: str
    floor_id: int
    floor_number: int
    cab_x: Optional[float] = None
    cab_y: Optional[float] = None
    description: Optional[str] = None
    image_path: Optional[str] = None

    class Config:
        from_attributes = True
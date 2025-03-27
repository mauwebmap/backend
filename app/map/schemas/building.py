from pydantic import BaseModel, Field
from typing import Optional

# Базовая схема для зданий
class BuildingBase(BaseModel):
    """
    Базовая схема для создания и чтения зданий.
    Содержит основные поля модели Building.
    """
    campus_id: int = Field(
        ...,
        description="ID кампуса, к которому относится здание"
    )
    name: str = Field(
        ...,
        max_length=255,
        description="Название здания (максимум 255 символов)"
    )
    x: float = Field(
        ...,
        description="Координата X входа (может быть любым числом)"
    )
    y: float = Field(
        ...,
        description="Координата Y входа (может быть любым числом)"
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Описание здания (необязательное, максимум 1000 символов)"
    )

# Схема для создания здания
class BuildingCreate(BuildingBase):
    """
    Схема для создания нового здания.
    Наследуется от BuildingBase.
    """
    pass

# Схема для обновления здания
class BuildingUpdate(BaseModel):
    """
    Схема для обновления существующего здания.
    Все поля опциональны.
    """
    campus_id: Optional[int] = Field(
        None,
        description="ID кампуса, к которому относится здание"
    )
    name: Optional[str] = Field(
        None,
        max_length=255,
        description="Новое название здания (максимум 255 символов)"
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Новое описание здания (необязательное, максимум 1000 символов)"
    )
    image_path: Optional[str] = Field(
        None,
        description="Путь к SVG-файлу здания (необязательное)"
    )

# Схема для ответа (чтение данных)
class BuildingResponse(BuildingBase):
    """
    Схема для возврата данных о здании.
    Добавлены поля id и image_path.
    """
    id: int = Field(..., description="Уникальный идентификатор здания")
    image_path: Optional[str] = Field(
        None,
        description="Путь к SVG-файлу здания (если загружен)"
    )

    class Config:
        from_attributes = True
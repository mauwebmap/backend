from pydantic import BaseModel, Field
from typing import Optional

class BuildingBase(BaseModel):
    campus_id: int = Field(..., description="ID кампуса, к которому относится здание")
    name: str = Field(..., max_length=255, description="Название здания")
    x: float = Field(..., description="Координата X входа")
    y: float = Field(..., description="Координата Y входа")
    x_head: float = Field(..., description="Координата X центра здания")
    y_head: float = Field(..., description="Координата Y центра здания")
    description: Optional[str] = Field(None, description="Описание здания")


class BuildingCreate(BuildingBase):
    pass


class BuildingUpdate(BuildingBase):
    pass


class BuildingResponse(BuildingBase):
    id: int
    image_path: Optional[str] = Field(None, description="Путь к SVG-файлу здания")

    class Config:
        orm_mode = True
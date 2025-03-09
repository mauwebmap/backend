from pydantic import BaseModel
from typing import Optional


class CampusBase(BaseModel):
    name: str
    description: Optional[str] = None


class CampusCreate(CampusBase):
    pass


class CampusUpdate(CampusBase):
    pass


class CampusResponse(CampusBase):
    id: int
    image_path: Optional[str]

    class Config:
        from_attributes = True
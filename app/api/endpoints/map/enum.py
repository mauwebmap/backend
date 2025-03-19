from fastapi import APIRouter
from typing import List
from app.map.models.enums import ConnectionType  # Импортируем перечисление типов соединений

router = APIRouter(prefix="/connection-types", tags=["Connection Types"])

@router.get("/", response_model=List[str])
def get_connection_types():
    """
    Получить список допустимых типов соединений.
    """
    return [type.value for type in ConnectionType]
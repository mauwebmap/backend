from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .utils.route_builder import build_route
from app.database.database import get_db

router = APIRouter(prefix="/routes", tags=["routes"])

@router.get("/find")
def find_route(
    start_building: str,
    start_floor: int,
    start_room: str,
    end_building: str,
    end_floor: int,
    end_room: str,
    db: Session = Depends(get_db)
):
    route = build_route(db, start_building, start_floor, start_room, end_building, end_floor, end_room)
    if "не найден" in route.lower():
        raise HTTPException(status_code=404, detail=route)
    return {"route": route}
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from app.map.crud.floor import get_floor, get_floors, create_floor, update_floor, delete_floor
from app.map.schemas.floor import Floor, FloorCreate, FloorUpdate
from app.database.database import get_db
import os

router = APIRouter(prefix="/floors", tags=["floors"])

@router.get("/{floor_id}", response_model=Floor)
def read_floor(floor_id: int, db: Session = Depends(get_db)):
    floor = get_floor(db, floor_id)
    if not floor: raise HTTPException(status_code=404, detail="Floor not found")
    return floor

@router.get("/", response_model=list[Floor])
def read_floors(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return get_floors(db, skip, limit)

@router.post("/", response_model=Floor)
async def create_floor_endpoint(floor: FloorCreate, svg_file: UploadFile = File(None), db: Session = Depends(get_db)):
    return await create_floor(db, floor, svg_file)

@router.put("/{floor_id}", response_model=Floor)
async def update_floor_endpoint(floor_id: int, floor: FloorUpdate, svg_file: UploadFile = File(None), db: Session = Depends(get_db)):
    updated_floor = await update_floor(db, floor_id, floor, svg_file)
    if not updated_floor: raise HTTPException(status_code=404, detail="Floor not found")
    return updated_floor

@router.delete("/{floor_id}", response_model=Floor)
def delete_floor_endpoint(floor_id: int, db: Session = Depends(get_db)):
    deleted_floor = delete_floor(db, floor_id)
    if not deleted_floor: raise HTTPException(status_code=404, detail="Floor not found")
    return deleted_floor

@router.get("/{floor_id}/svg")
async def get_floor_svg(floor_id: int, db: Session = Depends(get_db)):
    floor = get_floor(db, floor_id)
    if not floor or not floor.image_path: raise HTTPException(status_code=404, detail="SVG not found")
    if not os.path.exists(floor.image_path[1:]): raise HTTPException(status_code=404, detail="SVG file missing")
    return {"svg_url": floor.image_path}
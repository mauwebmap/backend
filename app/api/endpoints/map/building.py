from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from app.map.crud.building import get_building, get_buildings, create_building, update_building, delete_building
from app.map.schemas.building import Building, BuildingCreate, BuildingUpdate
from app.database.database import get_db
import os

router = APIRouter(prefix="/buildings", tags=["buildings"])

@router.get("/{building_id}", response_model=Building)
def read_building(building_id: int, db: Session = Depends(get_db)):
    building = get_building(db, building_id)
    if not building: raise HTTPException(status_code=404, detail="Building not found")
    return building

@router.get("/", response_model=list[Building])
def read_buildings(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return get_buildings(db, skip, limit)

@router.post("/", response_model=Building)
async def create_building_endpoint(building: BuildingCreate, svg_file: UploadFile = File(None), db: Session = Depends(get_db)):
    return await create_building(db, building, svg_file)

@router.put("/{building_id}", response_model=Building)
async def update_building_endpoint(building_id: int, building: BuildingUpdate, svg_file: UploadFile = File(None), db: Session = Depends(get_db)):
    updated_building = await update_building(db, building_id, building, svg_file)
    if not updated_building: raise HTTPException(status_code=404, detail="Building not found")
    return updated_building

@router.delete("/{building_id}", response_model=Building)
def delete_building_endpoint(building_id: int, db: Session = Depends(get_db)):
    deleted_building = delete_building(db, building_id)
    if not deleted_building: raise HTTPException(status_code=404, detail="Building not found")
    return deleted_building

@router.get("/{building_id}/svg")
async def get_building_svg(building_id: int, db: Session = Depends(get_db)):
    building = get_building(db, building_id)
    if not building or not building.image_path: raise HTTPException(status_code=404, detail="SVG not found")
    if not os.path.exists(building.image_path[1:]): raise HTTPException(status_code=404, detail="SVG file missing")
    return {"svg_url": building.image_path}
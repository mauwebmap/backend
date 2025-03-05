from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from app.map.crud.campus import get_campus, get_campuses, create_campus, update_campus, delete_campus
from app.map.schemas.campus import Campus, CampusCreate, CampusUpdate
from app.database.database import get_db
import os

router = APIRouter(prefix="/campuses", tags=["campuses"])

@router.get("/{campus_id}", response_model=Campus)
def read_campus(campus_id: int, db: Session = Depends(get_db)):
    campus = get_campus(db, campus_id)
    if not campus: raise HTTPException(status_code=404, detail="Campus not found")
    return campus

@router.get("/", response_model=list[Campus])
def read_campuses(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return get_campuses(db, skip, limit)

@router.post("/", response_model=Campus)
async def create_campus_endpoint(campus: CampusCreate, svg_file: UploadFile = File(None), db: Session = Depends(get_db)):
    return await create_campus(db, campus, svg_file)

@router.put("/{campus_id}", response_model=Campus)
async def update_campus_endpoint(campus_id: int, campus: CampusUpdate, svg_file: UploadFile = File(None), db: Session = Depends(get_db)):
    updated_campus = await update_campus(db, campus_id, campus, svg_file)
    if not updated_campus: raise HTTPException(status_code=404, detail="Campus not found")
    return updated_campus

@router.delete("/{campus_id}", response_model=Campus)
def delete_campus_endpoint(campus_id: int, db: Session = Depends(get_db)):
    deleted_campus = delete_campus(db, campus_id)
    if not deleted_campus: raise HTTPException(status_code=404, detail="Campus not found")
    return deleted_campus

@router.get("/{campus_id}/svg")
async def get_campus_svg(campus_id: int, db: Session = Depends(get_db)):
    campus = get_campus(db, campus_id)
    if not campus or not campus.image_path: raise HTTPException(status_code=404, detail="SVG not found")
    if not os.path.exists(campus.image_path[1:]): raise HTTPException(status_code=404, detail="SVG file missing")
    return {"svg_url": campus.image_path}
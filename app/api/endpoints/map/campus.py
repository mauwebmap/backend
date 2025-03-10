from fastapi import Depends, Form, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from app.database.database import get_db
from app.map.schemas.campus import CampusResponse
from app.map.crud.campus import get_all_campuses, get_campus, create_campus, update_campus, delete_campus
from app.users.dependencies.auth import admin_required
from fastapi import APIRouter

router = APIRouter(prefix="/campuses", tags=["Campuses"])

@router.get("/", response_model=list[CampusResponse])
def read_campuses(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return get_all_campuses(db, skip, limit)

@router.get("/{campus_id}", response_model=CampusResponse)
def read_campus(campus_id: int, db: Session = Depends(get_db)):
    campus = get_campus(db, campus_id)
    if not campus:
        raise HTTPException(status_code=404, detail="Campus not found")
    return campus

@router.post("/", response_model=CampusResponse, dependencies=[Depends(admin_required)])
async def create_campus_endpoint(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    svg_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    return await create_campus(db, name, description, svg_file)

@router.put("/{campus_id}", response_model=CampusResponse, dependencies=[Depends(admin_required)])
async def update_campus_endpoint(
    campus_id: int,
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    svg_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    update_data = {}
    if name:
        update_data["name"] = name
    if description:
        update_data["description"] = description

    return await update_campus(db, campus_id, update_data, svg_file)

@router.delete("/{campus_id}", response_model=CampusResponse, dependencies=[Depends(admin_required)])
def delete_campus_endpoint(campus_id: int, db: Session = Depends(get_db)):
    return delete_campus(db, campus_id)

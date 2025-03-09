from fastapi import Depends, Form, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from app.database.database import get_db
from app.map.schemas.campus import CampusResponse
from app.map.crud.campus import get_all_campuses, get_campus, create_campus, update_campus, delete_campus
from app.users.dependencies.auth import admin_required
from app.api.endpoints.base import SecureRouter, ProtectedMethodsRoute

router = SecureRouter(
    version=2,
    prefix="/campuses",
    tags=["Campuses"],
    route_class=ProtectedMethodsRoute,
    default_dependencies=[Depends(admin_required)]
)

@router.get("/", response_model=list[CampusResponse])
def read_campuses(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return get_all_campuses(db, skip, limit)

@router.get("/{campus_id}", response_model=CampusResponse)
def read_campus(campus_id: int, db: Session = Depends(get_db)):
    campus = get_campus(db, campus_id)
    if not campus:
        raise HTTPException(status_code=404, detail="Campus not found")
    return campus

@router.post("/", response_model=CampusResponse)
async def create_campus_endpoint(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    svg_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    try:
        return await create_campus(db, name, description, svg_file)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put("/{campus_id}", response_model=CampusResponse)
async def update_campus_endpoint(
    campus_id: int,
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    svg_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    update_data = {}
    if name is not None:
        update_data["name"] = name
    if description is not None:
        update_data["description"] = description
    file_to_process = svg_file if svg_file and svg_file.filename else None
    return await update_campus(db, campus_id, update_data, file_to_process)

@router.delete("/{campus_id}", response_model=CampusResponse)
def delete_campus_endpoint(
    campus_id: int,
    db: Session = Depends(get_db)
):
    deleted_campus = delete_campus(db, campus_id)
    if not deleted_campus:
        raise HTTPException(status_code=404, detail="Campus not found")
    return deleted_campus
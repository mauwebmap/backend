from fastapi import Depends, Form, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from app.database.database import get_db
from app.map.schemas.building import BuildingResponse
from app.map.crud.building import (
    get_all_buildings,
    get_building,
    create_building,
    update_building,
    delete_building
)
from app.users.dependencies.auth import admin_required
from app.api.endpoints.base import SecureRouter, ProtectedMethodsRoute

router = SecureRouter(
    version=2,
    prefix="/buildings",
    tags=["Buildings"],
    route_class=ProtectedMethodsRoute,
    default_dependencies=[Depends(admin_required)]
)

@router.get("/", response_model=list[BuildingResponse])
def read_buildings(
    campus_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Получить список всех зданий, опционально отфильтрованных по campus_id.
    """
    return get_all_buildings(db, campus_id=campus_id, skip=skip, limit=limit)

@router.get("/{building_id}", response_model=BuildingResponse)
def read_building(
    building_id: int,
    db: Session = Depends(get_db)
):
    """
    Получить информацию о здании по его ID.
    """
    building = get_building(db, building_id)
    if not building:
        raise HTTPException(status_code=404, detail="Building not found")
    return building

@router.post("/", response_model=BuildingResponse)
async def create_building_endpoint(
    campus_id: int = Form(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    svg_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """
    Создать новое здание в указанном кампусе.
    Требуются права администратора.
    """
    try:
        return await create_building(db, campus_id, name, description, svg_file)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put("/{building_id}", response_model=BuildingResponse)
async def update_building_endpoint(
    building_id: int,
    campus_id: Optional[int] = Form(None),
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    svg_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """
    Обновить информацию о здании.
    Требуются права администратора.
    """
    update_data = {}
    if campus_id is not None:
        update_data["campus_id"] = campus_id
    if name is not None:
        update_data["name"] = name
    if description is not None:
        update_data["description"] = description
    file_to_process = svg_file if svg_file and svg_file.filename else None
    try:
        updated_building = await update_building(db, building_id, update_data, file_to_process)
        if not updated_building:
            raise HTTPException(status_code=404, detail="Building not found")
        return updated_building
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete("/{building_id}", response_model=BuildingResponse)
def delete_building_endpoint(
    building_id: int,
    db: Session = Depends(get_db)
):
    """
    Удалить здание по его ID.
    Требуются права администратора.
    """
    deleted_building = delete_building(db, building_id)
    if not deleted_building:
        raise HTTPException(status_code=404, detail="Building not found")
    return deleted_building
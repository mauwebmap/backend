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
from fastapi import APIRouter

router = APIRouter(prefix="/buildings", tags=["Buildings"])


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


@router.post("/", response_model=BuildingResponse, dependencies=[Depends(admin_required)])
async def create_building_endpoint(
        campus_id: int = Form(...),
        name: str = Form(...),
        x: float = Form(..., description="Координата X входа"),
        y: float = Form(..., description="Координата Y входа"),
        x_head: float = Form(..., description="Координата X центра"),
        y_head: float = Form(..., description="Координата Y центра"),
        description: Optional[str] = Form(None),
        svg_file: Optional[UploadFile] = File(None),
        db: Session = Depends(get_db)
):
    """
    Создать новое здание в указанном кампусе.
    Требуются права администратора.
    """
    building_data = {
        "campus_id": campus_id,
        "name": name,
        "x": x,
        "y": y,
        "x_head": x_head,
        "y_head": y_head,
        "description": description
    }

    try:
        return await create_building(db, building_data, svg_file)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при создании здания: {str(e)}"
        )


@router.put("/{building_id}", response_model=BuildingResponse, dependencies=[Depends(admin_required)])
async def update_building_endpoint(
        building_id: int,
        campus_id: Optional[int] = Form(None),
        name: Optional[str] = Form(None),
        x: Optional[float] = Form(None),
        y: Optional[float] = Form(None),
        x_head: Optional[float] = Form(None),
        y_head: Optional[float] = Form(None),
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
    if x is not None:
        update_data["x"] = x
    if y is not None:
        update_data["y"] = y
    if x_head is not None:
        update_data["x_head"] = x_head
    if y_head is not None:
        update_data["y_head"] = y_head
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при обновлении здания: {str(e)}"
        )


@router.delete("/{building_id}", response_model=BuildingResponse, dependencies=[Depends(admin_required)])
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
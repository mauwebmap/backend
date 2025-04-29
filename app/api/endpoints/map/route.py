# app/api/endpoints/map/route.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.map.utils.pathfinder import find_path
from app.map.models.room import Room
from app.map.models.segment import Segment
from app.map.models.outdoor_segment import OutdoorSegment
from app.map.models.floor import Floor  # Добавляем импорт модели Floor
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/route", response_model=dict)
async def get_route(start: str, end: str, db: Session = Depends(get_db)):
    logger.info(f"Received request to find route from {start} to {end}")

    # Находим путь и граф
    path, weight, graph = find_path(db, start, end, return_graph=True)
    if not path:
        logger.warning("No path found")
        raise HTTPException(status_code=404, detail="Маршрут не найден")

    logger.info(f"A* result: path={path}, weight={weight}")

    # Преобразуем путь в формат для фронта
    route = []
    current_floor_number = None  # Изменяем на current_floor_number
    floor_points = []

    for vertex in path:
        try:
            # Разбираем вершину
            if vertex.startswith("phantom_"):
                # Обработка фантомной вершины
                parts = vertex.split("_")
                if len(parts) != 5 or parts[0] != "phantom" or parts[1] != "room" or parts[3] != "segment":
                    raise ValueError(f"Неверный формат фантомной вершины: {vertex}")

                # Извлекаем координаты из графа
                coords = graph.vertices[vertex]
                floor_id = coords[2]
                # Находим floor_number
                if floor_id != 0:  # Для уличных сегментов floor_id=0
                    floor = db.query(Floor).filter(Floor.id == floor_id).first()
                    if not floor:
                        raise ValueError(f"Этаж с id {floor_id} не найден")
                    floor_number = floor.floor_number
                else:
                    floor_number = 0  # Уличные сегменты остаются с номером 0
                logger.debug(
                    f"Processing phantom vertex {vertex}: floor_id={floor_id}, floor_number={floor_number}, coords={coords}")
            else:
                # Обычная вершина (room, segment, outdoor)
                vertex_type, vertex_id_part = vertex.split("_", 1)

                coords = None
                floor_id = None
                floor_number = None  # Добавляем floor_number
                if vertex_type == "room":
                    vertex_id = int(vertex_id_part)
                    room = db.query(Room).filter(Room.id == vertex_id).first()
                    if not room:
                        raise ValueError(f"Комната {vertex} не найдена")
                    coords = (room.cab_x, room.cab_y)
                    floor_id = room.floor_id
                    # Находим floor_number
                    floor = db.query(Floor).filter(Floor.id == floor_id).first()
                    if not floor:
                        raise ValueError(f"Этаж с id {floor_id} не найден")
                    floor_number = floor.floor_number
                elif vertex_type == "segment":
                    # Разбираем segment_X_start/end
                    segment_id_part, position = vertex_id_part.rsplit("_", 1)
                    segment_id = int(segment_id_part)
                    segment = db.query(Segment).filter(Segment.id == segment_id).first()
                    if not segment:
                        raise ValueError(f"Сегмент {vertex} не найден")
                    coords = (segment.start_x, segment.start_y) if position == "start" else (
                    segment.end_x, segment.end_y)
                    floor_id = segment.floor_id
                    # Находим floor_number
                    floor = db.query(Floor).filter(Floor.id == floor_id).first()
                    if not floor:
                        raise ValueError(f"Этаж с id {floor_id} не найден")
                    floor_number = floor.floor_number
                elif vertex_type == "outdoor":
                    # Разбираем outdoor_X_start/end
                    outdoor_id_part, position = vertex_id_part.rsplit("_", 1)
                    outdoor_id = int(outdoor_id_part)
                    outdoor = db.query(OutdoorSegment).filter(OutdoorSegment.id == outdoor_id).first()
                    if not outdoor:
                        raise ValueError(f"Уличный сегмент {vertex} не найден")
                    coords = (outdoor.start_x, outdoor.start_y) if position == "start" else (
                    outdoor.end_x, outdoor.end_y)
                    floor_id = 0  # Уличные сегменты на "нулевом" этаже
                    floor_number = 0  # Уличные сегменты остаются с номером 0
                else:
                    raise ValueError(f"Неизвестный тип вершины: {vertex_type}")

                logger.debug(
                    f"Processing vertex {vertex}: {vertex_type}, floor_id={floor_id}, floor_number={floor_number}")

            # Добавляем точку в маршрут
            if floor_number != current_floor_number:  # Сравниваем по floor_number
                if floor_points:
                    route.append({"floor": current_floor_number, "points": floor_points})
                floor_points = []
                current_floor_number = floor_number  # Обновляем current_floor_number

            floor_points.append({"x": coords[0], "y": coords[1]})
            logger.debug(f"Added point for vertex {vertex}: x={coords[0]}, y={coords[1]}")

        except Exception as e:
            logger.error(f"Error processing vertex {vertex}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Ошибка при обработке вершины {vertex}: {str(e)}")

    if floor_points:
        route.append({"floor": current_floor_number, "points": floor_points})

    return {"path": route, "weight": weight}
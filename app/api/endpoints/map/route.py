# app/api/endpoints/map/route.py
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.database.database import get_db
from app.map.utils.graph import Graph
from app.map.utils.pathfinder import a_star
from app.map.utils.builder import build_graph, parse_vertex_id
from app.map.models.floor import Floor
from app.map.models.room import Room
from app.map.models.segment import Segment

# Настройка логгера
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/route")
def get_route(start: str, end: str, db: Session = Depends(get_db)):
    """Получить маршрут от start до end (любые типы точек: room, segment, outdoor)."""
    logger.info(f"Received request to find route from {start} to {end}")
    try:
        # Парсинг начальной и конечной точек
        try:
            start_type, start_id = parse_vertex_id(start)
            end_type, end_id = parse_vertex_id(end)
            logger.debug(f"Parsed start: type={start_type}, id={start_id}")
            logger.debug(f"Parsed end: type={end_type}, id={end_id}")
        except ValueError as e:
            logger.error(f"Error parsing vertex IDs: {e}")
            raise HTTPException(status_code=400, detail=f"Ошибка парсинга ID: {e}")

        # Построение графа
        try:
            graph = build_graph(db, start, end)
            logger.info("Graph built successfully")
        except Exception as e:
            logger.error(f"Error building graph: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка при построении графа: {e}")

        # Обработка случая сегмента
        start_vertex = start if start_type != "segment" else f"segment_{start_id}_start"
        end_vertex = end if end_type != "segment" else f"segment_{end_id}_end"
        logger.debug(f"Start vertex: {start_vertex}")
        logger.debug(f"End vertex: {end_vertex}")

        # Проверка наличия вершин в графе
        if start_vertex not in graph.vertices or end_vertex not in graph.vertices:
            logger.error(f"Invalid start or end vertex: {start_vertex} or {end_vertex} not in graph")
            raise HTTPException(status_code=400, detail="Неверная начальная или конечная точка")

        # Поиск пути с помощью A*
        try:
            path, weight = a_star(graph, start_vertex, [end_vertex])
            logger.info(f"A* result: path={path}, weight={weight}")
        except Exception as e:
            logger.error(f"Error finding path with A*: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка при поиске пути: {e}")

        # Проверка, найден ли путь
        if not path:
            logger.warning("No path found")
            raise HTTPException(status_code=404, detail="Маршрут не найден")

        # Разделение пути по этажам
        path_by_floor = []
        current_floor = None
        current_points = []

        for vertex in path:
            try:
                floor_id = None
                if "room" in vertex:
                    room = db.query(Room).filter(Room.id == int(vertex.split('_')[1])).first()
                    floor_id = room.floor_id if room else None
                    logger.debug(f"Processing vertex {vertex}: room, floor_id={floor_id}")
                elif "segment" in vertex:
                    segment = db.query(Segment).filter(Segment.id == int(vertex.split('_')[1])).first()
                    floor_id = segment.floor_id if segment else None
                    logger.debug(f"Processing vertex {vertex}: segment, floor_id={floor_id}")
                elif "outdoor" in vertex:
                    floor_id = "outdoor"
                    logger.debug(f"Processing vertex {vertex}: outdoor, floor_id={floor_id}")

                if floor_id != current_floor:
                    if current_points:
                        floor_num = (
                            "outdoor"
                            if current_floor == "outdoor"
                            else db.query(Floor).filter(Floor.id == current_floor).first().floor_number
                            if current_floor else "unknown"
                        )
                        path_by_floor.append({"floor": floor_num, "points": current_points})
                        logger.debug(f"Added path segment for floor {floor_num}: {current_points}")
                    current_points = []
                    current_floor = floor_id

                coords = graph.vertices.get(vertex)
                if not coords:
                    logger.error(f"Vertex {vertex} not found in graph")
                    raise ValueError(f"Вершина {vertex} не найдена в графе")
                current_points.append({"x": coords[0], "y": coords[1]})
                logger.debug(f"Added point for vertex {vertex}: x={coords[0]}, y={coords[1]}")
            except SQLAlchemyError as e:
                logger.error(f"Database error while processing vertex {vertex}: {e}")
                raise HTTPException(status_code=500, detail=f"Ошибка при доступе к базе: {e}")
            except Exception as e:
                logger.error(f"Error processing vertex {vertex}: {e}")
                raise HTTPException(status_code=500, detail=f"Ошибка при обработке вершины {vertex}: {e}")

        if current_points:
            try:
                floor_num = (
                    "outdoor"
                    if current_floor == "outdoor"
                    else db.query(Floor).filter(Floor.id == current_floor).first().floor_number
                    if current_floor else "unknown"
                )
                path_by_floor.append({"floor": floor_num, "points": current_points})
                logger.debug(f"Added final path segment for floor {floor_num}: {current_points}")
            except SQLAlchemyError as e:
                logger.error(f"Database error while getting floor number: {e}")
                raise HTTPException(status_code=500, detail=f"Ошибка при получении номера этажа: {e}")

        logger.info(f"Route found: path={path_by_floor}, weight={weight}")
        return {"path": path_by_floor, "weight": weight}

    except HTTPException as http_exc:
        logger.error(f"HTTP exception: {http_exc.detail}")
        raise http_exc
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Произошла внутренняя ошибка сервера")
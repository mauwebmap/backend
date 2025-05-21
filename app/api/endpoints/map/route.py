# app/api/endpoints/map/route.py
from app.database.database import get_db
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.map.utils.pathfinder import find_path
from app.map.models.room import Room
from app.map.models.segment import Segment
from app.map.models.outdoor_segment import OutdoorSegment
from app.map.models.floor import Floor
from app.map.models.connection import Connection
import logging
from math import atan2, degrees

logger = logging.getLogger(__name__)

router = APIRouter()

def get_direction(prev_prev_coords: tuple, prev_coords: tuple, curr_coords: tuple, prev_direction: str = None,
                  initial_orientation: str = "вперёд", i: int = 0) -> str:
    """
    Определяет направление движения или поворот на основе смещения между последними двумя сегментами.
    prev_prev_coords: (x, y) - точка до предыдущей
    prev_coords: (x, y) - предыдущая точка
    curr_coords: (x, y) - текущая точка
    prev_direction: Предыдущее направление (для оптимизации поворотов)
    initial_orientation: Начальная ориентация (по умолчанию "вперёд")
    i: Индекс текущей вершины в пути
    Возвращает: "налево", "направо", "вперёд" или "назад" для движения, или поворот при изменении направления
    """
    # Вычисляем векторы для текущего сегмента
    curr_dx = curr_coords[0] - prev_coords[0]
    curr_dy = curr_coords[1] - prev_coords[1]

    # Если нет смещения в текущем сегменте, считаем, что идём "вперёд"
    if curr_dx == 0 and curr_dy == 0:
        return "вперёд"

    # Вычисляем угол для текущего сегмента
    curr_angle = degrees(atan2(curr_dy, curr_dx))
    curr_angle = ((curr_angle + 180) % 360) - 180

    # Базовое направление текущего сегмента
    if -45 <= curr_angle <= 45:
        base_direction = "направо"  # Движение вправо (x увеличивается)
    elif 45 < curr_angle <= 135:
        base_direction = "вперёд"   # Движение вверх (y увеличивается)
    elif 135 < curr_angle <= 180 or -180 <= curr_angle < -135:
        base_direction = "налево"   # Движение влево (x уменьшается)
    else:
        base_direction = "назад"    # Движение вниз (y уменьшается)

    # Корректировка для начальной ориентации (только для первого поворота)
    if i == 1 and initial_orientation == "налево" and base_direction == "направо":
        base_direction = "налево"
    elif i == 1 and initial_orientation == "налево" and base_direction == "назад":
        base_direction = "направо"

    # Если это первый или второй сегмент (prev_prev_coords is None), возвращаем базовое направление
    if prev_prev_coords is None:
        return base_direction

    # Вычисляем векторы для предыдущего сегмента
    prev_dx = prev_coords[0] - prev_prev_coords[0]
    prev_dy = prev_coords[1] - prev_prev_coords[1]

    # Вычисляем угол для предыдущего сегмента
    prev_angle = degrees(atan2(prev_dy, prev_dx)) if (prev_dx != 0 or prev_dy != 0) else curr_angle
    prev_angle = ((prev_angle + 180) % 360) - 180

    # Определяем поворот
    angle_diff = curr_angle - prev_angle
    angle_diff = ((angle_diff + 180) % 360) - 180  # Нормализация разницы углов
    if abs(angle_diff) > 10:  # Порог для игнорирования мелких изменений (в градусах)
        if -180 < angle_diff <= -10:
            return "поверните налево"  # Против часовой стрелки
        elif 10 <= angle_diff < 180:
            return "поверните направо"  # По часовой стрелке

    # Если нет значительного поворота, возвращаем базовое направление
    return base_direction

def get_vertex_details(vertex: str, db: Session) -> tuple:
    """
    Возвращает читаемое имя вершины и её номер (если есть).
    Возвращает: (имя, номер)
    """
    vertex_type, vertex_id = vertex.split("_", 1)
    if vertex_type == "room":
        room = db.query(Room).filter(Room.id == int(vertex_id)).first()
        if room:
            return room.name, room.cab_id
        return vertex, None
    elif vertex_type == "segment":
        return "лестницы", None if "_end" in vertex or "_start" in vertex else vertex_id
    elif vertex_type == "outdoor":
        return f"Уличный сегмент {vertex_id}", None
    elif vertex_type == "phantom":
        parts = vertex_id.split("_")
        room_id = parts[1]
        room = db.query(Room).filter(Room.id == int(room_id)).first()
        return f"Фантомная точка у {room.name if room else 'комнаты'}", None
    return vertex, None

def generate_text_instructions(path: list, graph: dict, db: Session) -> list:
    """
    Генерирует текстовое описание пути в виде массива строк.
    path: Список вершин маршрута
    graph: Граф с координатами вершин
    db: Сессия базы данных
    Возвращает: Список инструкций (каждая строка — отдельный шаг)
    """
    instructions = []
    prev_prev_coords = None
    prev_coords = None
    prev_vertex = None
    prev_direction = None
    prev_floor = None
    current_instruction = []
    last_turn = None

    for i, vertex in enumerate(path):
        # Получаем координаты текущей вершины
        coords = graph.vertices[vertex]
        floor_id = coords[2]

        # Определяем этаж
        if floor_id != 0:
            floor = db.query(Floor).filter(Floor.id == floor_id).first()
            floor_number = floor.floor_number if floor else floor_id
        else:
            floor_number = 0

        # Получаем читаемое имя вершины и её номер
        vertex_name, vertex_number = get_vertex_details(vertex, db)

        # Начало маршрута
        if i == 0:
            current_instruction.append(f"При выходе из {vertex_name}")
            prev_coords = (coords[0], coords[1])
            prev_vertex = vertex
            prev_floor = floor_number
            continue

        # Проверяем переход между этажами
        if prev_floor is not None and prev_floor != floor_number and i > 1:
            if current_instruction:
                if last_turn and "поверните" in last_turn.lower():
                    instructions.append(" ".join([current_instruction[0], last_turn]))
                else:
                    instructions.append(" ".join(current_instruction))
                current_instruction = []

            # Ищем соединение типа "лестница"
            prev_segment_id = int(prev_vertex.split("_")[1]) if prev_vertex.startswith("segment_") else None
            curr_segment_id = int(vertex.split("_")[1]) if vertex.startswith("segment_") else None
            if prev_segment_id and curr_segment_id:
                connection = db.query(Connection).filter(
                    Connection.type == "лестница",
                    ((Connection.from_segment_id == prev_segment_id) & (Connection.to_segment_id == curr_segment_id)) |
                    ((Connection.from_segment_id == curr_segment_id) & (Connection.to_segment_id == prev_segment_id))
                ).first()
                if connection:
                    if prev_floor < floor_number:
                        instructions.append(f"Дойдите до лестницы и поднимитесь на {floor_number}-й этаж")
                    else:
                        instructions.append(f"Дойдите до лестницы и спуститесь на {floor_number}-й этаж")
            prev_direction = None
            prev_prev_coords = None
            last_turn = None

        # Определяем направление или поворот
        if prev_coords:
            direction = get_direction(prev_prev_coords, prev_coords, (coords[0], coords[1]), prev_direction,
                                      initial_orientation="налево" if i == 1 else None, i=i)
            if direction.startswith("поверните"):
                last_turn = direction
                if current_instruction and current_instruction[-1] in ["налево", "направо", "вперёд", "назад"]:
                    current_instruction.pop()
                if not current_instruction:
                    current_instruction.append("")  # Placeholder
                current_instruction.append(direction)
            elif direction != "вперёд":
                if not last_turn:
                    if not current_instruction:
                        current_instruction.append("")  # Placeholder
                    current_instruction.append(direction)
            prev_direction = direction if not direction.startswith("поверните") else prev_direction

        # Если это последняя точка, указываем пункт назначения
        if i == len(path) - 1:
            destination = f"{vertex_name} номер {vertex_number}" if vertex_number else vertex_name
            if last_turn and "поверните" in last_turn.lower():
                current_instruction = [current_instruction[0] if current_instruction else "", last_turn]
                current_instruction.append(f"и пройдите вперёд до {destination}")
            else:
                current_instruction = [current_instruction[0] if current_instruction else ""]
                current_instruction.append(f"пройдите вперёд до {destination}")
            instructions.append(" ".join(filter(None, current_instruction)))

        prev_prev_coords = prev_coords
        prev_coords = (coords[0], coords[1])
        prev_floor = floor_number
        prev_vertex = vertex

    return instructions

@router.get("/route", response_model=dict)
async def get_route(start: str, end: str, db: Session = Depends(get_db)):
    logger.info(f"Received request to find route from {start} to {end}")

    # Находим путь, граф и все ребра
    path, weight, graph, all_edges = find_path(db, start, end, return_graph=True, return_all_edges=True)
    if not path:
        logger.warning("No path found")
        raise HTTPException(status_code=404, detail="Маршрут не найден")

    logger.info(f"A* result: path={path}, weight={weight}")

    # Генерируем текстовые инструкции
    instructions = generate_text_instructions(path, graph, db)

    # Преобразуем путь в формат для фронта
    route = []
    current_floor_number = None
    floor_points = []
    added_points = set()  # Для избежания дубликатов

    for i, vertex in enumerate(path):
        try:
            # Разбираем вершину
            coords = graph.vertices[vertex]
            floor_id = coords[2]
            if floor_id != 0:
                floor = db.query(Floor).filter(Floor.id == floor_id).first()
                floor_number = floor.floor_number if floor else floor_id
            else:
                floor_number = 0

            # Формируем точку
            point = {"x": coords[0], "y": coords[1]}
            point_tuple = (coords[0], coords[1])

            # Проверяем смена этажа
            if current_floor_number is None:
                current_floor_number = floor_number
                if point_tuple not in added_points:
                    floor_points.append(point)
                    added_points.add(point_tuple)
            elif floor_number != current_floor_number:
                if floor_points:
                    route.append({"floor": current_floor_number, "points": floor_points})
                added_points.clear()
                floor_points = [point] if point_tuple not in added_points else []
                added_points.add(point_tuple)
                current_floor_number = floor_number
            else:
                if point_tuple not in added_points:
                    floor_points.append(point)
                    added_points.add(point_tuple)

        except Exception as e:
            logger.error(f"Error processing vertex {vertex}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Ошибка при обработке вершины {vertex}: {str(e)}")

    if floor_points:
        route.append({"floor": current_floor_number, "points": floor_points})

    # Добавляем все ребра для отображения линий
    all_lines = [{"from": edge[0], "to": edge[1], "weight": edge[2]} for edge in all_edges]

    # Добавляем текстовые инструкции и все линии в ответ
    return {
        "path": route,
        "weight": weight,
        "instructions": instructions,
        "all_lines": all_lines
    }
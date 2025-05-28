import logging
from app.database.models import Vertex, Edge
from app.map.graph import Graph

logger = logging.getLogger(__name__)


def build_graph(db, start_vertex, end_vertex):
    logger.info(f"Начало построения графа для start={start_vertex}, end={end_vertex}")

    graph = Graph()

    # Получаем этажи и здания для начальной и конечной вершины
    start_data = db.query(Vertex).filter(Vertex.name == start_vertex).first()
    end_data = db.query(Vertex).filter(Vertex.name == end_vertex).first()

    if not start_data or not end_data:
        raise ValueError(f"Вершина {start_vertex} или {end_vertex} не найдена в базе данных")

    start_floor = start_data.floor_id
    end_floor = end_data.floor_id
    logger.info(f"Назначен номер этажа: {start_vertex}={start_floor}, {end_vertex}={end_floor}")

    building_ids = {start_data.building_id, end_data.building_id}
    floor_ids = {start_floor, end_floor}
    logger.info(f"Актуальные ID зданий: {building_ids}")
    logger.info(f"Актуальные ID этажей: {floor_ids}")

    # Получаем все вершины и рёбра
    vertices = db.query(Vertex).filter(Vertex.building_id.in_(building_ids)).all()
    edges = db.query(Edge).filter(
        Edge.from_vertex_id.in_([v.id for v in vertices]) &
        Edge.to_vertex_id.in_([v.id for v in vertices])
    ).all()

    # Объединяем парные лестничные вершины
    vertex_map = {}  # Для хранения объединённых вершин
    for vertex in vertices:
        name = vertex.name
        if name.startswith("phantom_stair_"):
            # Ищем парную вершину (например, phantom_stair_6_to_1 и phantom_stair_1_from_6)
            parts = name.split("_")
            if "to" in parts:
                from_floor, to_floor = parts[2], parts[4]
                paired_name = f"phantom_stair_{to_floor}_from_{from_floor}"
                canonical_name = f"phantom_stair_{from_floor}_to_{to_floor}"
                vertex_map[name] = canonical_name
                vertex_map[paired_name] = canonical_name
            elif "from" in parts:
                to_floor, from_floor = parts[2], parts[4]
                paired_name = f"phantom_stair_{from_floor}_to_{to_floor}"
                canonical_name = f"phantom_stair_{from_floor}_to_{to_floor}"
                vertex_map[name] = canonical_name
                vertex_map[paired_name] = canonical_name

    # Добавляем вершины в граф
    for vertex in vertices:
        name = vertex.name
        # Если вершина лестничная, используем каноническое имя
        if name in vertex_map:
            name = vertex_map[name]
            # Используем координаты вершины "to"
            original_name = next(v.name for v in vertices if v.name == name)
            vertex_data = next(v for v in vertices if v.name == original_name)
        else:
            vertex_data = vertex

        coords = (vertex_data.x, vertex_data.y, vertex_data.floor_id)
        graph.add_vertex(name, {"coords": coords})

    # Добавляем рёбра с фильтрацией
    for edge in edges:
        from_vertex = next(v for v in vertices if v.id == edge.from_vertex_id)
        to_vertex = next(v for v in vertices if v.id == edge.to_vertex_id)

        from_name = from_vertex.name
        to_name = to_vertex.name

        # Применяем маппинг для лестничных вершин
        if from_name in vertex_map:
            from_name = vertex_map[from_name]
        if to_name in vertex_map:
            to_name = vertex_map[to_name]

        # Пропускаем рёбра, ведущие к "end" вершинам, если это не переход "улица-дверь", "дверь-улица" или лестница
        if to_name.endswith("_end"):
            if not (from_name.startswith("phantom_segment") or to_name.startswith("phantom_segment") or
                    from_name.startswith("phantom_stair") or to_name.startswith("phantom_stair")):
                continue

        weight = edge.weight
        edge_type = edge.type if hasattr(edge, "type") else "unknown"
        graph.add_edge(from_name, to_name, weight, {"type": edge_type})

    logger.info(f"Граф успешно построен с {len(graph.vertices)} вершинами и {len(graph.edges)} рёбрами")
    return graph
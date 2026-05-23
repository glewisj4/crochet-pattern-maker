"""Shape fitting helpers for segmented color regions."""

from math import sqrt
from collections import deque


def contour_from_component(
    component: set[tuple[int, int]],
    scale: float,
    max_points: int = 96,
) -> tuple[tuple[float, float], ...]:
    boundary = []
    for x, y in component:
        if any(neighbor not in component for neighbor in _neighbors4(x, y)):
            boundary.append((x / scale, y / scale))

    if not boundary:
        return ()

    cx = sum(point[0] for point in boundary) / len(boundary)
    cy = sum(point[1] for point in boundary) / len(boundary)
    ordered = sorted(boundary, key=lambda point: _angle_key(point, cx, cy))
    if len(ordered) <= max_points:
        return tuple(ordered)

    stride = len(ordered) / max_points
    return tuple(ordered[int(index * stride)] for index in range(max_points))


def major_axis_from_component(
    component: set[tuple[int, int]],
    scale: float,
) -> tuple[tuple[float, float], tuple[float, float]]:
    points = [(x / scale, y / scale) for x, y in component]
    cx = sum(point[0] for point in points) / len(points)
    cy = sum(point[1] for point in points) / len(points)
    cov_xx = sum((x - cx) ** 2 for x, _y in points) / len(points)
    cov_yy = sum((y - cy) ** 2 for _x, y in points) / len(points)
    cov_xy = sum((x - cx) * (y - cy) for x, y in points) / len(points)

    if abs(cov_xy) < 1e-6 and cov_xx >= cov_yy:
        direction = (1.0, 0.0)
    elif abs(cov_xy) < 1e-6:
        direction = (0.0, 1.0)
    else:
        trace = cov_xx + cov_yy
        determinant = cov_xx * cov_yy - cov_xy * cov_xy
        eigenvalue = trace / 2 + sqrt(max(0.0, (trace / 2) ** 2 - determinant))
        direction = _normalize((eigenvalue - cov_yy, cov_xy))

    projections = [(x - cx) * direction[0] + (y - cy) * direction[1] for x, y in points]
    min_projection = min(projections)
    max_projection = max(projections)
    start = (cx + direction[0] * min_projection, cy + direction[1] * min_projection)
    end = (cx + direction[0] * max_projection, cy + direction[1] * max_projection)
    return _order_top_left(start, end)


def median_thickness_from_component(
    component: set[tuple[int, int]],
    scale: float,
) -> float:
    rows: dict[int, list[int]] = {}
    cols: dict[int, list[int]] = {}
    for x, y in component:
        rows.setdefault(y, []).append(x)
        cols.setdefault(x, []).append(y)

    runs = []
    for xs in rows.values():
        if len(xs) > 1:
            runs.append((max(xs) - min(xs) + 1) / scale)
    for ys in cols.values():
        if len(ys) > 1:
            runs.append((max(ys) - min(ys) + 1) / scale)

    if not runs:
        return 1.0
    runs.sort()
    middle = len(runs) // 2
    if len(runs) % 2:
        return runs[middle]
    return (runs[middle - 1] + runs[middle]) / 2


def segment_axis(
    axis: tuple[tuple[float, float], tuple[float, float]],
    max_segment_length: float,
) -> tuple[tuple[tuple[float, float], tuple[float, float]], ...]:
    start, end = axis
    length = _distance(start, end)
    if length <= 0:
        return ()
    count = max(1, round(length / max_segment_length))
    segments = []
    for index in range(count):
        t0 = index / count
        t1 = (index + 1) / count
        segments.append((_lerp(start, end, t0), _lerp(start, end, t1)))
    return tuple(segments)


def centerline_from_component(
    component: set[tuple[int, int]],
    scale: float,
    max_points: int = 18,
) -> tuple[tuple[float, float], ...]:
    """Extract a lightweight medial path from a binary component.

    This uses iterative thinning plus graph longest-path selection. It is not a
    full OpenCV-quality skeletonizer, but it handles clean illustrated limbs
    well enough to avoid bbox/straight-axis overfitting.
    """

    if not component:
        return ()
    skeleton = _thin(component)
    if not skeleton:
        return ()
    path = _longest_skeleton_path(skeleton)
    if len(path) < 2:
        return tuple((x / scale, y / scale) for x, y in path)
    simplified = _sample_path(path, max_points)
    return tuple((x / scale, y / scale) for x, y in simplified)


def _neighbors4(x: int, y: int) -> tuple[tuple[int, int], ...]:
    return ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))


def _neighbors8(x: int, y: int) -> tuple[tuple[int, int], ...]:
    return (
        (x, y - 1),
        (x + 1, y - 1),
        (x + 1, y),
        (x + 1, y + 1),
        (x, y + 1),
        (x - 1, y + 1),
        (x - 1, y),
        (x - 1, y - 1),
    )


def _thin(component: set[tuple[int, int]]) -> set[tuple[int, int]]:
    pixels = set(component)
    changed = True
    iterations = 0
    while changed and iterations < 80:
        changed = False
        iterations += 1
        for step in (0, 1):
            removable = []
            for point in pixels:
                x, y = point
                neighbors = [neighbor in pixels for neighbor in _neighbors8(x, y)]
                count = sum(neighbors)
                if count < 2 or count > 6:
                    continue
                transitions = sum(
                    1
                    for index in range(8)
                    if not neighbors[index] and neighbors[(index + 1) % 8]
                )
                if transitions != 1:
                    continue
                p2, p4, p6, p8 = neighbors[0], neighbors[2], neighbors[4], neighbors[6]
                if step == 0:
                    if p2 and p4 and p6:
                        continue
                    if p4 and p6 and p8:
                        continue
                else:
                    if p2 and p4 and p8:
                        continue
                    if p2 and p6 and p8:
                        continue
                removable.append(point)
            if removable:
                pixels.difference_update(removable)
                changed = True
    return pixels


def _longest_skeleton_path(skeleton: set[tuple[int, int]]) -> list[tuple[int, int]]:
    nodes = sorted(skeleton)
    endpoints = [
        point
        for point in nodes
        if sum(1 for neighbor in _neighbors8(*point) if neighbor in skeleton) <= 1
    ]
    candidates = endpoints or nodes
    start = _farthest_node(candidates[0], skeleton)[0]
    end, parents = _farthest_node(start, skeleton)
    return _reconstruct_path(start, end, parents)


def _farthest_node(
    start: tuple[int, int],
    skeleton: set[tuple[int, int]],
) -> tuple[tuple[int, int], dict[tuple[int, int], tuple[int, int] | None]]:
    parents: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    queue = deque([start])
    last = start
    while queue:
        current = queue.popleft()
        last = current
        for neighbor in _neighbors8(*current):
            if neighbor in skeleton and neighbor not in parents:
                parents[neighbor] = current
                queue.append(neighbor)
    return last, parents


def _reconstruct_path(
    start: tuple[int, int],
    end: tuple[int, int],
    parents: dict[tuple[int, int], tuple[int, int] | None],
) -> list[tuple[int, int]]:
    path = [end]
    current = end
    while current != start and parents.get(current) is not None:
        current = parents[current]  # type: ignore[assignment]
        path.append(current)
    path.reverse()
    return path


def _sample_path(path: list[tuple[int, int]], max_points: int) -> list[tuple[int, int]]:
    if len(path) <= max_points:
        return path
    stride = (len(path) - 1) / (max_points - 1)
    return [path[round(index * stride)] for index in range(max_points)]


def _angle_key(point: tuple[float, float], cx: float, cy: float) -> float:
    # Avoid importing atan2 for ordering-only use; quadrant-aware slope key is enough.
    x, y = point
    dx = x - cx
    dy = y - cy
    if dx >= 0 and dy < 0:
        quadrant = 0
    elif dx >= 0 and dy >= 0:
        quadrant = 1
    elif dx < 0 and dy >= 0:
        quadrant = 2
    else:
        quadrant = 3
    return quadrant * 10_000 + (dy / (abs(dx) + 1e-6))


def _normalize(vector: tuple[float, float]) -> tuple[float, float]:
    length = _distance((0, 0), vector)
    if length == 0:
        return (1.0, 0.0)
    return vector[0] / length, vector[1] / length


def _order_top_left(
    a: tuple[float, float],
    b: tuple[float, float],
) -> tuple[tuple[float, float], tuple[float, float]]:
    if (a[1], a[0]) <= (b[1], b[0]):
        return a, b
    return b, a


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def _lerp(
    a: tuple[float, float],
    b: tuple[float, float],
    t: float,
) -> tuple[float, float]:
    return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t

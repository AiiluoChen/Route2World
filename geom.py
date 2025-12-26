from __future__ import annotations

from dataclasses import dataclass
import math

from mathutils import Vector


@dataclass(frozen=True)
class Bounds2D:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def expand(self, margin: float) -> "Bounds2D":
        return Bounds2D(
            min_x=self.min_x - margin,
            min_y=self.min_y - margin,
            max_x=self.max_x + margin,
            max_y=self.max_y + margin,
        )

    def expand_xy(self, margin_x: float, margin_y: float) -> "Bounds2D":
        return Bounds2D(
            min_x=self.min_x - margin_x,
            min_y=self.min_y - margin_y,
            max_x=self.max_x + margin_x,
            max_y=self.max_y + margin_y,
        )

    @property
    def size_x(self) -> float:
        return self.max_x - self.min_x

    @property
    def size_y(self) -> float:
        return self.max_y - self.min_y


def bounds_from_points_xy(points: list[Vector]) -> Bounds2D:
    if not points:
        return Bounds2D(0.0, 0.0, 0.0, 0.0)
    min_x = min(p.x for p in points)
    max_x = max(p.x for p in points)
    min_y = min(p.y for p in points)
    max_y = max(p.y for p in points)
    return Bounds2D(min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y)


def closest_point_on_segment_2d(p: Vector, a: Vector, b: Vector) -> tuple[Vector, float]:
    ab = Vector((b.x - a.x, b.y - a.y))
    ap = Vector((p.x - a.x, p.y - a.y))
    denom = ab.length_squared
    if denom <= 1e-12:
        return Vector((a.x, a.y)), 0.0
    t = max(0.0, min(1.0, ap.dot(ab) / denom))
    q = Vector((a.x + ab.x * t, a.y + ab.y * t))
    return q, t


def smoothstep01(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge0 == edge1:
        return 0.0 if x < edge0 else 1.0
    t = (x - edge0) / (edge1 - edge0)
    return smoothstep01(t)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t

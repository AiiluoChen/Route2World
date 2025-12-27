from __future__ import annotations

from dataclasses import dataclass
import math
import xml.etree.ElementTree as etree
from typing import Iterable

from mathutils import Vector


EARTH_RADIUS_M = 6378137.0


@dataclass(frozen=True)
class GeoPoint:
    lat: float
    lon: float
    ele: float


def parse_gpx_track(filepath: str) -> list[GeoPoint]:
    root = etree.parse(filepath).getroot()

    points: list[GeoPoint] = []
    for e1 in root:
        if e1.tag[e1.tag.find("}") + 1 :] != "trk":
            continue
        for e2 in e1:
            if e2.tag[e2.tag.find("}") + 1 :] != "trkseg":
                continue
            for e3 in e2:
                if e3.tag[e3.tag.find("}") + 1 :] != "trkpt":
                    continue
                lat = float(e3.attrib["lat"])
                lon = float(e3.attrib["lon"])
                ele = 0.0
                for e4 in e3:
                    if e4.tag[e4.tag.find("}") + 1 :] == "ele" and e4.text:
                        try:
                            ele = float(e4.text)
                        except Exception:
                            ele = 0.0
                        break
                points.append(GeoPoint(lat=lat, lon=lon, ele=ele))
    return points


def project_to_local_meters(points: Iterable[GeoPoint]) -> list[Vector]:
    pts = list(points)
    if not pts:
        return []

    lat0 = math.radians(pts[0].lat)
    lon0 = math.radians(pts[0].lon)
    cos_lat0 = math.cos(lat0)

    out: list[Vector] = []
    for p in pts:
        lat = math.radians(p.lat)
        lon = math.radians(p.lon)
        x = (lon - lon0) * cos_lat0 * EARTH_RADIUS_M
        y = (lat - lat0) * EARTH_RADIUS_M
        out.append(Vector((x, y, p.ele)))
    return out


def simplify_polyline(points: list[Vector], min_step_m: float) -> list[Vector]:
    if min_step_m <= 0.0 or len(points) <= 2:
        return points[:]

    out = [points[0]]
    last = points[0]
    min_step_sq = min_step_m * min_step_m
    for p in points[1:]:
        if (p - last).length_squared >= min_step_sq:
            out.append(p)
            last = p
    if (out[-1] - points[-1]).length_squared > 0.000001:
        out.append(points[-1])
    return out


def simplify_polyline_xy(points: list[Vector], min_step_m: float) -> list[Vector]:
    if min_step_m <= 0.0 or len(points) <= 2:
        return points[:]

    out = [points[0]]
    last = points[0]
    min_step_sq = float(min_step_m) * float(min_step_m)
    for p in points[1:]:
        dx = float(p.x - last.x)
        dy = float(p.y - last.y)
        if dx * dx + dy * dy >= min_step_sq:
            out.append(p)
            last = p
    dx = float(out[-1].x - points[-1].x)
    dy = float(out[-1].y - points[-1].y)
    if dx * dx + dy * dy > 0.000001:
        out.append(points[-1])
    return out


def smooth_polyline(points: list[Vector], window_size: int = 1, iterations: int = 1) -> list[Vector]:
    if window_size < 1 or iterations < 1 or len(points) < 3:
        return points[:]

    # Use a separate buffer for reading/writing to avoid bias
    current_points = points[:]
    
    for _ in range(iterations):
        next_points = current_points[:]
        length = len(current_points)
        
        for i in range(1, length - 1):
            # Determine window bounds
            start_idx = max(0, i - window_size)
            end_idx = min(length, i + window_size + 1)
            
            # Compute average
            sum_vec = Vector((0.0, 0.0, 0.0))
            count = 0
            for k in range(start_idx, end_idx):
                sum_vec += current_points[k]
                count += 1
            
            if count > 0:
                next_points[i] = sum_vec / count
                
        current_points = next_points

    return current_points

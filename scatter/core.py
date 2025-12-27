from __future__ import annotations

import math
import os
import random
from dataclasses import dataclass
from typing import Iterable

import bpy
from mathutils import Euler, Vector
from mathutils.bvhtree import BVHTree

from .gn import (
    ATTR_CATEGORY,
    ATTR_PROTO_INDEX,
    ATTR_ROT_Z,
    ATTR_SCALE,
    apply_scatter_instances_modifier,
    build_category_library,
)


def _addon_source_dir() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "models")


def _ensure_collection(name: str, parent: bpy.types.Collection | None = None) -> bpy.types.Collection:
    c = bpy.data.collections.get(name)
    if c:
        return c
    c = bpy.data.collections.new(name)
    if parent is None:
        bpy.context.scene.collection.children.link(c)
    else:
        parent.children.link(c)
    return c


def _hide_collection(c: bpy.types.Collection) -> None:
    c.hide_select = True


def _unhide_collection_tree(c: bpy.types.Collection) -> None:
    c.hide_viewport = False
    c.hide_render = False
    for child in c.children:
        _unhide_collection_tree(child)


def _walk_hierarchy(root: bpy.types.Object) -> Iterable[bpy.types.Object]:
    stack = [root]
    while stack:
        ob = stack.pop()
        yield ob
        stack.extend(list(ob.children))


def _ensure_asset_library() -> bpy.types.Collection:
    lib = _ensure_collection("RWB_AssetLibrary")
    _unhide_collection_tree(lib)
    _hide_collection(lib)
    return lib


def _normalize_imported_objects(new_objects: list[bpy.types.Object]) -> None:
    if not new_objects:
        return
    new_set = set(new_objects)
    roots = [ob for ob in new_objects if ob.parent is None or ob.parent not in new_set]

    min_x = min_y = min_z = float("inf")
    max_x = max_y = max_z = float("-inf")
    has_bounds = False
    for ob in new_objects:
        if ob.type != "MESH":
            continue
        for corner in ob.bound_box:
            co = ob.matrix_world @ Vector(corner)
            min_x = min(min_x, co.x)
            min_y = min(min_y, co.y)
            min_z = min(min_z, co.z)
            max_x = max(max_x, co.x)
            max_y = max(max_y, co.y)
            max_z = max(max_z, co.z)
            has_bounds = True

    if not has_bounds:
        return
    cx = (min_x + max_x) * 0.5
    cy = (min_y + max_y) * 0.5
    shift = Vector((-cx, -cy, -min_z))
    for root in roots:
        root.location += shift


def _ensure_imported_asset_group(filepath: str) -> tuple[bpy.types.Collection, bpy.types.Collection]:
    base = os.path.splitext(os.path.basename(filepath))[0]
    lib = _ensure_asset_library()
    group_name = f"RWB_GLTF_{base}"
    group = bpy.data.collections.get(group_name)
    if group is None:
        group = bpy.data.collections.new(group_name)
        lib.children.link(group)
    _unhide_collection_tree(group)
    _hide_collection(group)

    imported_name = f"RWB_Imported_{base}"
    imported = bpy.data.collections.get(imported_name)
    if imported is None:
        imported = bpy.data.collections.new(imported_name)
        group.children.link(imported)
    _unhide_collection_tree(imported)
    _hide_collection(imported)

    if len(imported.all_objects) == 0:
        before_objects = set(bpy.data.objects)
        before_collections = set(bpy.data.collections)
        bpy.ops.import_scene.gltf(filepath=filepath)
        new_objects = [ob for ob in bpy.data.objects if ob not in before_objects]
        _normalize_imported_objects(new_objects)
        for ob in new_objects:
            if ob.name not in imported.objects:
                imported.objects.link(ob)
        for ob in new_objects:
            for c in list(ob.users_collection):
                if c != imported:
                    try:
                        c.objects.unlink(ob)
                    except RuntimeError:
                        pass

        new_collections = [c for c in bpy.data.collections if c not in before_collections]
        for c in new_collections:
            if c == imported or c == group or c == lib:
                continue
            if len(c.objects) == 0 and len(c.children) == 0 and c.users == 0:
                bpy.data.collections.remove(c)
        imported["rwb_normalized"] = True
    elif not bool(imported.get("rwb_normalized", False)):
        _normalize_imported_objects(list(imported.all_objects))
        imported["rwb_normalized"] = True

    return group, imported


def _extract_prototypes(group: bpy.types.Collection, imported: bpy.types.Collection) -> list[bpy.types.Collection]:
    existing = [c for c in group.children if c.name.startswith("RWB_Proto_")]
    if existing:
        return existing

    base = group.name.removeprefix("RWB_GLTF_")
    topo: list[bpy.types.Object] = []
    imported_set = set(imported.all_objects)
    for ob in imported.all_objects:
        if ob.parent is None or ob.parent not in imported_set:
            topo.append(ob)
    if not topo:
        topo = list(imported.all_objects)

    prototypes: list[bpy.types.Collection] = []
    used_objects: set[bpy.types.Object] = set()
    for i, root in enumerate(topo):
        objs = [ob for ob in _walk_hierarchy(root) if ob in imported_set]
        objs = [ob for ob in objs if ob not in used_objects]
        if not objs:
            continue
        for ob in objs:
            used_objects.add(ob)
        name = f"RWB_Proto_{base}_{i:03d}"
        proto = bpy.data.collections.new(name)
        group.children.link(proto)
        _hide_collection(proto)
        for ob in objs:
            if ob.name not in proto.objects:
                proto.objects.link(ob)
        prototypes.append(proto)

    if not prototypes:
        prototypes.append(imported)
    return prototypes


def get_prototypes_for_category(category: str, assets_root_dir: str | None) -> list[bpy.types.Collection]:
    root = assets_root_dir or _addon_source_dir()
    folder_by_category = {"BUILDING": "Building", "TREE": "Tree", "GRASS": "Grass"}
    folder = folder_by_category.get(category)
    if folder is None:
        return []

    path = os.path.join(root, folder)
    if not os.path.isdir(path):
        return []

    files = [os.path.join(path, f) for f in os.listdir(path) if f.lower().endswith(".glb")]
    files.sort()
    prototypes: list[bpy.types.Collection] = []
    for fp in files:
        group, imported = _ensure_imported_asset_group(fp)
        prototypes.extend(_extract_prototypes(group, imported))
    return prototypes


def _curve_points_world(obj: bpy.types.Object) -> list[Vector]:
    if obj.type != "CURVE":
        return []
    curve = obj.data
    points: list[Vector] = []
    for spline in curve.splines:
        if spline.type == "POLY":
            for p in spline.points:
                points.append(obj.matrix_world @ Vector((p.co.x, p.co.y, p.co.z)))
        elif spline.type == "BEZIER":
            for bp in spline.bezier_points:
                points.append(obj.matrix_world @ bp.co)
    return points


def _sample_polyline(points: list[Vector], step_m: float) -> list[tuple[Vector, Vector]]:
    if len(points) < 2:
        return []
    step = max(0.01, float(step_m))
    seg_len: list[float] = []
    for i in range(len(points) - 1):
        seg_len.append((points[i + 1] - points[i]).length)
    total = float(sum(seg_len))
    if total <= 1e-9:
        return []

    out: list[tuple[Vector, Vector]] = []
    dist = 0.0
    i = 0
    acc = 0.0
    while dist <= total + 1e-6:
        while i < len(seg_len) and acc + seg_len[i] < dist:
            acc += seg_len[i]
            i += 1
        if i >= len(seg_len):
            p = points[-1].copy()
            t = (points[-1] - points[-2]).copy()
            if t.length_squared <= 1e-12:
                t = Vector((1.0, 0.0, 0.0))
            else:
                t.normalize()
            out.append((p, t))
            break
        l = seg_len[i]
        t = (points[i + 1] - points[i]).copy()
        if t.length_squared <= 1e-12:
            t = Vector((1.0, 0.0, 0.0))
        else:
            t.normalize()
        if l <= 1e-9:
            p = points[i].copy()
        else:
            u = (dist - acc) / l
            p = points[i].lerp(points[i + 1], u)
        out.append((p, t))
        dist += step
    return out


def _build_terrain_bvh(obj: bpy.types.Object, depsgraph: bpy.types.Depsgraph) -> tuple[BVHTree, object, object] | None:
    if obj is None or obj.type != "MESH":
        return None
    eval_obj = obj.evaluated_get(depsgraph)
    mw = eval_obj.matrix_world
    try:
        bvh = BVHTree.FromObject(eval_obj, depsgraph)
        return bvh, mw, mw.inverted()
    except Exception:
        pass

    mesh = None
    try:
        mesh = eval_obj.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    except TypeError:
        try:
            mesh = eval_obj.to_mesh(preserve_all_data_layers=True)
        except TypeError:
            try:
                mesh = eval_obj.to_mesh()
            except Exception:
                mesh = None
    except Exception:
        mesh = None

    if mesh is None:
        return None

    try:
        bvh = BVHTree.FromMesh(mesh)
        return bvh, mw, mw.inverted()
    except Exception:
        return None
    finally:
        try:
            eval_obj.to_mesh_clear()
        except Exception:
            pass


def _terrain_bounds_xy_world(obj: bpy.types.Object, depsgraph: bpy.types.Depsgraph) -> tuple[float, float, float, float] | None:
    if obj is None or obj.type != "MESH":
        return None
    eval_obj = obj.evaluated_get(depsgraph)
    mw = eval_obj.matrix_world
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")
    for corner in eval_obj.bound_box:
        co = mw @ Vector(corner)
        min_x = min(min_x, co.x)
        min_y = min(min_y, co.y)
        max_x = max(max_x, co.x)
        max_y = max(max_y, co.y)
    if not math.isfinite(min_x) or not math.isfinite(min_y) or not math.isfinite(max_x) or not math.isfinite(max_y):
        return None
    return min_x, max_x, min_y, max_y


def _dist2_point_to_segment_xy(p: Vector, a: Vector, b: Vector) -> float:
    ax = float(a.x)
    ay = float(a.y)
    bx = float(b.x)
    by = float(b.y)
    px = float(p.x)
    py = float(p.y)
    abx = bx - ax
    aby = by - ay
    apx = px - ax
    apy = py - ay
    denom = abx * abx + aby * aby
    if denom <= 1e-12:
        dx = px - ax
        dy = py - ay
        return dx * dx + dy * dy
    t = (apx * abx + apy * aby) / denom
    if t <= 0.0:
        cx = ax
        cy = ay
    elif t >= 1.0:
        cx = bx
        cy = by
    else:
        cx = ax + abx * t
        cy = ay + aby * t
    dx = px - cx
    dy = py - cy
    return dx * dx + dy * dy


class _PolylineDistanceIndex:
    def __init__(self, points: list[Vector], cell_size: float):
        self._cell = max(0.5, float(cell_size))
        self._inv = 1.0 / self._cell
        self._pts = points
        self._cells: dict[tuple[int, int], list[int]] = {}
        for i in range(len(points) - 1):
            a = points[i]
            b = points[i + 1]
            min_x = min(float(a.x), float(b.x))
            max_x = max(float(a.x), float(b.x))
            min_y = min(float(a.y), float(b.y))
            max_y = max(float(a.y), float(b.y))
            ix0 = int(math.floor(min_x * self._inv))
            ix1 = int(math.floor(max_x * self._inv))
            iy0 = int(math.floor(min_y * self._inv))
            iy1 = int(math.floor(max_y * self._inv))
            for ix in range(ix0, ix1 + 1):
                for iy in range(iy0, iy1 + 1):
                    self._cells.setdefault((ix, iy), []).append(i)

    def min_dist2(self, p: Vector) -> float:
        ix = int(math.floor(float(p.x) * self._inv))
        iy = int(math.floor(float(p.y) * self._inv))
        best = float("inf")
        for ox in (-1, 0, 1):
            for oy in (-1, 0, 1):
                segs = self._cells.get((ix + ox, iy + oy))
                if not segs:
                    continue
                for i in segs:
                    d2 = _dist2_point_to_segment_xy(p, self._pts[i], self._pts[i + 1])
                    if d2 < best:
                        best = d2
        if best != float("inf"):
            return best
        for i in range(len(self._pts) - 1):
            d2 = _dist2_point_to_segment_xy(p, self._pts[i], self._pts[i + 1])
            if d2 < best:
                best = d2
        return best


def _project_to_terrain(
    xy: Vector,
    z_hint: float,
    bvh_pack: tuple[BVHTree, object, object] | None,
) -> tuple[Vector, Vector] | None:
    if bvh_pack is None:
        return None
    bvh, mw, mwi = bvh_pack
    origin_w = Vector((xy.x, xy.y, z_hint + 5000.0))
    dir_w = Vector((0.0, 0.0, -1.0))
    origin_l = mwi @ origin_w
    dir_l = (mwi.to_3x3() @ dir_w).normalized()
    hit = bvh.ray_cast(origin_l, dir_l, 20000.0)
    if hit is None or hit[0] is None:
        return None
    loc_l, normal_l, _, _ = hit
    loc_w = mw @ loc_l
    normal_w = (mw.to_3x3() @ normal_l).normalized()
    return loc_w, normal_w


class _Grid2D:
    def __init__(self, cell_size: float):
        self._cell = max(0.01, float(cell_size))
        self._inv = 1.0 / self._cell
        self._cells: dict[tuple[int, int], list[tuple[float, float]]] = {}

    def _key(self, x: float, y: float) -> tuple[int, int]:
        return (int(math.floor(x * self._inv)), int(math.floor(y * self._inv)))

    def can_place(self, x: float, y: float, min_dist: float) -> bool:
        r = max(0.0, float(min_dist))
        if r <= 1e-6:
            return True
        rr = r * r
        kx, ky = self._key(x, y)
        for oy in (-1, 0, 1):
            for ox in (-1, 0, 1):
                pts = self._cells.get((kx + ox, ky + oy))
                if not pts:
                    continue
                for px, py in pts:
                    dx = x - px
                    dy = y - py
                    if dx * dx + dy * dy < rr:
                        return False
        return True

    def insert(self, x: float, y: float) -> None:
        k = self._key(x, y)
        self._cells.setdefault(k, []).append((x, y))


def _instance_collection(
    name: str,
    prototype: bpy.types.Collection,
    target_collection: bpy.types.Collection,
    location: Vector,
    rotation: Euler,
    uniform_scale: float,
) -> bpy.types.Object:
    inst = bpy.data.objects.new(name, None)
    inst.empty_display_type = "PLAIN_AXES"
    inst.instance_type = "COLLECTION"
    inst.instance_collection = prototype
    inst.location = location
    inst.rotation_euler = rotation
    s = float(uniform_scale)
    inst.scale = (s, s, s)
    target_collection.objects.link(inst)
    return inst


@dataclass(frozen=True)
class ScatterCategorySettings:
    enabled: bool
    spacing_m: float
    probability: float
    min_distance_m: float
    offset_min_m: float
    offset_max_m: float
    scale_min: float
    scale_max: float


@dataclass(frozen=True)
class ScatterRoadsideSettings:
    seed: int
    road_width_m: float
    road_no_spawn_m: float
    building_cluster_min: int
    building_cluster_max: int
    building_cluster_along_m: float
    building_cluster_out_m: float
    side: str
    route_obj: bpy.types.Object | None
    terrain_obj: bpy.types.Object | None
    assets_root_dir: str | None
    max_instances: int
    building: ScatterCategorySettings
    tree: ScatterCategorySettings
    grass: ScatterCategorySettings


def scatter_roadside_assets(context: bpy.types.Context, settings: ScatterRoadsideSettings) -> tuple[int, str]:
    if int(settings.max_instances) <= 0:
        return 0, "Max Instances is 0"

    route_obj = settings.route_obj
    if route_obj is None:
        route_obj = bpy.data.objects.get("RWB_Route")
    if route_obj is None or route_obj.type != "CURVE":
        return 0, "Route curve not found (set Route or create RWB_Route)"

    route_points = _curve_points_world(route_obj)
    if len(route_points) < 2:
        return 0, "Route curve has too few points"

    terrain_obj = settings.terrain_obj or bpy.data.objects.get("RWB_Terrain")
    if terrain_obj is None or terrain_obj.type != "MESH":
        return 0, "Terrain mesh not found (set Terrain or create RWB_Terrain)"
    if terrain_obj.name == "RWB_Road":
        alt = bpy.data.objects.get("RWB_Terrain")
        if alt is not None and alt.type == "MESH":
            terrain_obj = alt

    depsgraph = context.evaluated_depsgraph_get()
    bvh_pack = _build_terrain_bvh(terrain_obj, depsgraph)
    if bvh_pack is None:
        return 0, f"Terrain '{terrain_obj.name}' cannot be evaluated to a mesh (convert/apply modifiers)"
    terrain_bounds = _terrain_bounds_xy_world(terrain_obj, depsgraph)

    parent = _ensure_collection("Route2World")
    target = _ensure_collection("RWB_Scatter", parent=parent)
    target.hide_viewport = False
    target.hide_render = False

    rng = random.Random(int(settings.seed))

    categories: list[tuple[str, ScatterCategorySettings]] = [
        ("BUILDING", settings.building),
        ("TREE", settings.tree),
        ("GRASS", settings.grass),
    ]

    side_signs: list[int]
    if settings.side == "LEFT":
        side_signs = [1]
    elif settings.side == "RIGHT":
        side_signs = [-1]
    else:
        side_signs = [1, -1]

    assets_root = settings.assets_root_dir or _addon_source_dir()
    if not os.path.isdir(assets_root):
        return 0, f"Assets root not found: {assets_root}"

    prototypes_by_cat: dict[str, list[bpy.types.Collection]] = {}
    for cat, cat_settings in categories:
        if not cat_settings.enabled:
            continue
        folder = {"BUILDING": "Building", "TREE": "Tree", "GRASS": "Grass"}[cat]
        cat_dir = os.path.join(assets_root, folder)
        if not os.path.isdir(cat_dir):
            return 0, f"Assets folder not found: {cat_dir}"
        has_glb = any(f.lower().endswith(".glb") for f in os.listdir(cat_dir))
        if not has_glb:
            return 0, f"No .glb found in: {cat_dir}"
        protos = get_prototypes_for_category(cat, settings.assets_root_dir)
        if protos:
            prototypes_by_cat[cat] = protos
        else:
            return 0, f"Imported 0 prototypes from: {cat_dir}"

    lib_parent = _ensure_asset_library()
    building_lib = None
    tree_lib = None
    grass_lib = None
    if settings.building.enabled:
        building_lib = build_category_library(name="RWB_GNLib_BUILDING", prototypes=prototypes_by_cat.get("BUILDING", []))
    if settings.tree.enabled:
        tree_lib = build_category_library(name="RWB_GNLib_TREE", prototypes=prototypes_by_cat.get("TREE", []))
    if settings.grass.enabled:
        grass_lib = build_category_library(name="RWB_GNLib_GRASS", prototypes=prototypes_by_cat.get("GRASS", []))

    for lib in (building_lib, tree_lib, grass_lib):
        if lib is None:
            continue
        if lib.name not in lib_parent.children:
            try:
                lib_parent.children.link(lib)
            except Exception:
                pass
        _unhide_collection_tree(lib)
        _hide_collection(lib)

    points_obj = bpy.data.objects.get("RWB_ScatterPoints")
    if points_obj is None or points_obj.type != "MESH":
        mesh = bpy.data.meshes.new("RWB_ScatterPointsMesh")
        points_obj = bpy.data.objects.new("RWB_ScatterPoints", mesh)
    if points_obj.name not in target.objects:
        target.objects.link(points_obj)
    for c in list(points_obj.users_collection):
        if c != target:
            try:
                c.objects.unlink(points_obj)
            except Exception:
                pass

    points_obj.hide_select = False
    try:
        points_obj.hide_set(False)
    except Exception:
        points_obj.hide_viewport = False
    points_obj.hide_render = False

    verts: list[tuple[float, float, float]] = []
    cat_attr: list[int] = []
    proto_attr: list[int] = []
    rot_attr: list[float] = []
    scale_attr: list[float] = []

    proto_min_x_cache: dict[str, float] = {}
    proto_radius_xy_cache: dict[str, float] = {}

    def _prototype_min_x(proto: bpy.types.Collection) -> float:
        k = proto.name
        cached = proto_min_x_cache.get(k)
        if cached is not None:
            return cached
        min_x = 0.0
        has = False
        for ob in proto.all_objects:
            if ob.type != "MESH":
                continue
            mw = ob.matrix_world
            for corner in ob.bound_box:
                x = (mw @ Vector(corner)).x
                if not has:
                    min_x = x
                    has = True
                else:
                    min_x = min(min_x, x)
        if not has:
            min_x = 0.0
        proto_min_x_cache[k] = float(min_x)
        return float(min_x)

    def _prototype_radius_xy(proto: bpy.types.Collection) -> float:
        k = proto.name
        cached = proto_radius_xy_cache.get(k)
        if cached is not None:
            return cached
        r2 = 0.0
        for ob in proto.all_objects:
            if ob.type != "MESH":
                continue
            mw = ob.matrix_world
            for corner in ob.bound_box:
                co = mw @ Vector(corner)
                d2 = float(co.x) * float(co.x) + float(co.y) * float(co.y)
                if d2 > r2:
                    r2 = d2
        r = float(r2**0.5)
        proto_radius_xy_cache[k] = r
        return r

    non_grass_min: list[float] = []
    if settings.building.enabled:
        non_grass_min.append(float(settings.building.min_distance_m))
    if settings.tree.enabled:
        non_grass_min.append(float(settings.tree.min_distance_m))
    non_grass_min = [d for d in non_grass_min if d > 0.0]
    global_grid = _Grid2D(min(non_grass_min) if non_grass_min else 1.0)

    stats: dict[str, dict[str, int]] = {}
    count = 0
    road_half = float(settings.road_width_m) * 0.5
    no_spawn_gap = max(0.0, float(settings.road_no_spawn_m))
    route_index = _PolylineDistanceIndex(route_points, cell_size=max(8.0, road_half * 4.0))
    for cat, cat_settings in categories:
        if not cat_settings.enabled:
            continue
        protos = prototypes_by_cat.get(cat, [])
        if not protos:
            continue
        samples = _sample_polyline(route_points, cat_settings.spacing_m)
        if not samples:
            continue
        stats[cat] = {"samples": len(samples), "prob_pass": 0, "placed": 0}
        grid = _Grid2D(max(cat_settings.min_distance_m, 0.01))
        for p, t in samples:
            if count >= int(settings.max_instances):
                return count, ""
            t2 = Vector((t.x, t.y, 0.0))
            if t2.length_squared <= 1e-12:
                t2 = Vector((1.0, 0.0, 0.0))
            else:
                t2.normalize()
            perp = Vector((-t2.y, t2.x, 0.0))
            for sgn in side_signs:
                if count >= int(settings.max_instances):
                    return count, ""
                if rng.random() > max(0.0, min(1.0, cat_settings.probability)):
                    continue
                stats[cat]["prob_pass"] += 1

                out_dir = (perp * float(sgn)).normalized()

                yaw = math.atan2(t2.y, t2.x)
                if cat == "BUILDING":
                    yaw += float(sgn) * (math.pi * 0.5)
                else:
                    yaw += rng.uniform(-math.pi, math.pi)
                rot = Euler((0.0, 0.0, yaw), "XYZ")

                sc_min = float(cat_settings.scale_min)
                sc_max = float(cat_settings.scale_max)
                if sc_min > sc_max:
                    sc_min, sc_max = sc_max, sc_min

                if cat == "BUILDING":
                    cl_min = max(1, int(settings.building_cluster_min))
                    cl_max = max(1, int(settings.building_cluster_max))
                    if cl_min > cl_max:
                        cl_min, cl_max = cl_max, cl_min
                    cluster_count = rng.randint(cl_min, cl_max)
                    along_r = max(0.0, float(settings.building_cluster_along_m))
                    out_r = max(0.0, float(settings.building_cluster_out_m))

                    for _ in range(cluster_count):
                        if count >= int(settings.max_instances):
                            return count, ""

                        proto_idx = rng.randrange(0, len(protos))
                        proto = protos[proto_idx]
                        sc = rng.uniform(sc_min, sc_max)

                        gap_min = float(cat_settings.offset_min_m)
                        gap_max = float(cat_settings.offset_max_m)
                        if gap_min > gap_max:
                            gap_min, gap_max = gap_max, gap_min
                        gap = max(no_spawn_gap, rng.uniform(gap_min, gap_max))

                        inward_dist = max(0.0, -_prototype_min_x(proto))
                        center_offset = road_half + gap + inward_dist * sc

                        along_j = t2 * rng.uniform(-along_r, along_r)
                        out_j = out_dir * rng.uniform(0.0, out_r)
                        pos_xy = Vector((p.x, p.y, 0.0)) + along_j + out_dir * center_offset + out_j
                        footprint_r = _prototype_radius_xy(proto) * sc
                        if route_index.min_dist2(pos_xy) < (road_half + footprint_r) * (road_half + footprint_r):
                            continue

                        if terrain_bounds is not None:
                            min_xb, max_xb, min_yb, max_yb = terrain_bounds
                            if pos_xy.x < min_xb or pos_xy.x > max_xb or pos_xy.y < min_yb or pos_xy.y > max_yb:
                                continue
                        if not grid.can_place(pos_xy.x, pos_xy.y, float(cat_settings.min_distance_m)):
                            continue
                        if not global_grid.can_place(pos_xy.x, pos_xy.y, float(cat_settings.min_distance_m)):
                            continue

                        hit = _project_to_terrain(pos_xy, p.z, bvh_pack)
                        if hit is None:
                            continue
                        loc, _ = hit
                        verts.append((float(loc.x), float(loc.y), float(loc.z)))
                        cat_attr.append(0)
                        proto_attr.append(int(proto_idx))
                        rot_attr.append(float(rot.z))
                        scale_attr.append(float(sc))
                        grid.insert(pos_xy.x, pos_xy.y)
                        global_grid.insert(pos_xy.x, pos_xy.y)
                        count += 1
                        stats[cat]["placed"] += 1
                else:
                    proto_idx = rng.randrange(0, len(protos))
                    proto = protos[proto_idx]
                    sc = rng.uniform(sc_min, sc_max)

                    gap_min = float(cat_settings.offset_min_m)
                    gap_max = float(cat_settings.offset_max_m)
                    if gap_min > gap_max:
                        gap_min, gap_max = gap_max, gap_min
                    gap = max(no_spawn_gap, rng.uniform(gap_min, gap_max))
                    center_offset = road_half + gap
                    pos_xy = Vector((p.x, p.y, 0.0)) + out_dir * center_offset
                    footprint_r = _prototype_radius_xy(proto) * sc
                    if route_index.min_dist2(pos_xy) < (road_half + footprint_r) * (road_half + footprint_r):
                        continue

                    if terrain_bounds is not None:
                        min_xb, max_xb, min_yb, max_yb = terrain_bounds
                        if pos_xy.x < min_xb or pos_xy.x > max_xb or pos_xy.y < min_yb or pos_xy.y > max_yb:
                            continue
                    if not grid.can_place(pos_xy.x, pos_xy.y, float(cat_settings.min_distance_m)):
                        continue
                    if cat != "GRASS" and not global_grid.can_place(pos_xy.x, pos_xy.y, float(cat_settings.min_distance_m)):
                        continue

                    hit = _project_to_terrain(pos_xy, p.z, bvh_pack)
                    if hit is None:
                        continue
                    loc, _ = hit
                    verts.append((float(loc.x), float(loc.y), float(loc.z)))
                    cat_attr.append(1 if cat == "TREE" else 2)
                    proto_attr.append(int(proto_idx))
                    rot_attr.append(float(rot.z))
                    scale_attr.append(float(sc))
                    grid.insert(pos_xy.x, pos_xy.y)
                    if cat != "GRASS":
                        global_grid.insert(pos_xy.x, pos_xy.y)
                    count += 1
                    stats[cat]["placed"] += 1

    if count <= 0:
        bits: list[str] = []
        for cat in ("BUILDING", "TREE", "GRASS"):
            if cat not in stats:
                continue
            d = stats[cat]
            bits.append(f"{cat}: samples={d['samples']} prob={d['prob_pass']} placed={d['placed']}")
        hint = " | ".join(bits) if bits else "No enabled categories"
        return 0, f"No placements. {hint}"

    new_mesh = bpy.data.meshes.new("RWB_ScatterPointsMesh")
    new_mesh.from_pydata(verts, [], [])

    def _ensure_attr(mesh: bpy.types.Mesh, name: str, typ: str):
        if name in mesh.attributes:
            try:
                mesh.attributes.remove(mesh.attributes[name])
            except Exception:
                pass
        return mesh.attributes.new(name=name, type=typ, domain="POINT")

    a_cat = _ensure_attr(new_mesh, ATTR_CATEGORY, "INT")
    a_idx = _ensure_attr(new_mesh, ATTR_PROTO_INDEX, "INT")
    a_rot = _ensure_attr(new_mesh, ATTR_ROT_Z, "FLOAT")
    a_sc = _ensure_attr(new_mesh, ATTR_SCALE, "FLOAT")

    for i in range(len(verts)):
        a_cat.data[i].value = int(cat_attr[i])
        a_idx.data[i].value = int(proto_attr[i])
        a_rot.data[i].value = float(rot_attr[i])
        a_sc.data[i].value = float(scale_attr[i])

    old_mesh = points_obj.data
    points_obj.data = new_mesh
    if isinstance(old_mesh, bpy.types.Mesh) and old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)

    err = apply_scatter_instances_modifier(
        points_obj=points_obj,
        building_lib=building_lib,
        tree_lib=tree_lib,
        grass_lib=grass_lib,
    )
    if err:
        return 0, err

    return count, ""

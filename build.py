from __future__ import annotations

import math

import bpy
import bmesh
from mathutils import Vector, noise

from .geom import Bounds2D, bounds_from_points_xy, lerp, smoothstep01


ROAD_UV_TILE_M = 6.0
TERRAIN_UV_TILE_M = 5.0


def ensure_collection(name: str) -> bpy.types.Collection:
    c = bpy.data.collections.get(name)
    if c:
        return c
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c


def add_shrinkwrap(obj: bpy.types.Object, target: bpy.types.Object, offset: float) -> None:
    mod = obj.modifiers.new(name="Shrinkwrap", type="SHRINKWRAP")
    mod.target = target
    mod.wrap_method = "NEAREST_SURFACEPOINT"
    mod.offset = offset


def add_solidify(obj: bpy.types.Object, thickness: float) -> None:
    t = float(thickness)
    if t <= 0.0:
        return
    mod = obj.modifiers.new(name="Solidify", type="SOLIDIFY")
    mod.thickness = t
    mod.offset = 1.0
    mod.use_even_offset = True


def create_route_curve(name: str, points: list[Vector]) -> bpy.types.Object:
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 2

    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for i, p in enumerate(points):
        spline.points[i].co = (p.x, p.y, p.z, 1.0)

    return bpy.data.objects.new(name, curve)


def create_road_mesh(name: str, points: list[Vector], width_m: float) -> bpy.types.Object:
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")

    left: list[bmesh.types.BMVert] = []
    right: list[bmesh.types.BMVert] = []

    half_w = width_m * 0.5
    tile = max(0.001, float(ROAD_UV_TILE_M))
    u0 = 0.0
    u1 = float(width_m) / tile
    v_by_i: list[float] = [0.0]
    for i in range(1, len(points)):
        v_by_i.append(v_by_i[-1] + (points[i] - points[i - 1]).length / tile)

    n = len(points)
    for i, p in enumerate(points):
        p_prev = points[i - 1] if i > 0 else points[i]
        p_next = points[i + 1] if i < n - 1 else points[i]
        t = Vector((p_next.x - p_prev.x, p_next.y - p_prev.y, 0.0))
        if t.length_squared <= 1e-12:
            t = Vector((1.0, 0.0, 0.0))
        t.normalize()
        perp = Vector((-t.y, t.x, 0.0))
        offset = perp * half_w

        l = bm.verts.new(Vector((p.x, p.y, p.z)) + offset)
        r = bm.verts.new(Vector((p.x, p.y, p.z)) - offset)
        left.append(l)
        right.append(r)

    bm.verts.ensure_lookup_table()

    for i in range(n - 1):
        v1, v2, v3, v4 = left[i], right[i], right[i + 1], left[i + 1]
        try:
            f = bm.faces.new([v1, v2, v3, v4])
            loops = f.loops
            v0 = v_by_i[i]
            v1v = v_by_i[i + 1]
            loops[0][uv_layer].uv = (u0, v0)
            loops[1][uv_layer].uv = (u1, v0)
            loops[2][uv_layer].uv = (u1, v1v)
            loops[3][uv_layer].uv = (u0, v1v)
        except ValueError:
            pass

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return bpy.data.objects.new(name, mesh)


def apply_evaluated_mesh(obj: bpy.types.Object) -> None:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    new_mesh = bpy.data.meshes.new_from_object(
        eval_obj,
        preserve_all_data_layers=True,
        depsgraph=depsgraph,
    )
    old_mesh = obj.data
    obj.data = new_mesh
    if isinstance(old_mesh, bpy.types.Mesh) and old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)


def level_road_crossfall(
    obj: bpy.types.Object,
    route: list[Vector],
    width_m: float,
    max_bank_slope_m_per_m: float = 0.05,
    bank_gain: float = 4.0,
) -> None:
    mesh = obj.data
    if not isinstance(mesh, bpy.types.Mesh):
        return

    n = len(route)
    if n < 2:
        return

    expected = 2 * n
    if len(mesh.vertices) < expected:
        return

    half_w = float(width_m) * 0.5
    if half_w <= 1e-6:
        return

    max_bank = max(0.0, float(max_bank_slope_m_per_m))
    gain = float(bank_gain)

    def curvature_at(i: int) -> float:
        i0 = max(0, i - 1)
        i1 = i
        i2 = min(n - 1, i + 1)

        p0 = route[i0]
        p1 = route[i1]
        p2 = route[i2]

        a = Vector((p1.x - p0.x, p1.y - p0.y))
        b = Vector((p2.x - p1.x, p2.y - p1.y))
        la = float(a.length)
        lb = float(b.length)
        if la <= 1e-6 or lb <= 1e-6:
            return 0.0

        dot = float(a.x * b.x + a.y * b.y)
        cross = float(a.x * b.y - a.y * b.x)
        angle = math.atan2(cross, dot)
        s = 0.5 * (la + lb)
        if s <= 1e-6:
            return 0.0
        return angle / s

    for i in range(n):
        li = 2 * i
        ri = li + 1
        vl = mesh.vertices[li]
        vr = mesh.vertices[ri]
        zl = float(vl.co.z)
        zr = float(vr.co.z)
        z_avg = 0.5 * (zl + zr)

        k = curvature_at(i)
        bank = k * gain
        if bank > max_bank:
            bank = max_bank
        elif bank < -max_bank:
            bank = -max_bank
        if abs(bank) < 0.002:
            bank = 0.0

        delta = bank * half_w
        vl.co.z = z_avg - delta
        vr.co.z = z_avg + delta

    mesh.update()


def _nearest_route_distance_and_height_segment_xy(x: float, y: float, route: list[Vector]) -> tuple[float, float]:
    best_d2 = float("inf")
    best_h = route[0].z if route else 0.0

    for i in range(len(route) - 1):
        a = route[i]
        b = route[i + 1]
        ax = a.x
        ay = a.y
        bx = b.x
        by = b.y
        abx = bx - ax
        aby = by - ay
        denom = abx * abx + aby * aby
        t = 0.0
        if denom > 1e-12:
            t = ((x - ax) * abx + (y - ay) * aby) / denom
            if t < 0.0:
                t = 0.0
            elif t > 1.0:
                t = 1.0
        cx = ax + abx * t
        cy = ay + aby * t
        dx = x - cx
        dy = y - cy
        d2 = dx * dx + dy * dy
        if d2 < best_d2:
            best_d2 = d2
            best_h = lerp(a.z, b.z, t)
    return math.sqrt(best_d2), best_h


def _bilinear_sample_height(
    heights: list[float],
    size: int,
    x: float,
    y: float,
    bounds: Bounds2D,
) -> float:
    width = bounds.size_x
    depth = bounds.size_y
    if width <= 1e-12 or depth <= 1e-12:
        return float(heights[0]) if heights else 0.0

    u = (x - bounds.min_x) / width
    v = (y - bounds.min_y) / depth
    if u < 0.0:
        u = 0.0
    elif u > 1.0:
        u = 1.0
    if v < 0.0:
        v = 0.0
    elif v > 1.0:
        v = 1.0

    sx = u * (size - 1)
    sy = v * (size - 1)
    ix = int(math.floor(sx))
    iy = int(math.floor(sy))
    tx = sx - ix
    ty = sy - iy

    ix1 = ix + 1
    iy1 = iy + 1
    if ix1 >= size:
        ix1 = size - 1
    if iy1 >= size:
        iy1 = size - 1

    h00 = float(heights[ix + iy * size])
    h10 = float(heights[ix1 + iy * size])
    h01 = float(heights[ix + iy1 * size])
    h11 = float(heights[ix1 + iy1 * size])

    hx0 = lerp(h00, h10, tx)
    hx1 = lerp(h01, h11, tx)
    return lerp(hx0, hx1, ty)


def _undulation_noise_2d(x: float, y: float, frequency: float) -> float:
    f = float(frequency)
    if f <= 0.0:
        return 0.0
    return noise.noise(Vector((x * f, y * f, 0.0)), noise_basis="PERLIN_ORIGINAL")


def build_multiscale_heightmap(
    bounds: Bounds2D,
    route: list[Vector],
    grid_resolution: int,
    multiscale_iterations: int,
    initial_scale_divisor: int,
    pin_radius_m: float,
    route_blend_radius_m: float,
    undulation_amplitude_m: float,
    undulation_frequency: float,
    undulation_seed: int,
    carve_depth_m: float,
    carve_radius_m: float,
) -> tuple[list[float], int, list[float]]:
    final_size = max(8, int(grid_resolution))
    coarse_size = max(8, int(math.floor(final_size / float(max(1, int(initial_scale_divisor))))))
    iter_cnt = max(1, int(multiscale_iterations))

    sizes: list[int] = [coarse_size]
    while len(sizes) < iter_cnt:
        ns = min(final_size, sizes[-1] * 2)
        if ns == sizes[-1]:
            break
        sizes.append(ns)
    if sizes[-1] != final_size:
        sizes.append(final_size)

    width = bounds.size_x
    depth = bounds.size_y

    noise.seed_set(int(undulation_seed) or 140230)

    prev_heights: list[float] = []
    prev_size = 0
    final_distances: list[float] = []

    pin_r = max(0.0, float(pin_radius_m))
    blend_r = max(pin_r, float(route_blend_radius_m))
    carve_r = max(0.0, float(carve_radius_m))
    carve_d = max(0.0, float(carve_depth_m))

    for size in sizes:
        heights = [0.0] * (size * size)
        distances: list[float] | None = [0.0] * (size * size) if size == final_size else None
        for iy in range(size):
            fy = iy / float(size - 1)
            y = bounds.min_y + fy * depth
            for ix in range(size):
                fx = ix / float(size - 1)
                x = bounds.min_x + fx * width

                if prev_size > 0:
                    base_h = _bilinear_sample_height(prev_heights, prev_size, x, y, bounds)
                else:
                    _, base_h = _nearest_route_distance_and_height_segment_xy(x, y, route)

                nearest_d, route_h = _nearest_route_distance_and_height_segment_xy(x, y, route)
                if distances is not None:
                    distances[ix + iy * size] = nearest_d

                if carve_d > 0.0 and carve_r > 0.0 and nearest_d < carve_r:
                    route_h -= carve_d * smoothstep01(1.0 - (nearest_d / carve_r))

                h = base_h
                if nearest_d <= pin_r:
                    h = route_h
                elif nearest_d <= blend_r:
                    denom = max(blend_r - pin_r, 1e-6)
                    t = (nearest_d - pin_r) / denom
                    t = smoothstep01(t)
                    h = lerp(route_h, base_h, t)

                if undulation_amplitude_m > 0.0 and blend_r > 0.0:
                    d_norm = (nearest_d - blend_r) / blend_r
                    if d_norm < 0.0:
                        d_norm = 0.0
                    elif d_norm > 1.0:
                        d_norm = 1.0
                    s = smoothstep01(d_norm)
                    h += _undulation_noise_2d(x, y, undulation_frequency) * float(undulation_amplitude_m) * s

                heights[ix + iy * size] = h

        prev_heights = heights
        prev_size = size
        if distances is not None:
            final_distances = distances

    return prev_heights, prev_size, final_distances


def _smooth_heights(
    heights: list[float],
    size: int,
    pinned: list[bool],
    strength: float,
    iterations: int,
) -> list[float]:
    s = float(strength)
    if s <= 0.0 or iterations <= 0:
        return heights

    out = heights[:]
    for _ in range(int(iterations)):
        tmp = out[:]
        for iy in range(1, size - 1):
            row = iy * size
            for ix in range(1, size - 1):
                idx = row + ix
                if pinned[idx]:
                    continue
                avg = (
                    out[idx]
                    + out[idx - 1]
                    + out[idx + 1]
                    + out[idx - size]
                    + out[idx + size]
                ) / 5.0
                tmp[idx] = lerp(out[idx], avg, s)
        out = tmp
    return out


def _limit_slope(
    heights: list[float],
    size: int,
    pinned: list[bool],
    max_slope_m_per_m: float,
    dx: float,
    dy: float,
    iterations: int,
) -> list[float]:
    it = max(0, int(iterations))
    if it == 0:
        return heights

    max_slope = max(0.0, float(max_slope_m_per_m))
    if max_slope <= 0.0:
        return heights

    max_dhx = max_slope * max(1e-6, float(dx))
    max_dhy = max_slope * max(1e-6, float(dy))

    out = heights[:]
    for _ in range(it):
        for iy in range(size):
            row = iy * size
            for ix in range(size):
                idx = row + ix
                if pinned[idx]:
                    continue
                h = out[idx]

                lo = -1e30
                hi = 1e30
                if ix > 0:
                    hn = out[idx - 1]
                    lo = max(lo, hn - max_dhx)
                    hi = min(hi, hn + max_dhx)
                if ix < size - 1:
                    hn = out[idx + 1]
                    lo = max(lo, hn - max_dhx)
                    hi = min(hi, hn + max_dhx)
                if iy > 0:
                    hn = out[idx - size]
                    lo = max(lo, hn - max_dhy)
                    hi = min(hi, hn + max_dhy)
                if iy < size - 1:
                    hn = out[idx + size]
                    lo = max(lo, hn - max_dhy)
                    hi = min(hi, hn + max_dhy)

                if h < lo:
                    out[idx] = lo
                elif h > hi:
                    out[idx] = hi
    return out


def create_terrain(
    name: str,
    bounds: Bounds2D,
    route: list[Vector],
    road_width_m: float,
    terrain_detail: int,
    terrain_style: float,
    seed: int,
    road_embed_m: float,
) -> bpy.types.Object:
    detail = max(1, min(5, int(terrain_detail)))
    style = max(0.0, min(1.0, float(terrain_style)))

    resolution_by_detail = {1: 64, 2: 96, 3: 128, 4: 192, 5: 256}
    iterations_by_detail = {1: 2, 2: 3, 3: 3, 4: 4, 5: 5}
    divisor_by_detail = {1: 32, 2: 32, 3: 32, 4: 16, 5: 16}

    grid_resolution = resolution_by_detail[detail]
    multiscale_iterations = iterations_by_detail[detail]
    initial_scale_divisor = divisor_by_detail[detail]

    half_road_w = max(0.0, float(road_width_m) * 0.5)
    pin_radius_m = max(0.0, half_road_w + max(0.25, float(road_width_m) * 0.05))
    route_blend_radius_m = pin_radius_m + lerp(25.0, 10.0, style)
    undulation_amplitude_m = lerp(3.0, 18.0, style)
    undulation_frequency = lerp(0.0018, 0.006, style)

    carve_depth_m = max(0.0, float(road_embed_m))
    carve_radius_m = max(pin_radius_m, half_road_w + max(1.0, float(road_width_m) * 0.2))

    heights, size, distances = build_multiscale_heightmap(
        bounds=bounds,
        route=route,
        grid_resolution=grid_resolution,
        multiscale_iterations=multiscale_iterations,
        initial_scale_divisor=initial_scale_divisor,
        pin_radius_m=pin_radius_m,
        route_blend_radius_m=route_blend_radius_m,
        undulation_amplitude_m=undulation_amplitude_m,
        undulation_frequency=undulation_frequency,
        undulation_seed=seed,
        carve_depth_m=carve_depth_m,
        carve_radius_m=carve_radius_m,
    )

    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")
    verts: list[list[bmesh.types.BMVert]] = []
    width = bounds.size_x
    depth = bounds.size_y

    pinned = [False] * (size * size)
    for i, d in enumerate(distances):
        pinned[i] = d <= pin_radius_m

    dx = width / float(max(1, size - 1))
    dy = depth / float(max(1, size - 1))
    slope_max = lerp(0.25, 0.85, style)
    slope_iterations = {1: 20, 2: 30, 3: 40, 4: 50, 5: 60}[detail]
    heights = _limit_slope(heights, size, pinned, slope_max, dx, dy, slope_iterations)

    smooth_strength = lerp(0.55, 0.10, style)
    smooth_iters = {1: 6, 2: 5, 3: 4, 4: 3, 5: 2}[detail]
    heights = _smooth_heights(heights, size, pinned, smooth_strength, smooth_iters)

    for iy in range(size):
        row: list[bmesh.types.BMVert] = []
        fy = iy / float(size - 1)
        y = bounds.min_y + fy * depth
        for ix in range(size):
            fx = ix / float(size - 1)
            x = bounds.min_x + fx * width
            z = float(heights[ix + iy * size])
            row.append(bm.verts.new((x, y, z)))
        verts.append(row)

    bm.verts.ensure_lookup_table()

    for iy in range(size - 1):
        for ix in range(size - 1):
            v00 = verts[iy][ix]
            v10 = verts[iy][ix + 1]
            v11 = verts[iy + 1][ix + 1]
            v01 = verts[iy + 1][ix]
            try:
                f = bm.faces.new((v00, v10, v11, v01))
                tile = max(0.001, float(TERRAIN_UV_TILE_M))
                for loop in f.loops:
                    co = loop.vert.co
                    loop[uv_layer].uv = (
                        (co.x - bounds.min_x) / tile,
                        (co.y - bounds.min_y) / tile,
                    )
            except ValueError:
                pass

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return bpy.data.objects.new(name, mesh)


def compute_route_bounds(points: list[Vector], margin_m: float) -> Bounds2D:
    return bounds_from_points_xy(points).expand(float(max(0.0, margin_m)))

import os

import bpy

from ..building.builder import (
    add_solidify,
    compute_route_bounds,
    create_road_mesh,
    create_route_curve,
    create_terrain,
    ensure_collection,
    level_road_crossfall,
    lower_terrain_under_road,
)
from ..parse.gpx import parse_gpx_track, project_to_local_meters, simplify_polyline_xy, smooth_polyline
from ..material.manager import apply_textures_from_scene_settings, reset_textures_data
from .mapbox import MapboxTerrainDownloader


class ROUTE2WORLD_OT_GenerateFromGpx(bpy.types.Operator):
    bl_idname = "route2world.generate_from_gpx"
    bl_label = "Generate from GPX"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        p = context.scene.route2world
        s = getattr(context.scene, "route2world_scatter", None)
        filepath = bpy.path.abspath(p.gpx_filepath) if p.gpx_filepath else ""
        if not filepath or not os.path.exists(filepath):
            self.report({"ERROR"}, "GPX file not found")
            return {"CANCELLED"}

        geo_points = parse_gpx_track(filepath)
        if len(geo_points) < 2:
            self.report({"ERROR"}, "No track points found in GPX")
            return {"CANCELLED"}

        detail = max(1, min(5, int(p.terrain_detail)))
        simplify_step_by_detail = {1: 10.0, 2: 7.0, 3: 5.0, 4: 3.0, 5: 2.0}
        max_points_by_detail = {1: 800, 2: 1500, 3: 2500, 4: 5000, 5: 8000}

        route_raw = project_to_local_meters(geo_points)
        if len(route_raw) < 2:
            self.report({"ERROR"}, "Route is too short")
            return {"CANCELLED"}

        # Apply smoothing
        route_raw = smooth_polyline(
            route_raw,
            window_size=p.gpx_smoothing_window,
            iterations=p.gpx_smoothing_iterations,
        )

        terrain_route = simplify_polyline_xy(route_raw, simplify_step_by_detail[detail])
        if len(terrain_route) > max_points_by_detail[detail]:
            max_points = int(max_points_by_detail[detail])
            if max_points < 2:
                max_points = 2
            cum = [0.0]
            for i in range(1, len(terrain_route)):
                dx = float(terrain_route[i].x - terrain_route[i - 1].x)
                dy = float(terrain_route[i].y - terrain_route[i - 1].y)
                cum.append(cum[-1] + (dx * dx + dy * dy) ** 0.5)
            total = float(cum[-1])
            if total <= 1e-6:
                terrain_route = [terrain_route[0], terrain_route[-1]]
            else:
                step = total / float(max_points - 1)
                sampled = [terrain_route[0]]
                target = step
                j = 1
                while len(sampled) < max_points - 1 and j < len(terrain_route) - 1:
                    while j < len(cum) - 1 and cum[j] < target:
                        j += 1
                    if j >= len(terrain_route) - 1:
                        break
                    sampled.append(terrain_route[j])
                    target += step
                sampled.append(terrain_route[-1])
                terrain_route = sampled

        collection = ensure_collection("Route2World")

        terrain_obj = None
        road_obj = None
        if p.create_terrain:
            if p.process_mode == "MAPBOX":
                try:
                    downloader = MapboxTerrainDownloader(context)
                    # Use preference quality
                    pkg_name = __package__.split('.')[0]
                    quality = context.preferences.addons[pkg_name].preferences.download_quality
                    terrain_obj = downloader.download_and_create_terrain(geo_points, quality=quality)
                    if terrain_obj:
                        collection.objects.link(terrain_obj)
                except Exception as e:
                    self.report({"ERROR"}, f"Mapbox Error: {e}")
                    return {"CANCELLED"}
            else:
                bounds = compute_route_bounds(route_raw, p.terrain_margin_m)
                terrain_obj = create_terrain(
                    name="RWB_Terrain",
                    bounds=bounds,
                    route=terrain_route,
                    road_width_m=p.road_width_m,
                    terrain_detail=p.terrain_detail,
                    terrain_style=p.terrain_style,
                    seed=p.seed,
                    road_embed_m=p.road_embed_m,
                )
                collection.objects.link(terrain_obj)

        route_obj = None
        if p.create_route_curve:
            route_obj = create_route_curve("RWB_Route", route_raw)
            collection.objects.link(route_obj)

        if p.create_road_mesh:
            road_obj = create_road_mesh("RWB_Road", route_raw, p.road_width_m)
            collection.objects.link(road_obj)
            road_obj.location.z += float(p.road_offset_m)
            level_road_crossfall(road_obj, route_raw, p.road_width_m)
            add_solidify(road_obj, p.road_thickness_m)

        if terrain_obj is not None:
            road_for_terrain = road_obj or bpy.data.objects.get("RWB_Road")
            if road_for_terrain is not None:
                lower_terrain_under_road(terrain_obj, road_for_terrain)

        if terrain_obj is None:
            terrain_obj = bpy.data.objects.get("RWB_Terrain")
        if road_obj is None:
            road_obj = bpy.data.objects.get("RWB_Road")
        if route_obj is None:
            route_obj = bpy.data.objects.get("RWB_Route")

        if terrain_obj is not None:
            try:
                p.texture_terrain_obj = terrain_obj
            except Exception:
                pass
            try:
                p.terrain_transition_terrain_obj = terrain_obj
            except Exception:
                pass
            if s is not None:
                try:
                    s.terrain_object = terrain_obj
                except Exception:
                    pass

        if road_obj is not None:
            try:
                p.texture_road_obj = road_obj
            except Exception:
                pass
            try:
                p.terrain_transition_road_obj = road_obj
            except Exception:
                pass

        if route_obj is not None and s is not None:
            try:
                s.route_object = route_obj
            except Exception:
                pass

        return {"FINISHED"}


class ROUTE2WORLD_OT_ApplyTextures(bpy.types.Operator):
    bl_idname = "route2world.apply_textures"
    bl_label = "Apply Textures"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        p = context.scene.route2world
        terrain_obj = getattr(p, "texture_terrain_obj", None) or bpy.data.objects.get("RWB_Terrain")
        road_obj = getattr(p, "texture_road_obj", None) or bpy.data.objects.get("RWB_Road")
        if terrain_obj is None and road_obj is None:
            self.report({"ERROR"}, "Terrain/Road not found (set Targets or create RWB_Terrain/RWB_Road)")
            return {"CANCELLED"}

        msgs = apply_textures_from_scene_settings(p, terrain_obj=terrain_obj, road_obj=road_obj)
        for m in msgs:
            self.report({"WARNING"}, str(m))
        return {"FINISHED"}


class ROUTE2WORLD_OT_ResetTextures(bpy.types.Operator):
    bl_idname = "route2world.reset_textures"
    bl_label = "Reset Textures"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        p = context.scene.route2world
        root = str(getattr(p, "texture_root_dir", "") or "")
        msg = reset_textures_data(texture_root=root)
        self.report({"INFO"}, str(msg))
        return {"FINISHED"}

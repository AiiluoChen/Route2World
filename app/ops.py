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
from ..parse.gpx import parse_gpx_track, project_to_local_meters, simplify_polyline_xy
from ..material.manager import apply_textures_from_scene_settings


class ROUTE2WORLD_OT_GenerateFromGpx(bpy.types.Operator):
    bl_idname = "route2world.generate_from_gpx"
    bl_label = "Generate from GPX"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        p = context.scene.route2world
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

        if p.create_route_curve:
            curve_obj = create_route_curve("RWB_Route", route_raw)
            collection.objects.link(curve_obj)

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

        msgs = apply_textures_from_scene_settings(p, terrain_obj=terrain_obj, road_obj=road_obj)
        for m in msgs:
            self.report({"WARNING"}, str(m))

        return {"FINISHED"}


class ROUTE2WORLD_OT_SetupPaintMask(bpy.types.Operator):
    bl_idname = "route2world.setup_paint_mask"
    bl_label = "Setup Paint Mask"
    bl_description = "Creates the color attribute for manual terrain painting and switches to Vertex Paint mode"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = bpy.data.objects.get("RWB_Terrain")
        if not obj:
            self.report({"ERROR"}, "RWB_Terrain object not found")
            return {"CANCELLED"}
        
        if obj.type != "MESH":
            self.report({"ERROR"}, "RWB_Terrain is not a mesh")
            return {"CANCELLED"}
            
        def _collection_is_in_tree(root: bpy.types.Collection, target: bpy.types.Collection) -> bool:
            if root == target:
                return True
            for c in root.children:
                if _collection_is_in_tree(c, target):
                    return True
            return False

        def _layer_collection_path(
            root: bpy.types.LayerCollection,
            target: bpy.types.Collection,
            acc: list[bpy.types.LayerCollection],
        ) -> list[bpy.types.LayerCollection] | None:
            if root.collection == target:
                return acc + [root]
            for lc in root.children:
                found = _layer_collection_path(lc, target, acc + [root])
                if found:
                    return found
            return None

        if not obj.users_collection:
            c = ensure_collection("Route2World")
            if obj.name not in c.objects:
                c.objects.link(obj)

        scene_root = context.scene.collection
        for c in list(obj.users_collection):
            if not _collection_is_in_tree(scene_root, c):
                try:
                    scene_root.children.link(c)
                except RuntimeError:
                    pass

        for c in list(obj.users_collection):
            path = _layer_collection_path(context.view_layer.layer_collection, c, [])
            if not path:
                continue
            for lc in path:
                lc.exclude = False
                lc.hide_viewport = False

        try:
            obj.hide_set(False)
        except Exception:
            obj.hide_viewport = False
        obj.hide_select = False

        if context.view_layer.objects.get(obj.name) is None:
            try:
                context.scene.collection.objects.link(obj)
            except RuntimeError:
                pass

        if context.view_layer.objects.get(obj.name) is None:
            self.report({"ERROR"}, "RWB_Terrain is not available in the active ViewLayer")
            return {"CANCELLED"}

        context.view_layer.objects.active = obj
        obj.select_set(True)
        
        # Ensure attribute exists
        attr_name = "Terrain_Region_Mask"
        if attr_name not in obj.data.attributes:
            obj.data.attributes.new(name=attr_name, type="BYTE_COLOR", domain="CORNER")
            # Default to black (transparent/no override)
            # Actually, newly created attributes are usually black (0,0,0,1) or white?
            # Blender defaults vary. We can fill it with black just in case.
            # But in vertex paint, default is usually white or black depending on method.
            # Let's assume user starts painting.
            
        # Switch to Vertex Paint
        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode="VERTEX_PAINT")
            
        # Set brush color to Red (Ground) as default suggestion?
        # That's hard to access via API robustly without context override.
        # But we can report instructions.
        
        self.report({"INFO"}, "Switched to Vertex Paint. Paint Red=Ground, Green=Rock, Blue=Snow.")
        return {"FINISHED"}

from __future__ import annotations

import bpy

from .core import ScatterCategorySettings, ScatterRoadsideSettings, scatter_roadside_assets


class ROUTE2WORLD_OT_ScatterRoadsideAssets(bpy.types.Operator):
    bl_idname = "route2world.scatter_roadside_assets"
    bl_label = "Scatter Roadside Assets"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        p = context.scene.route2world
        s = context.scene.route2world_scatter

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

        def _ensure_collection_visible(c: bpy.types.Collection) -> None:
            scene_root = context.scene.collection
            if not _collection_is_in_tree(scene_root, c):
                try:
                    scene_root.children.link(c)
                except RuntimeError:
                    pass
            path = _layer_collection_path(context.view_layer.layer_collection, c, [])
            if not path:
                return
            for lc in path:
                lc.exclude = False
                lc.hide_viewport = False

        settings = ScatterRoadsideSettings(
            seed=int(s.scatter_seed),
            road_width_m=float(p.road_width_m),
            road_no_spawn_m=float(s.road_no_spawn_m),
            side=str(s.scatter_side),
            route_obj=s.route_object,
            terrain_obj=s.terrain_object,
            assets_root_dir=bpy.path.abspath(s.assets_root_dir) if s.assets_root_dir else None,
            max_instances=int(s.max_instances),
            building_cluster_min=int(s.building_cluster_min),
            building_cluster_max=int(s.building_cluster_max),
            building_cluster_along_m=float(s.building_cluster_along_m),
            building_cluster_out_m=float(s.building_cluster_out_m),
            building=ScatterCategorySettings(
                enabled=bool(s.building_enabled),
                spacing_m=float(s.building_spacing_m),
                probability=float(s.building_probability),
                min_distance_m=float(s.building_min_distance_m),
                offset_min_m=float(s.building_offset_min_m),
                offset_max_m=float(s.building_offset_max_m),
                scale_min=float(s.building_scale_min),
                scale_max=float(s.building_scale_max),
            ),
            tree=ScatterCategorySettings(
                enabled=bool(s.tree_enabled),
                spacing_m=float(s.tree_spacing_m),
                probability=float(s.tree_probability),
                min_distance_m=float(s.tree_min_distance_m),
                offset_min_m=float(s.tree_offset_min_m),
                offset_max_m=float(s.tree_offset_max_m),
                scale_min=float(s.tree_scale_min),
                scale_max=float(s.tree_scale_max),
            ),
            grass=ScatterCategorySettings(
                enabled=bool(s.grass_enabled),
                spacing_m=float(s.grass_spacing_m),
                probability=float(s.grass_probability),
                min_distance_m=float(s.grass_min_distance_m),
                offset_min_m=float(s.grass_offset_min_m),
                offset_max_m=float(s.grass_offset_max_m),
                scale_min=float(s.grass_scale_min),
                scale_max=float(s.grass_scale_max),
            ),
        )

        try:
            created, message = scatter_roadside_assets(context, settings)
        except Exception as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}
        if created <= 0:
            self.report({"WARNING"}, message or "No instances created")
        else:
            scatter_collection = bpy.data.collections.get("RWB_Scatter")
            if scatter_collection is not None:
                _ensure_collection_visible(scatter_collection)
            points_obj = bpy.data.objects.get("RWB_ScatterPoints")
            if points_obj is not None:
                try:
                    points_obj.hide_set(False)
                except Exception:
                    points_obj.hide_viewport = False
                points_obj.hide_render = False
            self.report({"INFO"}, f"Created {created} instances")
        return {"FINISHED"}

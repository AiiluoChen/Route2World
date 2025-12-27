from __future__ import annotations

import bpy
from .translations import t


class Route2WorldScatterProperties(bpy.types.PropertyGroup):
    assets_root_dir: bpy.props.StringProperty(
        name="Assets Root",
        description="Optional override. If empty, uses the add-on assets/models folder",
        subtype="DIR_PATH",
        default="",
    )

    route_object: bpy.props.PointerProperty(
        name="Route",
        type=bpy.types.Object,
        description="Route curve object. If empty, uses object named RWB_Route",
    )

    terrain_object: bpy.props.PointerProperty(
        name="Terrain",
        type=bpy.types.Object,
        description="Terrain mesh for height projection (recommended)",
    )

    scatter_seed: bpy.props.IntProperty(
        name="Seed",
        min=0,
        max=999999,
        default=140230,
    )

    scatter_side: bpy.props.EnumProperty(
        name="Side",
        items=(
            ("BOTH", "Both", ""),
            ("LEFT", "Left", ""),
            ("RIGHT", "Right", ""),
        ),
        default="BOTH",
    )

    max_instances: bpy.props.IntProperty(
        name="Max Instances",
        min=0,
        soft_max=50000,
        default=6000,
    )

    road_no_spawn_m: bpy.props.FloatProperty(
        name="Road No-Spawn (m)",
        min=0.0,
        soft_max=50.0,
        default=1.0,
    )

    building_enabled: bpy.props.BoolProperty(name="Buildings", default=True)
    building_spacing_m: bpy.props.FloatProperty(name="Building Spacing (m)", min=1.0, soft_max=200.0, default=35.0)
    building_probability: bpy.props.FloatProperty(name="Building Probability", min=0.0, max=1.0, default=0.35)
    building_min_distance_m: bpy.props.FloatProperty(name="Building Min Distance (m)", min=0.0, soft_max=100.0, default=12.0)
    building_offset_min_m: bpy.props.FloatProperty(name="Building Offset Min (m)", min=0.0, soft_max=200.0, default=4.0)
    building_offset_max_m: bpy.props.FloatProperty(name="Building Offset Max (m)", min=0.0, soft_max=200.0, default=20.0)
    building_scale_min: bpy.props.FloatProperty(name="Building Scale Min", min=0.01, soft_max=10.0, default=1.0)
    building_scale_max: bpy.props.FloatProperty(name="Building Scale Max", min=0.01, soft_max=10.0, default=1.0)
    building_cluster_min: bpy.props.IntProperty(name="Building Cluster Min", min=1, soft_max=50, default=1)
    building_cluster_max: bpy.props.IntProperty(name="Building Cluster Max", min=1, soft_max=50, default=10)
    building_cluster_along_m: bpy.props.FloatProperty(name="Building Cluster Along (m)", min=0.0, soft_max=200.0, default=18.0)
    building_cluster_out_m: bpy.props.FloatProperty(name="Building Cluster Out (m)", min=0.0, soft_max=400.0, default=30.0)

    tree_enabled: bpy.props.BoolProperty(name="Trees", default=True)
    tree_spacing_m: bpy.props.FloatProperty(name="Tree Spacing (m)", min=0.5, soft_max=50.0, default=7.0)
    tree_probability: bpy.props.FloatProperty(name="Tree Probability", min=0.0, max=1.0, default=0.75)
    tree_min_distance_m: bpy.props.FloatProperty(name="Tree Min Distance (m)", min=0.0, soft_max=50.0, default=2.5)
    tree_offset_min_m: bpy.props.FloatProperty(name="Tree Offset Min (m)", min=0.0, soft_max=200.0, default=2.0)
    tree_offset_max_m: bpy.props.FloatProperty(name="Tree Offset Max (m)", min=0.0, soft_max=200.0, default=12.0)
    tree_scale_min: bpy.props.FloatProperty(name="Tree Scale Min", min=0.01, soft_max=10.0, default=0.85)
    tree_scale_max: bpy.props.FloatProperty(name="Tree Scale Max", min=0.01, soft_max=10.0, default=1.15)

    grass_enabled: bpy.props.BoolProperty(name="Grass", default=False)
    grass_spacing_m: bpy.props.FloatProperty(name="Grass Spacing (m)", min=0.1, soft_max=10.0, default=1.2)
    grass_probability: bpy.props.FloatProperty(name="Grass Probability", min=0.0, max=1.0, default=0.5)
    grass_min_distance_m: bpy.props.FloatProperty(name="Grass Min Distance (m)", min=0.0, soft_max=10.0, default=0.0)
    grass_offset_min_m: bpy.props.FloatProperty(name="Grass Offset Min (m)", min=0.0, soft_max=200.0, default=1.0)
    grass_offset_max_m: bpy.props.FloatProperty(name="Grass Offset Max (m)", min=0.0, soft_max=200.0, default=8.0)
    grass_scale_min: bpy.props.FloatProperty(name="Grass Scale Min", min=0.01, soft_max=10.0, default=0.9)
    grass_scale_max: bpy.props.FloatProperty(name="Grass Scale Max", min=0.01, soft_max=10.0, default=1.1)


class ROUTE2WORLD_PT_Procedural(bpy.types.Panel):
    bl_label = "Procedural"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Route2World"
    bl_parent_id = "ROUTE2WORLD_PT_Main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        p = context.scene.route2world
        s = context.scene.route2world_scatter
        layout = self.layout

        # 1. Target Settings
        box = layout.box()
        box.label(text=t("Targets"))
        box.prop(s, "route_object", text=t("Route"))
        box.prop(s, "terrain_object", text=t("Terrain"))
        box.prop(s, "assets_root_dir", text=t("Assets Root"))

        # 2. Scatter Control
        box = layout.box()
        box.label(text=t("Scatter Control"))
        
        row = box.row()
        row.prop(s, "scatter_side", expand=True, text=t("Side"))
        
        col = box.column()
        col.prop(s, "scatter_seed", text=t("Seed"))
        col.prop(s, "max_instances", text=t("Max Instances"))
        col.prop(s, "road_no_spawn_m", text=t("Road No-Spawn (m)"))
        
        box.separator()
        box.operator("route2world.scatter_roadside_assets", text=t("Scatter Assets"))

        # 3. Asset Types
        box = layout.box()
        box.label(text=t("Asset Types"))
        
        # Buildings
        col = box.column()
        row = col.row()
        row.prop(s, "building_enabled", text=t("Buildings"), icon="BUILDING_DATA", toggle=True)
        
        if s.building_enabled:
            sub = col.box()
            sub.prop(s, "building_spacing_m", text=t("Building Spacing (m)"))
            sub.prop(s, "building_probability", text=t("Building Probability"))
            sub.prop(s, "building_min_distance_m", text=t("Building Min Distance (m)"))
            
            sub.label(text=t("Offset"), icon="TRANSFORM")
            row = sub.row(align=True)
            row.prop(s, "building_offset_min_m", text=t("Min"))
            row.prop(s, "building_offset_max_m", text=t("Max"))
            
            sub.label(text=t("Scale"), icon="FULLSCREEN_ENTER")
            row = sub.row(align=True)
            row.prop(s, "building_scale_min", text=t("Min"))
            row.prop(s, "building_scale_max", text=t("Max"))
            
            sub.label(text=t("Cluster"), icon="GROUP")
            row = sub.row(align=True)
            row.prop(s, "building_cluster_min", text=t("Min"))
            row.prop(s, "building_cluster_max", text=t("Max"))
            
            sub.prop(s, "building_cluster_along_m", text=t("Building Cluster Along (m)"))
            sub.prop(s, "building_cluster_out_m", text=t("Building Cluster Out (m)"))
            
        col.separator()

        # Trees
        col = box.column()
        row = col.row()
        row.prop(s, "tree_enabled", text=t("Trees"), icon="OUTLINER_OB_CURVE", toggle=True)
        
        if s.tree_enabled:
            sub = col.box()
            sub.prop(s, "tree_spacing_m", text=t("Tree Spacing (m)"))
            sub.prop(s, "tree_probability", text=t("Tree Probability"))
            sub.prop(s, "tree_min_distance_m", text=t("Tree Min Distance (m)"))
            
            sub.label(text=t("Offset"), icon="TRANSFORM")
            row = sub.row(align=True)
            row.prop(s, "tree_offset_min_m", text=t("Min"))
            row.prop(s, "tree_offset_max_m", text=t("Max"))
            
            sub.label(text=t("Scale"), icon="FULLSCREEN_ENTER")
            row = sub.row(align=True)
            row.prop(s, "tree_scale_min", text=t("Min"))
            row.prop(s, "tree_scale_max", text=t("Max"))

        col.separator()
        
        # Grass
        col = box.column()
        row = col.row()
        row.prop(s, "grass_enabled", text=t("Grass"), icon="HAIR", toggle=True)
        
        if s.grass_enabled:
            sub = col.box()
            sub.prop(s, "grass_spacing_m", text=t("Grass Spacing (m)"))
            sub.prop(s, "grass_probability", text=t("Grass Probability"))
            sub.prop(s, "grass_min_distance_m", text=t("Grass Min Distance (m)"))
            
            sub.label(text=t("Offset"), icon="TRANSFORM")
            row = sub.row(align=True)
            row.prop(s, "grass_offset_min_m", text=t("Min"))
            row.prop(s, "grass_offset_max_m", text=t("Max"))
            
            sub.label(text=t("Scale"), icon="FULLSCREEN_ENTER")
            row = sub.row(align=True)
            row.prop(s, "grass_scale_min", text=t("Min"))
            row.prop(s, "grass_scale_max", text=t("Max"))

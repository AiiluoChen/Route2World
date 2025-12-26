from __future__ import annotations

import bpy


class Route2WorldScatterProperties(bpy.types.PropertyGroup):
    assets_root_dir: bpy.props.StringProperty(
        name="Assets Root",
        description="Optional override. If empty, uses the add-on Source folder",
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

    def draw(self, context):
        p = context.scene.route2world
        s = context.scene.route2world_scatter
        layout = self.layout

        box = layout.box()
        box.label(text="Targets")
        box.prop(s, "route_object")
        box.prop(s, "terrain_object")
        box.prop(s, "assets_root_dir")

        box = layout.box()
        box.label(text="Scatter")
        row = box.row(align=True)
        row.prop(s, "scatter_side", expand=True)
        box.prop(s, "scatter_seed")
        box.prop(s, "max_instances")
        box.prop(s, "road_no_spawn_m")
        box.operator("route2world.scatter_roadside_assets", text="Scatter Roadsides")

        box = layout.box()
        box.label(text="Buildings")
        box.prop(s, "building_enabled", toggle=True)
        col = box.column()
        col.enabled = bool(s.building_enabled)
        col.prop(s, "building_spacing_m")
        col.prop(s, "building_probability")
        col.prop(s, "building_min_distance_m")
        col.prop(s, "building_offset_min_m")
        col.prop(s, "building_offset_max_m")
        col.prop(s, "building_scale_min")
        col.prop(s, "building_scale_max")
        col.prop(s, "building_cluster_min")
        col.prop(s, "building_cluster_max")
        col.prop(s, "building_cluster_along_m")
        col.prop(s, "building_cluster_out_m")

        box = layout.box()
        box.label(text="Trees")
        box.prop(s, "tree_enabled", toggle=True)
        col = box.column()
        col.enabled = bool(s.tree_enabled)
        col.prop(s, "tree_spacing_m")
        col.prop(s, "tree_probability")
        col.prop(s, "tree_min_distance_m")
        col.prop(s, "tree_offset_min_m")
        col.prop(s, "tree_offset_max_m")
        col.prop(s, "tree_scale_min")
        col.prop(s, "tree_scale_max")

        box = layout.box()
        box.label(text="Grass")
        box.prop(s, "grass_enabled", toggle=True)
        col = box.column()
        col.enabled = bool(s.grass_enabled)
        col.prop(s, "grass_spacing_m")
        col.prop(s, "grass_probability")
        col.prop(s, "grass_min_distance_m")
        col.prop(s, "grass_offset_min_m")
        col.prop(s, "grass_offset_max_m")
        col.prop(s, "grass_scale_min")
        col.prop(s, "grass_scale_max")

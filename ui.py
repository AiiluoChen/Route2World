import bpy
from .texturing import apply_textures_from_scene_settings


def update_textures(self, context):
    """Update textures on existing objects when properties change."""
    # Try to find the objects by name (default names used in ops.py)
    # We could store pointers, but names are simpler for now.
    terrain_obj = bpy.data.objects.get("RWB_Terrain")
    road_obj = bpy.data.objects.get("RWB_Road")

    if terrain_obj or road_obj:
        apply_textures_from_scene_settings(
            self,
            terrain_obj=terrain_obj,
            road_obj=road_obj
        )


class Route2WorldProperties(bpy.types.PropertyGroup):
    gpx_filepath: bpy.props.StringProperty(
        name="GPX",
        description="GPX track file",
        subtype="FILE_PATH",
    )

    texture_root_dir: bpy.props.StringProperty(
        name="Texture Root",
        description="Optional override. If empty, uses the add-on Texture folder",
        subtype="DIR_PATH",
        default="",
        update=update_textures,
    )

    apply_terrain_textures: bpy.props.BoolProperty(
        name="Texture Terrain",
        default=True,
        update=update_textures,
    )

    apply_road_textures: bpy.props.BoolProperty(
        name="Texture Road",
        default=True,
        update=update_textures,
    )

    texture_variants: bpy.props.IntProperty(
        name="Texture Variants",
        min=1,
        max=8,
        default=3,
        update=update_textures,
    )

    texture_noise_scale: bpy.props.FloatProperty(
        name="Mix Scale",
        min=0.1,
        soft_max=50.0,
        default=6.0,
    )

    texture_transition_width: bpy.props.FloatProperty(
        name="Transition Width",
        min=0.0,
        max=1.0,
        default=0.06,
        update=update_textures,
    )

    terrain_ground_ratio: bpy.props.FloatProperty(
        name="Ground Ratio",
        min=0.0,
        max=1.0,
        default=0.4,
    )

    terrain_rock_ratio: bpy.props.FloatProperty(
        name="Rock Ratio",
        min=0.0,
        max=1.0,
        default=0.75,
    )

    terrain_height_blend: bpy.props.FloatProperty(
        name="Height Blend",
        min=0.0,
        max=0.5,
        default=0.08,
    )

    terrain_cliff_slope_start: bpy.props.FloatProperty(
        name="Cliff Start",
        min=0.0,
        max=1.0,
        default=0.35,
    )

    terrain_cliff_slope_end: bpy.props.FloatProperty(
        name="Cliff End",
        min=0.0,
        max=1.0,
        default=0.6,
    )

    road_width_m: bpy.props.FloatProperty(
        name="Road Width (m)",
        min=0.5,
        soft_max=20.0,
        default=6.0,
    )

    road_offset_m: bpy.props.FloatProperty(
        name="Road Offset (m)",
        description="Lift road above terrain to avoid z-fighting",
        min=-10.0,
        max=10.0,
        default=0.05,
    )

    road_embed_m: bpy.props.FloatProperty(
        name="Road Embed (m)",
        min=0.0,
        soft_max=2.0,
        default=0.0,
    )

    road_thickness_m: bpy.props.FloatProperty(
        name="Road Thickness (m)",
        min=0.0,
        soft_max=20.0,
        default=3.0,
    )

    terrain_margin_m: bpy.props.FloatProperty(
        name="Terrain Margin (m)",
        min=0.0,
        soft_max=2000.0,
        default=200.0,
    )

    terrain_detail: bpy.props.IntProperty(
        name="Detail",
        min=1,
        max=5,
        default=3,
    )

    terrain_style: bpy.props.FloatProperty(
        name="Style",
        min=0.0,
        max=1.0,
        default=0.6,
    )

    seed: bpy.props.IntProperty(
        name="Seed",
        min=0,
        max=999999,
        default=140230,
    )

    create_route_curve: bpy.props.BoolProperty(
        name="Create Route Curve",
        default=True,
    )

    create_road_mesh: bpy.props.BoolProperty(
        name="Create Road Mesh",
        default=True,
    )

    create_terrain: bpy.props.BoolProperty(
        name="Create Terrain",
        default=True,
    )


class ROUTE2WORLD_PT_Main(bpy.types.Panel):
    bl_label = "Route2World"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Route2World"

    def draw(self, context):
        p = context.scene.route2world
        layout = self.layout

        box = layout.box()
        box.prop(p, "gpx_filepath")
        box.operator("route2world.generate_from_gpx", text="Generate")

        box = layout.box()
        box.label(text="Textures")
        box.prop(p, "texture_root_dir")
        row = box.row(align=True)
        row.prop(p, "apply_terrain_textures", toggle=True)
        row.prop(p, "apply_road_textures", toggle=True)
        box.prop(p, "texture_variants")
        box.prop(p, "texture_noise_scale")
        box.prop(p, "texture_transition_width")

        box = layout.box()
        box.label(text="Manual Painting")
        box.operator("route2world.setup_paint_mask", text="Start Painting")
        box.label(text="Red=Ground, Green=Rock, Blue=Snow")

        box = layout.box()
        box.label(text="Objects")
        row = box.row(align=True)
        row.prop(p, "create_route_curve", toggle=True)
        row.prop(p, "create_road_mesh", toggle=True)
        row.prop(p, "create_terrain", toggle=True)

        box = layout.box()
        box.label(text="Road")
        box.prop(p, "road_width_m")
        box.prop(p, "road_offset_m")
        box.prop(p, "road_embed_m")
        box.prop(p, "road_thickness_m")

        box = layout.box()
        box.label(text="Terrain")
        box.prop(p, "terrain_margin_m")
        box.prop(p, "terrain_detail")
        box.prop(p, "terrain_style")
        box.prop(p, "seed")
        box.prop(p, "terrain_ground_ratio")
        box.prop(p, "terrain_rock_ratio")
        box.prop(p, "terrain_height_blend")
        box.prop(p, "terrain_cliff_slope_start")
        box.prop(p, "terrain_cliff_slope_end")

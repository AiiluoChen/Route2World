import bpy
from ..material.manager import apply_textures_from_scene_settings
from ..building.builder import apply_road_terrain_blend
from .translations import t


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


def update_road_terrain_blend(self, context):
    terrain_obj = bpy.data.objects.get("RWB_Terrain")
    road_obj = bpy.data.objects.get("RWB_Road")
    apply_road_terrain_blend(
        terrain_obj,
        road_obj,
        enabled=bool(self.enable_road_terrain_blend),
        blend_start_m=float(self.road_terrain_blend_start_m),
        blend_end_m=float(self.road_terrain_blend_end_m),
    )


class Route2WorldProperties(bpy.types.PropertyGroup):
    gpx_filepath: bpy.props.StringProperty(
        name="GPX",
        description="GPX track file",
        subtype="FILE_PATH",
    )

    process_mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ("AUTO", "Auto Generate", "Automatically generate terrain based on GPX"),
            ("MAPBOX", "Download Terrain", "Download terrain from Mapbox"),
        ],
        default="AUTO",
    )

    texture_root_dir: bpy.props.StringProperty(
        name="Texture Root",
        description="Optional override. If empty, uses the add-on assets/textures folder",
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

    enable_road_terrain_blend: bpy.props.BoolProperty(
        name="Road-Terrain Blend",
        default=True,
        update=update_road_terrain_blend,
    )

    road_terrain_blend_start_m: bpy.props.FloatProperty(
        name="Blend Start (m)",
        min=0.0,
        soft_max=50.0,
        default=0.0,
        update=update_road_terrain_blend,
    )

    road_terrain_blend_end_m: bpy.props.FloatProperty(
        name="Blend End (m)",
        min=0.0,
        soft_max=200.0,
        default=10.0,
        update=update_road_terrain_blend,
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
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        p = context.scene.route2world
        layout = self.layout

        # 1. Core Generation
        box = layout.box()
        box.label(text=t("Core Generation"))
        box.prop(p, "gpx_filepath", text=t("GPX"))
        
        row = box.row()
        row.prop(p, "process_mode", expand=True, text=t("Mode"))
        
        btn_text = t("Build World")
        if p.process_mode == "MAPBOX":
            btn_text = t("Download Terrain")
            
        box.operator("route2world.generate_from_gpx", text=btn_text)

        # 2. Scene Objects
        box = layout.box()
        box.label(text=t("Scene Objects"))
        row = box.row(align=True)
        row.prop(p, "create_route_curve", toggle=True, text=t("Create Route Curve"))
        row.prop(p, "create_road_mesh", toggle=True, text=t("Create Road Mesh"))
        row.prop(p, "create_terrain", toggle=True, text=t("Create Terrain"))

        # 3. Detailed Settings
        box = layout.box()
        box.label(text=t("Detailed Settings"))
        
        # Terrain Sub-panel
        if p.create_terrain:
            col = box.column()
            col.label(text=t("Terrain Settings"), icon="MESH_DATA")
            col.prop(p, "terrain_margin_m", text=t("Terrain Margin (m)"))
            col.prop(p, "terrain_detail", text=t("Detail"))
            if p.process_mode == "AUTO":
                col.prop(p, "terrain_style", text=t("Style"))
                col.prop(p, "seed", text=t("Seed"))
            
            col.separator()
            col.label(text=t("Material Blending"))
            col.prop(p, "terrain_ground_ratio", text=t("Ground Ratio"))
            col.prop(p, "terrain_rock_ratio", text=t("Rock Ratio"))
            col.prop(p, "terrain_height_blend", text=t("Height Blend"))
            col.prop(p, "terrain_cliff_slope_start", text=t("Cliff Start"))
            col.prop(p, "terrain_cliff_slope_end", text=t("Cliff End"))
            if p.create_road_mesh:
                col.separator()
                col.label(text=t("Road-Terrain Blend"))
                col.prop(p, "enable_road_terrain_blend", text=t("Enable Blend"))
                if p.enable_road_terrain_blend:
                    col.prop(p, "road_terrain_blend_start_m", text=t("Blend Start (m)"))
                    col.prop(p, "road_terrain_blend_end_m", text=t("Blend End (m)"))
            box.separator()

        # Road Sub-panel
        if p.create_road_mesh:
            col = box.column()
            col.label(text=t("Road Settings"), icon="DRIVER")
            col.prop(p, "road_width_m", text=t("Road Width (m)"))
            col.prop(p, "road_offset_m", text=t("Road Offset (m)"))
            col.prop(p, "road_embed_m", text=t("Road Embed (m)"))
            col.prop(p, "road_thickness_m", text=t("Road Thickness (m)"))
            box.separator()

        # Texture Sub-panel
        col = box.column()
        col.label(text=t("Textures"), icon="TEXTURE")
        col.prop(p, "texture_root_dir", text=t("Texture Root"))
        row = col.row(align=True)
        row.prop(p, "apply_terrain_textures", toggle=True, text=t("Texture Terrain"))
        row.prop(p, "apply_road_textures", toggle=True, text=t("Texture Road"))
        col.prop(p, "texture_variants", text=t("Texture Variants"))
        col.prop(p, "texture_noise_scale", text=t("Mix Scale"))
        col.prop(p, "texture_transition_width", text=t("Transition Width"))

        # 4. Tools
        box = layout.box()
        box.label(text=t("Manual Tools"))
        box.operator("route2world.setup_paint_mask", text=t("Start Painting"))
        box.label(text=t("Red=Ground, Green=Rock, Blue=Snow"), icon="INFO")

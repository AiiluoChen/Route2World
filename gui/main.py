import bpy
from ..material.manager import apply_textures_from_scene_settings
from .translations import t


def update_textures(self, context):
    """Update textures on existing objects when properties change."""
    terrain_obj = getattr(self, "texture_terrain_obj", None) or bpy.data.objects.get("RWB_Terrain")
    road_obj = getattr(self, "texture_road_obj", None) or bpy.data.objects.get("RWB_Road")

    if terrain_obj or road_obj:
        apply_textures_from_scene_settings(
            self,
            terrain_obj=terrain_obj,
            road_obj=road_obj
        )


def _poll_mesh_object(self, obj):
    return obj is not None and obj.type == "MESH"


class Route2WorldProperties(bpy.types.PropertyGroup):
    gpx_filepath: bpy.props.StringProperty(
        name="GPX",
        description="GPX track file",
        subtype="FILE_PATH",
    )

    gpx_smoothing_window: bpy.props.IntProperty(
        name="Smoothing Window",
        min=1,
        max=50,
        default=5,
        description="Window size for moving average smoothing",
    )

    gpx_smoothing_iterations: bpy.props.IntProperty(
        name="Smoothing Iterations",
        min=0,
        max=20,
        default=1,
        description="Number of smoothing passes",
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

    texture_terrain_obj: bpy.props.PointerProperty(
        name="Terrain",
        type=bpy.types.Object,
    )

    texture_road_obj: bpy.props.PointerProperty(
        name="Road",
        type=bpy.types.Object,
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

    terrain_ground_texture_dir: bpy.props.StringProperty(
        name="Ground Texture",
        description="Optional override. If empty, picks one folder from Texture Root/Ground",
        subtype="DIR_PATH",
        default="",
        update=update_textures,
    )

    terrain_rock_texture_dir: bpy.props.StringProperty(
        name="Rock Texture",
        description="Optional override. If empty, picks one folder from Texture Root/Rock",
        subtype="DIR_PATH",
        default="",
        update=update_textures,
    )

    terrain_snow_texture_dir: bpy.props.StringProperty(
        name="Snow Texture",
        description="Optional override. If empty, picks one folder from Texture Root/Snow",
        subtype="DIR_PATH",
        default="",
        update=update_textures,
    )

    terrain_texture_scale: bpy.props.FloatProperty(
        name="Texture Scale",
        min=0.001,
        soft_max=50.0,
        default=6.0,
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

    terrain_transition_terrain_obj: bpy.props.PointerProperty(
        name="Terrain",
        type=bpy.types.Object,
    )

    terrain_transition_road_obj: bpy.props.PointerProperty(
        name="Road",
        type=bpy.types.Object,
    )

    terrain_transition_width_m: bpy.props.FloatProperty(
        name="Transition Width (m)",
        min=0.0,
        soft_max=50.0,
        default=10.0,
    )

    terrain_transition_flat_width_m: bpy.props.FloatProperty(
        name="Flat Width (m)",
        min=0.0,
        soft_max=5.0,
        default=1.0,
    )

    terrain_transition_clearance_m: bpy.props.FloatProperty(
        name="Clearance (m)",
        min=0.0,
        soft_max=1.0,
        default=0.02,
    )

    terrain_transition_subdivide_levels: bpy.props.IntProperty(
        name="Subdivide Levels",
        min=0,
        max=6,
        default=0,
    )


class ROUTE2WORLD_PT_Main(bpy.types.Panel):
    bl_label = "Route2World"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Route2World"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        self.layout.label(text=t("Workflow"))


class ROUTE2WORLD_PT_Step1Generate(bpy.types.Panel):
    bl_label = t("Step 1: Generate Route/Road/Terrain")
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Route2World"
    bl_parent_id = "ROUTE2WORLD_PT_Main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        p = context.scene.route2world
        box = self.layout.box()

        box.prop(p, "gpx_filepath", text=t("GPX"))

        row = box.row(align=True)
        row.prop(p, "gpx_smoothing_window", text=t("Smoothing Window"))
        row.prop(p, "gpx_smoothing_iterations", text=t("Smoothing Iterations"))

        row = box.row()
        row.prop(p, "process_mode", expand=True, text=t("Mode"))

        row = box.row(align=True)
        row.prop(p, "create_route_curve", toggle=True, text=t("Create Route Curve"))
        row.prop(p, "create_road_mesh", toggle=True, text=t("Create Road Mesh"))
        row.prop(p, "create_terrain", toggle=True, text=t("Create Terrain"))

        if p.create_terrain:
            box.separator()
            box.label(text=t("Terrain Settings"), icon="MESH_DATA")
            box.prop(p, "terrain_margin_m", text=t("Terrain Margin (m)"))
            box.prop(p, "terrain_detail", text=t("Detail"))
            if p.process_mode == "AUTO":
                box.prop(p, "terrain_style", text=t("Style"))
                box.prop(p, "seed", text=t("Seed"))

        if p.create_road_mesh:
            box.separator()
            box.label(text=t("Road Settings"), icon="DRIVER")
            box.prop(p, "road_width_m", text=t("Road Width (m)"))
            box.prop(p, "road_offset_m", text=t("Road Offset (m)"))
            box.prop(p, "road_embed_m", text=t("Road Embed (m)"))
            box.prop(p, "road_thickness_m", text=t("Road Thickness (m)"))

        box.separator()
        btn_text = t("Generate Route/Road/Terrain")
        if p.process_mode == "MAPBOX":
            btn_text = t("Download Terrain")
        box.operator("route2world.generate_from_gpx", text=btn_text)


class ROUTE2WORLD_PT_Step2Textures(bpy.types.Panel):
    bl_label = t("Step 2: Road & Terrain Textures")
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Route2World"
    bl_parent_id = "ROUTE2WORLD_PT_Main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        p = context.scene.route2world
        box = self.layout.box()

        box.label(text=t("Targets"))
        box.prop(p, "texture_terrain_obj", text=t("Terrain"))
        box.prop(p, "texture_road_obj", text=t("Road"))
        box.separator()

        box.label(text=t("Textures"), icon="TEXTURE")
        box.prop(p, "texture_root_dir", text=t("Texture Root"))
        row = box.row(align=True)
        row.prop(p, "apply_terrain_textures", toggle=True, text=t("Texture Terrain"))
        row.prop(p, "apply_road_textures", toggle=True, text=t("Texture Road"))

        if p.apply_terrain_textures:
            box.separator()
            box.label(text=t("Terrain"), icon="MESH_GRID")
            box.prop(p, "terrain_ground_texture_dir", text=t("Ground Texture"))
            box.prop(p, "terrain_rock_texture_dir", text=t("Rock Texture"))
            box.prop(p, "terrain_snow_texture_dir", text=t("Snow Texture"))
            box.prop(p, "terrain_texture_scale", text=t("Texture Scale"))
            box.separator()
            box.label(text=t("Material Blending"))
            box.prop(p, "terrain_ground_ratio", text=t("Ground Ratio"))
            box.prop(p, "terrain_rock_ratio", text=t("Rock Ratio"))
            box.prop(p, "terrain_height_blend", text=t("Height Blend"))

        if p.apply_road_textures:
            box.separator()
            box.label(text=t("Road"), icon="CURVE_DATA")
            box.prop(p, "texture_variants", text=t("Texture Variants"))
            box.prop(p, "texture_noise_scale", text=t("Mix Scale"))

        box.separator()
        box.operator("route2world.apply_textures", text=t("Apply Textures"))
        box.operator("route2world.reset_textures", text=t("Reset Textures"))


class ROUTE2WORLD_PT_Step3PostProcess(bpy.types.Panel):
    bl_label = t("Step 3: Terrain Post Process")
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Route2World"
    bl_parent_id = "ROUTE2WORLD_PT_Main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        p = context.scene.route2world
        box = self.layout.box()
        box.label(text=t("Post Process"))
        box.prop(p, "terrain_transition_terrain_obj", text=t("Terrain"))
        box.prop(p, "terrain_transition_road_obj", text=t("Road"))
        box.prop(p, "terrain_transition_width_m", text=t("Transition Width (m)"))
        box.prop(p, "terrain_transition_flat_width_m", text=t("Flat Width (m)"))
        box.prop(p, "terrain_transition_clearance_m", text=t("Clearance (m)"))
        box.prop(p, "terrain_transition_subdivide_levels", text=t("Subdivide Levels"))
        box.operator("route2world.apply_terrain_transition", text=t("Apply Terrain Transition"))

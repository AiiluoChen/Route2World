bl_info = {
    "name": "Route2World",
    "author": "aiiluo",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Route2World",
    "description": "Generate route, road mesh and terrain from a GPX track",
    "category": "Import-Export",
}

import bpy

from .gui.main import (
    ROUTE2WORLD_PT_Main,
    ROUTE2WORLD_PT_Step1Generate,
    ROUTE2WORLD_PT_Step2Textures,
    ROUTE2WORLD_PT_Step3PostProcess,
    Route2WorldProperties,
)
from .app.ops import ROUTE2WORLD_OT_ApplyTextures, ROUTE2WORLD_OT_GenerateFromGpx, ROUTE2WORLD_OT_SetupPaintMask
from .postprocess.terrain_transition import ROUTE2WORLD_OT_ApplyTerrainTransition
from .scatter.ops import ROUTE2WORLD_OT_ScatterRoadsideAssets
from .gui.scatter import ROUTE2WORLD_PT_Procedural, Route2WorldScatterProperties
from .gui.translations import t


class Route2WorldPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    mapbox_access_token: bpy.props.StringProperty(
        name="Mapbox Access Token",
        description="Enter your Mapbox Access Token",
        subtype="PASSWORD",
    )

    default_process_mode: bpy.props.EnumProperty(
        name="Default Processing Mode",
        items=[
            ("AUTO", "Auto Generate", "Automatically generate terrain based on GPX"),
            ("MAPBOX", "Download Terrain", "Download terrain from Mapbox"),
        ],
        default="AUTO",
    )

    download_quality: bpy.props.EnumProperty(
        name="Download Quality",
        items=[
            ("HIGH", "High", "High resolution"),
            ("MEDIUM", "Medium", "Medium resolution"),
            ("LOW", "Low", "Low resolution"),
        ],
        default="MEDIUM",
    )

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text=t("Mapbox Configuration"))
        box.prop(self, "mapbox_access_token", text=t("Mapbox Access Token"))
        box.prop(self, "default_process_mode", text=t("Default Processing Mode"))
        box.prop(self, "download_quality", text=t("Download Quality"))


_classes = (
    Route2WorldPreferences,
    Route2WorldProperties,
    Route2WorldScatterProperties,
    ROUTE2WORLD_OT_GenerateFromGpx,
    ROUTE2WORLD_OT_ApplyTextures,
    ROUTE2WORLD_OT_SetupPaintMask,
    ROUTE2WORLD_OT_ApplyTerrainTransition,
    ROUTE2WORLD_OT_ScatterRoadsideAssets,
    ROUTE2WORLD_PT_Main,
    ROUTE2WORLD_PT_Step1Generate,
    ROUTE2WORLD_PT_Step2Textures,
    ROUTE2WORLD_PT_Step3PostProcess,
    ROUTE2WORLD_PT_Procedural,
)


def register():
    for c in _classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.route2world = bpy.props.PointerProperty(type=Route2WorldProperties)
    bpy.types.Scene.route2world_scatter = bpy.props.PointerProperty(type=Route2WorldScatterProperties)


def unregister():
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
    del bpy.types.Scene.route2world
    del bpy.types.Scene.route2world_scatter

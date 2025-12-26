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

from .ui import ROUTE2WORLD_PT_Main, Route2WorldProperties
from .ops import ROUTE2WORLD_OT_GenerateFromGpx, ROUTE2WORLD_OT_SetupPaintMask
from .scatter_ops import ROUTE2WORLD_OT_ScatterRoadsideAssets
from .scatter_ui import ROUTE2WORLD_PT_Procedural, Route2WorldScatterProperties


_classes = (
    Route2WorldProperties,
    Route2WorldScatterProperties,
    ROUTE2WORLD_OT_GenerateFromGpx,
    ROUTE2WORLD_OT_SetupPaintMask,
    ROUTE2WORLD_OT_ScatterRoadsideAssets,
    ROUTE2WORLD_PT_Main,
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

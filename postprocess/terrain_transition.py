import bpy

from ..gui.translations import t


NODE_GROUP_NAME = "R2W_TerrainTransition"
MODIFIER_NAME = "R2W_TerrainTransition"


def _new_node(nt: bpy.types.NodeTree, node_type: str, x: float, y: float) -> bpy.types.Node:
    n = nt.nodes.new(node_type)
    n.location = (x, y)
    return n


def _interface_sockets(node_group: bpy.types.NodeTree, in_out: str):
    if hasattr(node_group, "interface"):
        for item in node_group.interface.items_tree:
            if getattr(item, "item_type", None) == "SOCKET" and getattr(item, "in_out", None) == in_out:
                yield item
        return
    sockets = node_group.inputs if in_out == "INPUT" else node_group.outputs
    for s in sockets:
        yield s


def _find_socket(node_group: bpy.types.NodeTree, name: str, in_out: str):
    for s in _interface_sockets(node_group, in_out):
        if getattr(s, "name", "") == name:
            return s
    return None


def _ensure_socket(node_group: bpy.types.NodeTree, *, name: str, in_out: str, socket_type: str):
    s = _find_socket(node_group, name, in_out)
    if s is not None:
        return s
    if hasattr(node_group, "interface"):
        return node_group.interface.new_socket(name=name, in_out=in_out, socket_type=socket_type)
    if in_out == "INPUT":
        return node_group.inputs.new(socket_type, name)
    return node_group.outputs.new(socket_type, name)


def ensure_terrain_transition_node_group() -> bpy.types.NodeTree:
    ng = bpy.data.node_groups.get(NODE_GROUP_NAME)
    if ng is None or getattr(ng, "bl_idname", "") != "GeometryNodeTree":
        ng = bpy.data.node_groups.new(NODE_GROUP_NAME, "GeometryNodeTree")

    _ensure_socket(ng, name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    _ensure_socket(ng, name="Road", in_out="INPUT", socket_type="NodeSocketObject")
    w = _ensure_socket(ng, name="Transition Width (m)", in_out="INPUT", socket_type="NodeSocketFloat")
    flat_w = _ensure_socket(ng, name="Flat Width (m)", in_out="INPUT", socket_type="NodeSocketFloat")
    c = _ensure_socket(ng, name="Clearance (m)", in_out="INPUT", socket_type="NodeSocketFloat")
    subd = _ensure_socket(ng, name="Subdivide Levels", in_out="INPUT", socket_type="NodeSocketInt")
    _ensure_socket(ng, name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    if hasattr(w, "default_value"):
        w.default_value = 10.0
    if hasattr(flat_w, "default_value"):
        flat_w.default_value = 1.0
    if hasattr(c, "default_value"):
        c.default_value = 0.02
    if hasattr(subd, "default_value"):
        subd.default_value = 0

    nt = ng
    nt.nodes.clear()
    nt.links.clear()

    group_in = _new_node(nt, "NodeGroupInput", -900, 0)
    group_out = _new_node(nt, "NodeGroupOutput", 900, 0)
    if hasattr(group_out, "is_active_output"):
        group_out.is_active_output = True

    pos = _new_node(nt, "GeometryNodeInputPosition", -700, 200)

    obj_info = _new_node(nt, "GeometryNodeObjectInfo", -700, -40)
    if "As Instance" in obj_info.inputs:
        obj_info.inputs["As Instance"].default_value = False

    prox = _new_node(nt, "GeometryNodeProximity", -480, -40)
    prox.target_element = "FACES"

    subd_mesh = _new_node(nt, "GeometryNodeSubdivideMesh", -260, 0)

    sub = _new_node(nt, "ShaderNodeVectorMath", -260, 220)
    sub.operation = "SUBTRACT"

    sep = _new_node(nt, "ShaderNodeSeparateXYZ", -40, 220)
    comb_xy = _new_node(nt, "ShaderNodeCombineXYZ", 180, 220)
    comb_xy.inputs["Z"].default_value = 0.0

    length = _new_node(nt, "ShaderNodeVectorMath", 400, 220)
    length.operation = "LENGTH"

    sel_cmp = _new_node(nt, "FunctionNodeCompare", 400, 0)
    sel_cmp.data_type = "FLOAT"
    sel_cmp.operation = "LESS_EQUAL"

    mapr = _new_node(nt, "ShaderNodeMapRange", 620, 220)
    mapr.inputs["From Min"].default_value = 0.0
    mapr.inputs["To Min"].default_value = 1.0
    mapr.inputs["To Max"].default_value = 0.0
    mapr.clamp = True
    if hasattr(mapr, "interpolation_type"):
        mapr.interpolation_type = "SMOOTHSTEP"

    sep_pos = _new_node(nt, "ShaderNodeSeparateXYZ", -480, 420)

    sep_prox = _new_node(nt, "ShaderNodeSeparateXYZ", -40, -200)
    sub_clear = _new_node(nt, "ShaderNodeMath", 180, -200)
    sub_clear.operation = "SUBTRACT"

    mix_final = _new_node(nt, "ShaderNodeMix", 840, 320)
    mix_final.data_type = "FLOAT"

    comb_final = _new_node(nt, "ShaderNodeCombineXYZ", 620, 420)
    set_pos = _new_node(nt, "GeometryNodeSetPosition", 700, 120)

    nt.links.new(group_in.outputs["Road"], obj_info.inputs["Object"])
    nt.links.new(obj_info.outputs["Geometry"], prox.inputs["Target"])

    nt.links.new(pos.outputs["Position"], prox.inputs["Source Position"])
    nt.links.new(pos.outputs["Position"], sub.inputs[0])
    nt.links.new(prox.outputs["Position"], sub.inputs[1])

    nt.links.new(sub.outputs["Vector"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["X"], comb_xy.inputs["X"])
    nt.links.new(sep.outputs["Y"], comb_xy.inputs["Y"])
    nt.links.new(comb_xy.outputs["Vector"], length.inputs[0])

    nt.links.new(length.outputs["Value"], sel_cmp.inputs[2])
    nt.links.new(group_in.outputs["Transition Width (m)"], sel_cmp.inputs[3])

    nt.links.new(length.outputs["Value"], mapr.inputs["Value"])
    nt.links.new(group_in.outputs["Flat Width (m)"], mapr.inputs["From Min"])
    nt.links.new(group_in.outputs["Transition Width (m)"], mapr.inputs["From Max"])

    nt.links.new(pos.outputs["Position"], sep_pos.inputs["Vector"])

    nt.links.new(prox.outputs["Position"], sep_prox.inputs["Vector"])
    nt.links.new(sep_prox.outputs["Z"], sub_clear.inputs[0])
    nt.links.new(group_in.outputs["Clearance (m)"], sub_clear.inputs[1])

    nt.links.new(mapr.outputs["Result"], mix_final.inputs["Factor"])
    nt.links.new(sep_pos.outputs["Z"], mix_final.inputs["A"])
    nt.links.new(sub_clear.outputs["Value"], mix_final.inputs["B"])

    nt.links.new(sep_pos.outputs["X"], comb_final.inputs["X"])
    nt.links.new(sep_pos.outputs["Y"], comb_final.inputs["Y"])
    nt.links.new(mix_final.outputs["Result"], comb_final.inputs["Z"])

    nt.links.new(group_in.outputs["Geometry"], subd_mesh.inputs["Mesh"])
    if "Level" in subd_mesh.inputs:
        nt.links.new(group_in.outputs["Subdivide Levels"], subd_mesh.inputs["Level"])
    if "Selection" in subd_mesh.inputs:
        nt.links.new(sel_cmp.outputs["Result"], subd_mesh.inputs["Selection"])

    nt.links.new(subd_mesh.outputs["Mesh"], set_pos.inputs["Geometry"])
    nt.links.new(comb_final.outputs["Vector"], set_pos.inputs["Position"])
    nt.links.new(set_pos.outputs["Geometry"], group_out.inputs["Geometry"])

    return ng


def _set_socket_default(node_group: bpy.types.NodeTree, socket_name: str, value):
    s = _find_socket(node_group, socket_name, "INPUT")
    if s is None:
        return False
    if not hasattr(s, "default_value"):
        return False
    try:
        s.default_value = value
        return True
    except Exception:
        return False


def _set_modifier_input(mod: bpy.types.Modifier, socket_name: str, value) -> bool:
    try:
        mod[socket_name] = value
        return True
    except Exception:
        pass

    ng = getattr(mod, "node_group", None)
    if ng is not None and hasattr(ng, "interface"):
        for item in ng.interface.items_tree:
            if getattr(item, "item_type", None) != "SOCKET":
                continue
            if getattr(item, "in_out", None) != "INPUT":
                continue
            if getattr(item, "name", None) != socket_name:
                continue
            ident = getattr(item, "identifier", None)
            if ident:
                try:
                    mod[ident] = value
                    return True
                except Exception:
                    pass

    for k in mod.keys():
        if str(k).strip().lower() == socket_name.strip().lower():
            try:
                mod[k] = value
                return True
            except Exception:
                pass
    return False


def apply_terrain_transition(
    *,
    terrain_obj: bpy.types.Object,
    road_obj: bpy.types.Object,
    transition_width_m: float,
    flat_width_m: float,
    clearance_m: float,
    subdivide_levels: int,
) -> str | None:
    if terrain_obj is None or terrain_obj.type != "MESH":
        return "Terrain object is not a mesh"
    if road_obj is None or road_obj.type != "MESH":
        return "Road object is not a mesh"

    ng = ensure_terrain_transition_node_group()
    _set_socket_default(ng, "Road", road_obj)
    _set_socket_default(ng, "Transition Width (m)", float(max(0.0, transition_width_m)))
    _set_socket_default(ng, "Flat Width (m)", float(max(0.0, flat_width_m)))
    _set_socket_default(ng, "Clearance (m)", float(max(0.0, clearance_m)))
    _set_socket_default(ng, "Subdivide Levels", int(max(0, subdivide_levels)))

    mod = terrain_obj.modifiers.get(MODIFIER_NAME)
    if mod is None:
        mod = terrain_obj.modifiers.new(MODIFIER_NAME, "NODES")

    mod.node_group = ng

    _set_modifier_input(mod, "Road", road_obj)
    _set_modifier_input(mod, "Transition Width (m)", float(max(0.0, transition_width_m)))
    _set_modifier_input(mod, "Flat Width (m)", float(max(0.0, flat_width_m)))
    _set_modifier_input(mod, "Clearance (m)", float(max(0.0, clearance_m)))
    _set_modifier_input(mod, "Subdivide Levels", int(max(0, subdivide_levels)))
    return None


class ROUTE2WORLD_OT_ApplyTerrainTransition(bpy.types.Operator):
    bl_idname = "route2world.apply_terrain_transition"
    bl_label = t("Apply Terrain Transition")
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        p = context.scene.route2world
        terrain_obj = getattr(p, "terrain_transition_terrain_obj", None) or bpy.data.objects.get("RWB_Terrain")
        if terrain_obj is None and context.active_object is not None and context.active_object.type == "MESH":
            terrain_obj = context.active_object

        road_obj = getattr(p, "terrain_transition_road_obj", None) or bpy.data.objects.get("RWB_Road")

        err = apply_terrain_transition(
            terrain_obj=terrain_obj,
            road_obj=road_obj,
            transition_width_m=float(getattr(p, "terrain_transition_width_m", 10.0)),
            flat_width_m=float(getattr(p, "terrain_transition_flat_width_m", 1.0)),
            clearance_m=float(getattr(p, "terrain_transition_clearance_m", 0.02)),
            subdivide_levels=int(getattr(p, "terrain_transition_subdivide_levels", 0)),
        )
        if err:
            self.report({"ERROR"}, err)
            return {"CANCELLED"}

        return {"FINISHED"}

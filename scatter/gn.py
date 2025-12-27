from __future__ import annotations

import bpy


NODE_GROUP_NAME = "R2W_ScatterInstances"
MODIFIER_NAME = "R2W_ScatterInstances"

ATTR_CATEGORY = "r2w_category"
ATTR_PROTO_INDEX = "r2w_proto_index"
ATTR_ROT_Z = "r2w_rot_z"
ATTR_SCALE = "r2w_scale"


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


def _ensure_gn_node_group() -> bpy.types.NodeTree:
    ng = bpy.data.node_groups.get(NODE_GROUP_NAME)
    if ng is not None and getattr(ng, "bl_idname", "") == "GeometryNodeTree":
        return ng

    ng = bpy.data.node_groups.new(NODE_GROUP_NAME, "GeometryNodeTree")
    _ensure_socket(ng, name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    _ensure_socket(ng, name="Building Library", in_out="INPUT", socket_type="NodeSocketCollection")
    _ensure_socket(ng, name="Tree Library", in_out="INPUT", socket_type="NodeSocketCollection")
    _ensure_socket(ng, name="Grass Library", in_out="INPUT", socket_type="NodeSocketCollection")
    _ensure_socket(ng, name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    nt = ng
    nt.nodes.clear()
    nt.links.clear()

    group_in = _new_node(nt, "NodeGroupInput", -900, 0)
    group_out = _new_node(nt, "NodeGroupOutput", 1100, 0)
    if hasattr(group_out, "is_active_output"):
        group_out.is_active_output = True

    named_cat = _new_node(nt, "GeometryNodeInputNamedAttribute", -700, 220)
    named_cat.data_type = "INT"
    named_cat.inputs["Name"].default_value = ATTR_CATEGORY

    named_idx = _new_node(nt, "GeometryNodeInputNamedAttribute", -700, 60)
    named_idx.data_type = "INT"
    named_idx.inputs["Name"].default_value = ATTR_PROTO_INDEX

    named_rot = _new_node(nt, "GeometryNodeInputNamedAttribute", -700, -100)
    named_rot.data_type = "FLOAT"
    named_rot.inputs["Name"].default_value = ATTR_ROT_Z

    named_scale = _new_node(nt, "GeometryNodeInputNamedAttribute", -700, -260)
    named_scale.data_type = "FLOAT"
    named_scale.inputs["Name"].default_value = ATTR_SCALE

    join = _new_node(nt, "GeometryNodeJoinGeometry", 860, 0)

    def _category_branch(cat_id: int, lib_input_name: str, y: float):
        eq = _new_node(nt, "FunctionNodeCompare", -420, y + 240)
        eq.data_type = "INT"
        eq.operation = "EQUAL"
        eq.inputs[3].default_value = int(cat_id)
        nt.links.new(named_cat.outputs["Attribute"], eq.inputs[2])

        sep = _new_node(nt, "GeometryNodeSeparateGeometry", -220, y + 240)
        sep.domain = "POINT"
        nt.links.new(group_in.outputs["Geometry"], sep.inputs["Geometry"])
        nt.links.new(eq.outputs["Result"], sep.inputs["Selection"])

        lib = _new_node(nt, "GeometryNodeCollectionInfo", -220, y + 40)
        if "Collection" in lib.inputs:
            nt.links.new(group_in.outputs[lib_input_name], lib.inputs["Collection"])
        if hasattr(lib, "separate_children"):
            lib.separate_children = True
        if hasattr(lib, "reset_children"):
            lib.reset_children = True

        rot_euler = _new_node(nt, "ShaderNodeCombineXYZ", 40, y + 20)
        nt.links.new(named_rot.outputs["Attribute"], rot_euler.inputs["Z"])

        rot = _new_node(nt, "FunctionNodeEulerToRotation", 260, y + 20)
        nt.links.new(rot_euler.outputs["Vector"], rot.inputs["Euler"])

        sc = _new_node(nt, "ShaderNodeCombineXYZ", 260, y - 160)
        nt.links.new(named_scale.outputs["Attribute"], sc.inputs["X"])
        nt.links.new(named_scale.outputs["Attribute"], sc.inputs["Y"])
        nt.links.new(named_scale.outputs["Attribute"], sc.inputs["Z"])

        inst = _new_node(nt, "GeometryNodeInstanceOnPoints", 520, y + 140)
        if "Pick Instance" in inst.inputs:
            inst.inputs["Pick Instance"].default_value = True
        if "Pick Instance" in inst.inputs and inst.inputs["Pick Instance"].is_linked:
            pass
        if hasattr(inst, "pick_instance"):
            inst.pick_instance = True
        nt.links.new(sep.outputs["Selection"], inst.inputs["Points"])
        if "Instances" in inst.inputs:
            nt.links.new(lib.outputs["Instances"], inst.inputs["Instance"])
        else:
            nt.links.new(lib.outputs[0], inst.inputs[1])

        if "Instance Index" in inst.inputs:
            nt.links.new(named_idx.outputs["Attribute"], inst.inputs["Instance Index"])

        if "Rotation" in inst.inputs:
            nt.links.new(rot.outputs["Rotation"], inst.inputs["Rotation"])

        if "Scale" in inst.inputs:
            nt.links.new(sc.outputs["Vector"], inst.inputs["Scale"])

        nt.links.new(inst.outputs["Instances"], join.inputs["Geometry"])

    _category_branch(0, "Building Library", 240)
    _category_branch(1, "Tree Library", -120)
    _category_branch(2, "Grass Library", -480)

    nt.links.new(join.outputs["Geometry"], group_out.inputs["Geometry"])
    return ng


def ensure_library_collection(name: str) -> bpy.types.Collection:
    c = bpy.data.collections.get(name)
    if c is not None:
        return c
    c = bpy.data.collections.new(name)
    return c


def build_category_library(
    *,
    name: str,
    prototypes: list[bpy.types.Collection],
) -> bpy.types.Collection:
    lib = ensure_library_collection(name)

    for ob in list(lib.objects):
        try:
            lib.objects.unlink(ob)
        except Exception:
            pass
        try:
            bpy.data.objects.remove(ob)
        except Exception:
            pass

    for proto in prototypes:
        inst = bpy.data.objects.new(f"{name}_Proto", None)
        inst.empty_display_type = "PLAIN_AXES"
        inst.instance_type = "COLLECTION"
        inst.instance_collection = proto
        inst.hide_viewport = True
        inst.hide_render = True
        inst.hide_select = True
        lib.objects.link(inst)

    lib.hide_viewport = True
    lib.hide_render = True
    lib.hide_select = True
    return lib


def apply_scatter_instances_modifier(
    *,
    points_obj: bpy.types.Object,
    building_lib: bpy.types.Collection | None,
    tree_lib: bpy.types.Collection | None,
    grass_lib: bpy.types.Collection | None,
) -> str | None:
    if points_obj is None or points_obj.type != "MESH":
        return "Scatter points object is not a mesh"

    ng = _ensure_gn_node_group()

    mod = points_obj.modifiers.get(MODIFIER_NAME)
    if mod is None:
        mod = points_obj.modifiers.new(MODIFIER_NAME, "NODES")
    mod.node_group = ng

    if building_lib is not None:
        try:
            mod["Building Library"] = building_lib
        except Exception:
            pass
    if tree_lib is not None:
        try:
            mod["Tree Library"] = tree_lib
        except Exception:
            pass
    if grass_lib is not None:
        try:
            mod["Grass Library"] = grass_lib
        except Exception:
            pass

    if hasattr(ng, "interface"):
        for item in ng.interface.items_tree:
            if getattr(item, "item_type", None) != "SOCKET":
                continue
            if getattr(item, "in_out", None) != "INPUT":
                continue
            if getattr(item, "name", None) == "Building Library" and building_lib is not None:
                try:
                    mod[item.identifier] = building_lib
                except Exception:
                    pass
            if getattr(item, "name", None) == "Tree Library" and tree_lib is not None:
                try:
                    mod[item.identifier] = tree_lib
                except Exception:
                    pass
            if getattr(item, "name", None) == "Grass Library" and grass_lib is not None:
                try:
                    mod[item.identifier] = grass_lib
                except Exception:
                    pass

    return None


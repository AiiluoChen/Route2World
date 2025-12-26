from __future__ import annotations

import os
import random
from dataclasses import dataclass

import bpy


_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".exr", ".hdr")


def _addon_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def default_texture_root() -> str:
    return os.path.join(_addon_dir(), "Texture")


@dataclass(frozen=True)
class TextureSet:
    name: str
    color: str | None
    ao: str | None
    roughness: str | None
    normal: str | None
    displacement: str | None


def _find_first_file(folder: str, patterns: list[str]) -> str | None:
    try:
        for fn in os.listdir(folder):
            low = fn.lower()
            if not low.endswith(_IMAGE_EXTS):
                continue
            for p in patterns:
                if p in low:
                    full = os.path.join(folder, fn)
                    if os.path.isfile(full):
                        return full
    except FileNotFoundError:
        return None
    return None


def _find_any_image(folder: str) -> str | None:
    try:
        for fn in os.listdir(folder):
            if fn.lower().endswith(_IMAGE_EXTS):
                full = os.path.join(folder, fn)
                if os.path.isfile(full):
                    return full
    except FileNotFoundError:
        return None
    return None


def _collect_texture_sets(category_dir: str) -> list[TextureSet]:
    sets: list[TextureSet] = []
    try:
        entries = sorted(os.listdir(category_dir))
    except FileNotFoundError:
        return sets

    for entry in entries:
        full = os.path.join(category_dir, entry)
        if os.path.isdir(full):
            color = _find_first_file(full, ["_color", "albedo", "diffuse", "basecolor"])
            if color is None:
                color = _find_any_image(full)
            ao = _find_first_file(full, ["ambientocclusion", "_ambientocclusion", "_ao", "ao"])
            roughness = _find_first_file(full, ["_roughness", "roughness"])
            normal = _find_first_file(full, ["_normalgl", "normalgl"])
            if normal is None:
                candidate = _find_first_file(full, ["_normal", "normal"])
                if candidate is not None and "normaldx" not in os.path.basename(candidate).lower():
                    normal = candidate
            displacement = _find_first_file(full, ["_displacement", "displacement", "height"])
            sets.append(
                TextureSet(
                    name=entry,
                    color=color,
                    ao=ao,
                    roughness=roughness,
                    normal=normal,
                    displacement=displacement,
                )
            )
        elif os.path.isfile(full) and entry.lower().endswith(_IMAGE_EXTS):
            sets.append(
                TextureSet(
                    name=os.path.splitext(entry)[0],
                    color=full,
                    ao=None,
                    roughness=None,
                    normal=None,
                    displacement=None,
                )
            )

    return sets


def _load_image(path: str | None, *, is_data: bool) -> bpy.types.Image | None:
    if not path:
        return None
    if not os.path.exists(path):
        return None
    try:
        img = bpy.data.images.load(path, check_existing=True)
    except RuntimeError:
        return None
    try:
        img.colorspace_settings.name = "Non-Color" if is_data else "sRGB"
    except Exception:
        pass
    return img


def _ensure_material(name: str) -> bpy.types.Material:
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    return mat


def _set_active_material(obj: bpy.types.Object, mat: bpy.types.Material) -> None:
    if obj.data is None:
        return
    mats = getattr(obj.data, "materials", None)
    if mats is None:
        return
    if len(mats) == 0:
        mats.append(mat)
    else:
        mats[0] = mat


def _mesh_z_bounds_local(obj: bpy.types.Object) -> tuple[float, float] | None:
    mesh = obj.data
    if not isinstance(mesh, bpy.types.Mesh):
        return None
    if not mesh.vertices:
        return None
    min_z = float("inf")
    max_z = float("-inf")
    for v in mesh.vertices:
        z = float(v.co.z)
        if z < min_z:
            min_z = z
        if z > max_z:
            max_z = z
    if min_z == float("inf") or max_z == float("-inf"):
        return None
    if max_z - min_z <= 1e-8:
        return (min_z, min_z + 1.0)
    return (min_z, max_z)


def _new_node(nt: bpy.types.NodeTree, node_type: str, x: float, y: float) -> bpy.types.Node:
    n = nt.nodes.new(node_type)
    n.location = (x, y)
    return n


def _mix_factor_from_noise(nt: bpy.types.NodeTree, vec_socket, *, w: float, x: float, y: float):
    noise = _new_node(nt, "ShaderNodeTexNoise", x, y)
    if "W" in noise.inputs:
        noise.inputs["W"].default_value = float(w)
        nt.links.new(vec_socket, noise.inputs["Vector"])
    else:
        comb = _new_node(nt, "ShaderNodeCombineXYZ", x - 220, y - 220)
        comb.inputs["X"].default_value = float(w * 19.19)
        comb.inputs["Y"].default_value = float(w * 7.73)
        comb.inputs["Z"].default_value = float(w * 3.31)
        add = _new_node(nt, "ShaderNodeVectorMath", x - 40, y - 220)
        add.operation = "ADD"
        nt.links.new(vec_socket, add.inputs[0])
        nt.links.new(comb.outputs["Vector"], add.inputs[1])
        nt.links.new(add.outputs["Vector"], noise.inputs["Vector"])
    ramp = _new_node(nt, "ShaderNodeMapRange", x + 220, y)
    ramp.inputs["From Min"].default_value = 0.45
    ramp.inputs["From Max"].default_value = 0.55
    ramp.inputs["To Min"].default_value = 0.0
    ramp.inputs["To Max"].default_value = 1.0
    ramp.clamp = True
    if hasattr(ramp, "interpolation_type"):
        ramp.interpolation_type = "SMOOTHSTEP"
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Value"])
    return ramp.outputs["Result"]


def _texture_set_nodes(
    nt: bpy.types.NodeTree,
    uv_socket,
    t: TextureSet,
    *,
    x: float,
    y: float,
) -> tuple:
    color_img = _load_image(t.color, is_data=False)
    ao_img = _load_image(t.ao, is_data=True)
    rough_img = _load_image(t.roughness, is_data=True)
    normal_img = _load_image(t.normal, is_data=True)
    disp_img = _load_image(t.displacement, is_data=True)

    if color_img is None:
        rgb = _new_node(nt, "ShaderNodeRGB", x, y)
        rgb.outputs["Color"].default_value = (0.5, 0.5, 0.5, 1.0)
        color_out = rgb.outputs["Color"]
    else:
        tex = _new_node(nt, "ShaderNodeTexImage", x, y)
        tex.image = color_img
        nt.links.new(uv_socket, tex.inputs["Vector"])
        color_out = tex.outputs["Color"]

    if ao_img is not None:
        aotex = _new_node(nt, "ShaderNodeTexImage", x + 220, y + 20)
        aotex.image = ao_img
        nt.links.new(uv_socket, aotex.inputs["Vector"])
        aobw = _new_node(nt, "ShaderNodeRGBToBW", x + 440, y + 20)
        nt.links.new(aotex.outputs["Color"], aobw.inputs["Color"])
        mul = _new_node(nt, "ShaderNodeMixRGB", x + 660, y)
        mul.blend_type = "MULTIPLY"
        mul.inputs["Fac"].default_value = 1.0
        nt.links.new(color_out, mul.inputs["Color1"])
        nt.links.new(aobw.outputs["Val"], mul.inputs["Color2"])
        color_out = mul.outputs["Color"]

    if rough_img is None:
        val = _new_node(nt, "ShaderNodeValue", x, y - 220)
        val.outputs["Value"].default_value = 0.65
        rough_out = val.outputs["Value"]
    else:
        rtex = _new_node(nt, "ShaderNodeTexImage", x, y - 220)
        rtex.image = rough_img
        nt.links.new(uv_socket, rtex.inputs["Vector"])
        rbw = _new_node(nt, "ShaderNodeRGBToBW", x + 220, y - 220)
        nt.links.new(rtex.outputs["Color"], rbw.inputs["Color"])
        rough_out = rbw.outputs["Val"]

    if normal_img is None:
        nvec = _new_node(nt, "ShaderNodeCombineXYZ", x, y - 440)
        nvec.inputs["Z"].default_value = 1.0
        normal_out = nvec.outputs["Vector"]
    else:
        ntex = _new_node(nt, "ShaderNodeTexImage", x, y - 440)
        ntex.image = normal_img
        nt.links.new(uv_socket, ntex.inputs["Vector"])
        nmap = _new_node(nt, "ShaderNodeNormalMap", x + 220, y - 440)
        nt.links.new(ntex.outputs["Color"], nmap.inputs["Color"])
        normal_out = nmap.outputs["Normal"]

    if disp_img is None:
        dval = _new_node(nt, "ShaderNodeValue", x, y - 660)
        dval.outputs["Value"].default_value = 0.0
        disp_out = dval.outputs["Value"]
    else:
        dtex = _new_node(nt, "ShaderNodeTexImage", x, y - 660)
        dtex.image = disp_img
        nt.links.new(uv_socket, dtex.inputs["Vector"])
        dbw = _new_node(nt, "ShaderNodeRGBToBW", x + 220, y - 660)
        nt.links.new(dtex.outputs["Color"], dbw.inputs["Color"])
        disp_out = dbw.outputs["Val"]

    return color_out, rough_out, normal_out, disp_out


def _mix_layers(nt: bpy.types.NodeTree, a, b, factor, *, x: float, y: float) -> tuple:
    mix_c = _new_node(nt, "ShaderNodeMixRGB", x, y)
    mix_c.blend_type = "MIX"
    mix_c.inputs["Fac"].default_value = 0.0
    nt.links.new(factor, mix_c.inputs["Fac"])
    nt.links.new(a[0], mix_c.inputs["Color1"])
    nt.links.new(b[0], mix_c.inputs["Color2"])

    mix_r = _new_node(nt, "ShaderNodeMix", x, y - 220)
    mix_r.data_type = "FLOAT"
    nt.links.new(factor, mix_r.inputs["Factor"])
    nt.links.new(a[1], mix_r.inputs["A"])
    nt.links.new(b[1], mix_r.inputs["B"])

    mix_n = _new_node(nt, "ShaderNodeMix", x, y - 440)
    mix_n.data_type = "VECTOR"
    nt.links.new(factor, mix_n.inputs["Factor"])
    nt.links.new(a[2], mix_n.inputs["A"])
    nt.links.new(b[2], mix_n.inputs["B"])
    norm = _new_node(nt, "ShaderNodeVectorMath", x + 220, y - 440)
    norm.operation = "NORMALIZE"
    nt.links.new(mix_n.outputs["Result"], norm.inputs[0])

    mix_d = _new_node(nt, "ShaderNodeMix", x, y - 660)
    mix_d.data_type = "FLOAT"
    nt.links.new(factor, mix_d.inputs["Factor"])
    nt.links.new(a[3], mix_d.inputs["A"])
    nt.links.new(b[3], mix_d.inputs["B"])

    return (mix_c.outputs["Color"], mix_r.outputs["Result"], norm.outputs["Vector"], mix_d.outputs["Result"])


def _sparse_mask_from_noise(
    nt: bpy.types.NodeTree,
    noise_vec_socket,
    *,
    w: float,
    coverage: float,
    softness: float,
    x: float,
    y: float,
):
    noise = _new_node(nt, "ShaderNodeTexNoise", x, y)
    if "W" in noise.inputs:
        noise.inputs["W"].default_value = float(w)
        nt.links.new(noise_vec_socket, noise.inputs["Vector"])
    else:
        comb = _new_node(nt, "ShaderNodeCombineXYZ", x - 220, y - 220)
        comb.inputs["X"].default_value = float(w * 19.19)
        comb.inputs["Y"].default_value = float(w * 7.73)
        comb.inputs["Z"].default_value = float(w * 3.31)
        add = _new_node(nt, "ShaderNodeVectorMath", x - 40, y - 220)
        add.operation = "ADD"
        nt.links.new(noise_vec_socket, add.inputs[0])
        nt.links.new(comb.outputs["Vector"], add.inputs[1])
        nt.links.new(add.outputs["Vector"], noise.inputs["Vector"])

    c = max(0.01, min(0.99, float(coverage)))
    s = max(0.001, min(0.49, float(softness)))
    frm_min = max(0.0, min(1.0, c - s))
    frm_max = max(0.0, min(1.0, c + s))

    ramp = _new_node(nt, "ShaderNodeMapRange", x + 220, y)
    ramp.inputs["From Min"].default_value = float(frm_min)
    ramp.inputs["From Max"].default_value = float(frm_max)
    ramp.inputs["To Min"].default_value = 0.0
    ramp.inputs["To Max"].default_value = 1.0
    ramp.clamp = True
    if hasattr(ramp, "interpolation_type"):
        ramp.interpolation_type = "SMOOTHSTEP"
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Value"])
    return ramp.outputs["Result"]


def _build_category_mix(
    nt: bpy.types.NodeTree,
    uv_socket,
    noise_vec_socket,
    sets: list[TextureSet],
    *,
    seed: int,
    variants: int,
    dominant_min: float,
    dominant_max: float,
    coverage_min: float,
    coverage_max: float,
    softness: float,
    x: float,
    y: float,
) -> tuple:
    if not sets:
        rgb = _new_node(nt, "ShaderNodeRGB", x, y)
        rgb.outputs["Color"].default_value = (0.5, 0.5, 0.5, 1.0)
        val = _new_node(nt, "ShaderNodeValue", x, y - 220)
        val.outputs["Value"].default_value = 0.65
        nvec = _new_node(nt, "ShaderNodeCombineXYZ", x, y - 440)
        nvec.inputs["Z"].default_value = 1.0
        d = _new_node(nt, "ShaderNodeValue", x, y - 660)
        d.outputs["Value"].default_value = 0.0
        return (rgb.outputs["Color"], val.outputs["Value"], nvec.outputs["Vector"], d.outputs["Value"])

    rng = random.Random(int(seed))
    items = list(sets)
    rng.shuffle(items)
    # Support up to 4 variants for subdivision
    max_variants = min(4, max(1, variants))
    picked = items[: min(max_variants, len(items))]
    
    if len(picked) == 1:
        return _texture_set_nodes(nt, uv_socket, picked[0], x=x, y=y)

    # Create sub-region blending using Voronoi Smooth F1
    # This ensures "irregular but rounded polygon shapes" and "smooth transitions"
    
    vor = _new_node(nt, "ShaderNodeTexVoronoi", x + 400, y)
    vor.feature = "SMOOTH_F1"
    if "Vector" in vor.inputs:
        nt.links.new(noise_vec_socket, vor.inputs["Vector"])
    
    # Use Smoothness to control transition width (0.5-2m equivalent)
    # The 'softness' parameter can map to Smoothness
    if "Smoothness" in vor.inputs:
        vor.inputs["Smoothness"].default_value = max(0.0, min(1.0, float(softness) * 5.0)) # Scale up softness
    
    # Use Random Color (smoothed) to drive mixing
    col_out = vor.outputs.get("Color") or vor.outputs[0]
    
    sep = _new_node(nt, "ShaderNodeSeparateColor", x + 600, y)
    nt.links.new(col_out, sep.inputs[0])
    
    # Generate layers
    layers = []
    current_y = y
    for i, p in enumerate(picked):
        layers.append(_texture_set_nodes(nt, uv_socket, p, x=x, y=current_y))
        current_y -= 250 # Stagger nodes vertically
        
    # Mix layers based on Voronoi color channels
    # We have up to 4 layers: A, B, C, D
    # We have 3 smooth random values: R, G, B
    
    # Mix 0 and 1 using Red
    if len(layers) >= 2:
        mix01 = _mix_layers(nt, layers[0], layers[1], sep.outputs[0], x=x + 800, y=y)
    else:
        mix01 = layers[0]
        
    if len(layers) >= 3:
        # Mix (0-1) and 2 using Green
        mix012 = _mix_layers(nt, mix01, layers[2], sep.outputs[1], x=x + 1000, y=y)
    else:
        mix012 = mix01
        
    if len(layers) >= 4:
        # Mix (0-1-2) and 3 using Blue
        mix0123 = _mix_layers(nt, mix012, layers[3], sep.outputs[2], x=x + 1200, y=y)
        return mix0123
        
    return mix012



def _smoothstep(nt: bpy.types.NodeTree, value_socket, start_socket, end_socket, *, x: float, y: float):
    node = _new_node(nt, "ShaderNodeMapRange", x, y)
    node.inputs["To Min"].default_value = 0.0
    node.inputs["To Max"].default_value = 1.0
    node.clamp = True
    if hasattr(node, "interpolation_type"):
        node.interpolation_type = "SMOOTHSTEP"
    nt.links.new(value_socket, node.inputs["Value"])
    nt.links.new(start_socket, node.inputs["From Min"])
    nt.links.new(end_socket, node.inputs["From Max"])
    return node.outputs["Result"]


def apply_terrain_material(
    terrain_obj: bpy.types.Object,
    *,
    texture_root: str | None,
    seed: int,
    variants_per_category: int,
    ground_to_rock_ratio: float,
    rock_to_snow_ratio: float,
    height_blend: float,
    cliff_slope_start: float,
    cliff_slope_end: float,
    noise_scale: float,
    transition_width: float = 0.06,
) -> str | None:
    if terrain_obj.type != "MESH":
        return "Terrain object is not a mesh"

    root = bpy.path.abspath(texture_root) if texture_root else default_texture_root()
    ground_sets = _collect_texture_sets(os.path.join(root, "Ground"))
    rock_sets = _collect_texture_sets(os.path.join(root, "Rock"))
    snow_sets = _collect_texture_sets(os.path.join(root, "Snow"))
    cliff_sets = _collect_texture_sets(os.path.join(root, "Cliff"))

    z = _mesh_z_bounds_local(terrain_obj)
    if z is None:
        return "Terrain has no vertices"
    min_z, max_z = z

    mat = _ensure_material("RWB_Terrain_Mat")
    nt = mat.node_tree
    if nt is None:
        return "Failed to create terrain material node tree"
    nt.nodes.clear()
    nt.links.clear()

    out = _new_node(nt, "ShaderNodeOutputMaterial", 1400, 0)
    bsdf = _new_node(nt, "ShaderNodeBsdfPrincipled", 1180, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    texcoord = _new_node(nt, "ShaderNodeTexCoord", 0, 160)
    uv = texcoord.outputs.get("UV") or texcoord.outputs[0]

    mapping = _new_node(nt, "ShaderNodeMapping", 200, 160)
    mapping.inputs["Scale"].default_value = (float(noise_scale), float(noise_scale), 1.0)
    nt.links.new(uv, mapping.inputs["Vector"])
    noise_vec = mapping.outputs["Vector"]

    geom = _new_node(nt, "ShaderNodeNewGeometry", 0, -260)
    pos = geom.outputs.get("Position") or geom.outputs[0]
    normal = geom.outputs.get("Normal") or geom.outputs[1]

    sep_pos = _new_node(nt, "ShaderNodeSeparateXYZ", 220, -260)
    nt.links.new(pos, sep_pos.inputs["Vector"])
    z_socket = sep_pos.outputs["Z"]

    minz = _new_node(nt, "ShaderNodeValue", 0, -520)
    minz.outputs["Value"].default_value = float(min_z)
    maxz = _new_node(nt, "ShaderNodeValue", 0, -560)
    maxz.outputs["Value"].default_value = float(max_z)

    hmap = _new_node(nt, "ShaderNodeMapRange", 440, -260)
    hmap.inputs["To Min"].default_value = 0.0
    hmap.inputs["To Max"].default_value = 1.0
    hmap.clamp = True
    nt.links.new(z_socket, hmap.inputs["Value"])
    nt.links.new(minz.outputs["Value"], hmap.inputs["From Min"])
    nt.links.new(maxz.outputs["Value"], hmap.inputs["From Max"])
    h = hmap.outputs["Result"]

    r1 = _new_node(nt, "ShaderNodeValue", 0, -660)
    r1.outputs["Value"].default_value = float(max(0.0, min(1.0, ground_to_rock_ratio)))
    r2 = _new_node(nt, "ShaderNodeValue", 0, -700)
    r2.outputs["Value"].default_value = float(max(0.0, min(1.0, rock_to_snow_ratio)))
    bw = _new_node(nt, "ShaderNodeValue", 0, -740)
    bw.outputs["Value"].default_value = float(max(0.0, min(0.5, height_blend)))

    r1_lo = _new_node(nt, "ShaderNodeMath", 220, -660)
    r1_lo.operation = "SUBTRACT"
    nt.links.new(r1.outputs["Value"], r1_lo.inputs[0])
    nt.links.new(bw.outputs["Value"], r1_lo.inputs[1])
    r1_hi = _new_node(nt, "ShaderNodeMath", 220, -700)
    r1_hi.operation = "ADD"
    nt.links.new(r1.outputs["Value"], r1_hi.inputs[0])
    nt.links.new(bw.outputs["Value"], r1_hi.inputs[1])

    r2_lo = _new_node(nt, "ShaderNodeMath", 220, -780)
    r2_lo.operation = "SUBTRACT"
    nt.links.new(r2.outputs["Value"], r2_lo.inputs[0])
    nt.links.new(bw.outputs["Value"], r2_lo.inputs[1])
    r2_hi = _new_node(nt, "ShaderNodeMath", 220, -820)
    r2_hi.operation = "ADD"
    nt.links.new(r2.outputs["Value"], r2_hi.inputs[0])
    nt.links.new(bw.outputs["Value"], r2_hi.inputs[1])

    t1 = _smoothstep(nt, h, r1_lo.outputs["Value"], r1_hi.outputs["Value"], x=680, y=-640)
    t2 = _smoothstep(nt, h, r2_lo.outputs["Value"], r2_hi.outputs["Value"], x=680, y=-760)

    # --- Manual Painting Override Logic ---
    # Attribute: Terrain_Region_Mask (R=Ground, G=Rock, B=Snow)
    attr = _new_node(nt, "ShaderNodeAttribute", 440, -1000)
    attr.attribute_name = "Terrain_Region_Mask"
    
    # Check if attribute exists (we assume user paints if attribute is present and non-black)
    # However, in shader nodes we just use the values. If 0,0,0, it has no effect.
    
    # Calculate procedural weights
    # W_snow = t2
    # W_rock = t1 * (1 - t2)
    # W_ground = (1 - t1) * (1 - t2)
    
    one_node = _new_node(nt, "ShaderNodeValue", 680, -900)
    one_node.outputs["Value"].default_value = 1.0
    
    sub_t2 = _new_node(nt, "ShaderNodeMath", 900, -900)
    sub_t2.operation = "SUBTRACT"
    nt.links.new(one_node.outputs["Value"], sub_t2.inputs[0])
    nt.links.new(t2, sub_t2.inputs[1]) # (1-t2)
    
    w_p_snow = t2
    
    w_p_rock = _new_node(nt, "ShaderNodeMath", 1100, -900)
    w_p_rock.operation = "MULTIPLY"
    nt.links.new(t1, w_p_rock.inputs[0])
    nt.links.new(sub_t2.outputs["Value"], w_p_rock.inputs[1])
    
    sub_t1 = _new_node(nt, "ShaderNodeMath", 900, -1000)
    sub_t1.operation = "SUBTRACT"
    nt.links.new(one_node.outputs["Value"], sub_t1.inputs[0])
    nt.links.new(t1, sub_t1.inputs[1]) # (1-t1)
    
    w_p_ground = _new_node(nt, "ShaderNodeMath", 1100, -1000)
    w_p_ground.operation = "MULTIPLY"
    nt.links.new(sub_t1.outputs["Value"], w_p_ground.inputs[0])
    nt.links.new(sub_t2.outputs["Value"], w_p_ground.inputs[1])
    
    # Mix with painted weights
    sep_attr = _new_node(nt, "ShaderNodeSeparateColor", 680, -1100)
    nt.links.new(attr.outputs["Color"], sep_attr.inputs[0])
    
    paint_ground = sep_attr.outputs[0] # R
    paint_rock = sep_attr.outputs[1]   # G
    paint_snow = sep_attr.outputs[2]   # B
    
    # Paint Mask = Clamp(R + G + B)
    add_gr = _new_node(nt, "ShaderNodeMath", 900, -1100)
    add_gr.operation = "ADD"
    nt.links.new(paint_ground, add_gr.inputs[0])
    nt.links.new(paint_rock, add_gr.inputs[1])
    
    paint_mask = _new_node(nt, "ShaderNodeMath", 1100, -1100)
    paint_mask.operation = "ADD"
    nt.links.new(add_gr.outputs["Value"], paint_mask.inputs[0])
    nt.links.new(paint_snow, paint_mask.inputs[1])
    paint_mask.use_clamp = True
    
    # Mix Weights
    # Final Ground
    w_f_ground = _new_node(nt, "ShaderNodeMix", 1300, -900)
    w_f_ground.data_type = "FLOAT"
    nt.links.new(paint_mask.outputs["Value"], w_f_ground.inputs["Factor"])
    nt.links.new(w_p_ground.outputs["Value"], w_f_ground.inputs["A"])
    nt.links.new(paint_ground, w_f_ground.inputs["B"])
    
    # Final Rock
    w_f_rock = _new_node(nt, "ShaderNodeMix", 1300, -1000)
    w_f_rock.data_type = "FLOAT"
    nt.links.new(paint_mask.outputs["Value"], w_f_rock.inputs["Factor"])
    nt.links.new(w_p_rock.outputs["Value"], w_f_rock.inputs["A"])
    nt.links.new(paint_rock, w_f_rock.inputs["B"])
    
    # Final Snow
    w_f_snow = _new_node(nt, "ShaderNodeMix", 1300, -1100)
    w_f_snow.data_type = "FLOAT"
    nt.links.new(paint_mask.outputs["Value"], w_f_snow.inputs["Factor"])
    nt.links.new(w_p_snow, w_f_snow.inputs["A"])
    nt.links.new(paint_snow, w_f_snow.inputs["B"])
    
    # Reconstruct t1, t2
    # t1_new = Rock / (Ground + Rock)
    add_gr_f = _new_node(nt, "ShaderNodeMath", 1500, -900)
    add_gr_f.operation = "ADD"
    nt.links.new(w_f_ground.outputs["Result"], add_gr_f.inputs[0])
    nt.links.new(w_f_rock.outputs["Result"], add_gr_f.inputs[1])
    
    # Safe divide
    div_t1 = _new_node(nt, "ShaderNodeMath", 1700, -900)
    div_t1.operation = "DIVIDE"
    nt.links.new(w_f_rock.outputs["Result"], div_t1.inputs[0])
    nt.links.new(add_gr_f.outputs["Value"], div_t1.inputs[1])
    
    t1 = div_t1.outputs["Value"]
    
    # t2_new = Snow / (Ground + Rock + Snow)
    add_total = _new_node(nt, "ShaderNodeMath", 1500, -1000)
    add_total.operation = "ADD"
    nt.links.new(add_gr_f.outputs["Value"], add_total.inputs[0])
    nt.links.new(w_f_snow.outputs["Result"], add_total.inputs[1])
    
    div_t2 = _new_node(nt, "ShaderNodeMath", 1700, -1000)
    div_t2.operation = "DIVIDE"
    nt.links.new(w_f_snow.outputs["Result"], div_t2.inputs[0])
    nt.links.new(add_total.outputs["Value"], div_t2.inputs[1])
    
    t2 = div_t2.outputs["Value"]
    
    # --- End Manual Painting Override Logic ---

    one = _new_node(nt, "ShaderNodeValue", 440, -880)

    one.outputs["Value"].default_value = 1.0

    inv_t1 = _new_node(nt, "ShaderNodeMath", 900, -640)
    inv_t1.operation = "SUBTRACT"
    nt.links.new(one.outputs["Value"], inv_t1.inputs[0])
    nt.links.new(t1, inv_t1.inputs[1])
    ground_w = inv_t1.outputs["Value"]

    inv_t2 = _new_node(nt, "ShaderNodeMath", 900, -760)
    inv_t2.operation = "SUBTRACT"
    nt.links.new(one.outputs["Value"], inv_t2.inputs[0])
    nt.links.new(t2, inv_t2.inputs[1])

    rock_w = _new_node(nt, "ShaderNodeMath", 1120, -700)
    rock_w.operation = "MULTIPLY"
    nt.links.new(t1, rock_w.inputs[0])
    nt.links.new(inv_t2.outputs["Value"], rock_w.inputs[1])

    snow_w = t2

    ground_layer = _build_category_mix(
        nt,
        uv,
        noise_vec,
        ground_sets,
        seed=int(seed) ^ 0x13579,
        variants=variants_per_category,
        dominant_min=0.80,
        dominant_max=1.0,
        coverage_min=0.72,
        coverage_max=0.88,
        softness=transition_width,
        x=0,
        y=520,
    )
    rock_layer = _build_category_mix(
        nt,
        uv,
        noise_vec,
        rock_sets,
        seed=int(seed) ^ 0x2468A,
        variants=variants_per_category,
        dominant_min=0.80,
        dominant_max=1.0,
        coverage_min=0.74,
        coverage_max=0.90,
        softness=transition_width,
        x=0,
        y=100,
    )
    snow_layer = _build_category_mix(
        nt,
        uv,
        noise_vec,
        snow_sets,
        seed=int(seed) ^ 0xABCDE,
        variants=variants_per_category,
        dominant_min=0.80,
        dominant_max=1.0,
        coverage_min=0.78,
        coverage_max=0.92,
        softness=transition_width,
        x=0,
        y=-320,
    )
    cliff_layer = _build_category_mix(
        nt,
        uv,
        noise_vec,
        cliff_sets,
        seed=int(seed) ^ 0x77777,
        variants=variants_per_category,
        dominant_min=0.80,
        dominant_max=1.0,
        coverage_min=0.80,
        coverage_max=0.93,
        softness=transition_width,
        x=0,
        y=-760,
    )

    mix_gr = _new_node(nt, "ShaderNodeMixRGB", 760, 320)
    mix_gr.inputs["Fac"].default_value = 0.0
    nt.links.new(t1, mix_gr.inputs["Fac"])
    nt.links.new(ground_layer[0], mix_gr.inputs["Color1"])
    nt.links.new(rock_layer[0], mix_gr.inputs["Color2"])

    mix_rs = _new_node(nt, "ShaderNodeMixRGB", 980, 320)
    mix_rs.inputs["Fac"].default_value = 0.0
    nt.links.new(t2, mix_rs.inputs["Fac"])
    nt.links.new(mix_gr.outputs["Color"], mix_rs.inputs["Color1"])
    nt.links.new(snow_layer[0], mix_rs.inputs["Color2"])
    base_color = mix_rs.outputs["Color"]

    mixr_gr = _new_node(nt, "ShaderNodeMix", 760, 100)
    mixr_gr.data_type = "FLOAT"
    nt.links.new(t1, mixr_gr.inputs["Factor"])
    nt.links.new(ground_layer[1], mixr_gr.inputs["A"])
    nt.links.new(rock_layer[1], mixr_gr.inputs["B"])

    mixr_rs = _new_node(nt, "ShaderNodeMix", 980, 100)
    mixr_rs.data_type = "FLOAT"
    nt.links.new(t2, mixr_rs.inputs["Factor"])
    nt.links.new(mixr_gr.outputs["Result"], mixr_rs.inputs["A"])
    nt.links.new(snow_layer[1], mixr_rs.inputs["B"])
    base_rough = mixr_rs.outputs["Result"]

    mixn_gr = _new_node(nt, "ShaderNodeMix", 760, -120)
    mixn_gr.data_type = "VECTOR"
    nt.links.new(t1, mixn_gr.inputs["Factor"])
    nt.links.new(ground_layer[2], mixn_gr.inputs["A"])
    nt.links.new(rock_layer[2], mixn_gr.inputs["B"])

    mixn_rs = _new_node(nt, "ShaderNodeMix", 980, -120)
    mixn_rs.data_type = "VECTOR"
    nt.links.new(t2, mixn_rs.inputs["Factor"])
    nt.links.new(mixn_gr.outputs["Result"], mixn_rs.inputs["A"])
    nt.links.new(snow_layer[2], mixn_rs.inputs["B"])

    base_norm = _new_node(nt, "ShaderNodeVectorMath", 1200, -120)
    base_norm.operation = "NORMALIZE"
    nt.links.new(mixn_rs.outputs["Result"], base_norm.inputs[0])

    mixd_gr = _new_node(nt, "ShaderNodeMix", 760, -340)
    mixd_gr.data_type = "FLOAT"
    nt.links.new(t1, mixd_gr.inputs["Factor"])
    nt.links.new(ground_layer[3], mixd_gr.inputs["A"])
    nt.links.new(rock_layer[3], mixd_gr.inputs["B"])

    mixd_rs = _new_node(nt, "ShaderNodeMix", 980, -340)
    mixd_rs.data_type = "FLOAT"
    nt.links.new(t2, mixd_rs.inputs["Factor"])
    nt.links.new(mixd_gr.outputs["Result"], mixd_rs.inputs["A"])
    nt.links.new(snow_layer[3], mixd_rs.inputs["B"])
    base_disp = mixd_rs.outputs["Result"]

    sep_n = _new_node(nt, "ShaderNodeSeparateXYZ", 220, -40)
    nt.links.new(normal, sep_n.inputs["Vector"])
    abs_z = _new_node(nt, "ShaderNodeMath", 440, -40)
    abs_z.operation = "ABSOLUTE"
    nt.links.new(sep_n.outputs["Z"], abs_z.inputs[0])
    steep = _new_node(nt, "ShaderNodeMath", 640, -40)
    steep.operation = "SUBTRACT"
    nt.links.new(one.outputs["Value"], steep.inputs[0])
    nt.links.new(abs_z.outputs["Value"], steep.inputs[1])

    cliff_start = _new_node(nt, "ShaderNodeValue", 440, -140)
    cliff_start.outputs["Value"].default_value = float(max(0.0, min(1.0, cliff_slope_start)))
    cliff_end = _new_node(nt, "ShaderNodeValue", 440, -180)
    cliff_end.outputs["Value"].default_value = float(max(0.0, min(1.0, cliff_slope_end)))
    cliff_f = _smoothstep(nt, steep.outputs["Value"], cliff_start.outputs["Value"], cliff_end.outputs["Value"], x=900, y=-40)

    cliff_mix_c = _new_node(nt, "ShaderNodeMixRGB", 1220, 320)
    cliff_mix_c.inputs["Fac"].default_value = 0.0
    nt.links.new(cliff_f, cliff_mix_c.inputs["Fac"])
    nt.links.new(base_color, cliff_mix_c.inputs["Color1"])
    nt.links.new(cliff_layer[0], cliff_mix_c.inputs["Color2"])

    cliff_mix_r = _new_node(nt, "ShaderNodeMix", 1220, 100)
    cliff_mix_r.data_type = "FLOAT"
    nt.links.new(cliff_f, cliff_mix_r.inputs["Factor"])
    nt.links.new(base_rough, cliff_mix_r.inputs["A"])
    nt.links.new(cliff_layer[1], cliff_mix_r.inputs["B"])

    cliff_mix_n = _new_node(nt, "ShaderNodeMix", 1220, -120)
    cliff_mix_n.data_type = "VECTOR"
    nt.links.new(cliff_f, cliff_mix_n.inputs["Factor"])
    nt.links.new(base_norm.outputs["Vector"], cliff_mix_n.inputs["A"])
    nt.links.new(cliff_layer[2], cliff_mix_n.inputs["B"])
    cliff_norm = _new_node(nt, "ShaderNodeVectorMath", 1420, -120)
    cliff_norm.operation = "NORMALIZE"
    nt.links.new(cliff_mix_n.outputs["Result"], cliff_norm.inputs[0])

    nt.links.new(cliff_mix_c.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(cliff_mix_r.outputs["Result"], bsdf.inputs["Roughness"])
    nt.links.new(cliff_norm.outputs["Vector"], bsdf.inputs["Normal"])

    cliff_mix_d = _new_node(nt, "ShaderNodeMix", 1220, -340)
    cliff_mix_d.data_type = "FLOAT"
    nt.links.new(cliff_f, cliff_mix_d.inputs["Factor"])
    nt.links.new(base_disp, cliff_mix_d.inputs["A"])
    nt.links.new(cliff_layer[3], cliff_mix_d.inputs["B"])

    disp = _new_node(nt, "ShaderNodeDisplacement", 1400, -340)
    disp.inputs["Midlevel"].default_value = 0.5
    disp.inputs["Scale"].default_value = 0.06
    nt.links.new(cliff_mix_d.outputs["Result"], disp.inputs["Height"])
    if "Displacement" in out.inputs:
        nt.links.new(disp.outputs["Displacement"], out.inputs["Displacement"])

    _set_active_material(terrain_obj, mat)
    return None


def apply_road_material(
    road_obj: bpy.types.Object,
    *,
    texture_root: str | None,
    seed: int,
    variants: int,
    noise_scale: float,
) -> str | None:
    if road_obj.type != "MESH":
        return "Road object is not a mesh"

    root = bpy.path.abspath(texture_root) if texture_root else default_texture_root()
    road_sets = _collect_texture_sets(os.path.join(root, "Road"))
    if not road_sets:
        return "No road textures found"

    mat = _ensure_material("RWB_Road_Mat")
    nt = mat.node_tree
    if nt is None:
        return "Failed to create road material node tree"
    nt.nodes.clear()
    nt.links.clear()

    out = _new_node(nt, "ShaderNodeOutputMaterial", 1180, 0)
    bsdf = _new_node(nt, "ShaderNodeBsdfPrincipled", 960, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    texcoord = _new_node(nt, "ShaderNodeTexCoord", 0, 160)
    uv = texcoord.outputs.get("UV") or texcoord.outputs[0]

    mapping = _new_node(nt, "ShaderNodeMapping", 200, 160)
    mapping.inputs["Scale"].default_value = (float(noise_scale) * 1.2, float(noise_scale) * 0.25, 1.0)
    nt.links.new(uv, mapping.inputs["Vector"])
    noise_vec = mapping.outputs["Vector"]

    road_layer = _build_category_mix(
        nt,
        uv,
        noise_vec,
        road_sets,
        seed=int(seed) ^ 0xF00D,
        variants=variants,
        dominant_min=0.80,
        dominant_max=1.0,
        coverage_min=0.82,
        coverage_max=0.94,
        softness=0.04,
        x=0,
        y=200,
    )

    nt.links.new(road_layer[0], bsdf.inputs["Base Color"])
    nt.links.new(road_layer[1], bsdf.inputs["Roughness"])

    norm = _new_node(nt, "ShaderNodeVectorMath", 820, -220)
    norm.operation = "NORMALIZE"
    nt.links.new(road_layer[2], norm.inputs[0])
    nt.links.new(norm.outputs["Vector"], bsdf.inputs["Normal"])

    disp = _new_node(nt, "ShaderNodeDisplacement", 980, -220)
    disp.inputs["Midlevel"].default_value = 0.5
    disp.inputs["Scale"].default_value = 0.02
    nt.links.new(road_layer[3], disp.inputs["Height"])
    if "Displacement" in out.inputs:
        nt.links.new(disp.outputs["Displacement"], out.inputs["Displacement"])

    _set_active_material(road_obj, mat)
    return None


def apply_textures_from_scene_settings(
    scene_settings,
    *,
    terrain_obj: bpy.types.Object | None,
    road_obj: bpy.types.Object | None,
) -> list[str]:
    msgs: list[str] = []
    root = str(getattr(scene_settings, "texture_root_dir", "") or "")
    seed = int(getattr(scene_settings, "seed", 0))
    variants = int(getattr(scene_settings, "texture_variants", 3))
    noise_scale = float(getattr(scene_settings, "texture_noise_scale", 6.0))
    transition_width = float(getattr(scene_settings, "texture_transition_width", 0.06))

    if bool(getattr(scene_settings, "apply_terrain_textures", True)) and terrain_obj is not None:
        m = apply_terrain_material(
            terrain_obj,
            texture_root=root,
            seed=seed,
            variants_per_category=variants,
            ground_to_rock_ratio=float(getattr(scene_settings, "terrain_ground_ratio", 0.4)),
            rock_to_snow_ratio=float(getattr(scene_settings, "terrain_rock_ratio", 0.75)),
            height_blend=float(getattr(scene_settings, "terrain_height_blend", 0.08)),
            cliff_slope_start=float(getattr(scene_settings, "terrain_cliff_slope_start", 0.35)),
            cliff_slope_end=float(getattr(scene_settings, "terrain_cliff_slope_end", 0.6)),
            noise_scale=noise_scale,
            transition_width=transition_width,
        )
        if m:
            msgs.append(m)

    if bool(getattr(scene_settings, "apply_road_textures", True)) and road_obj is not None:
        m = apply_road_material(
            road_obj,
            texture_root=root,
            seed=seed,
            variants=variants,
            noise_scale=noise_scale,
        )
        if m:
            msgs.append(m)

    return msgs

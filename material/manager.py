from __future__ import annotations

import os
import random
from dataclasses import dataclass

import bpy


_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".exr", ".hdr")
_DEFAULT_TERRAIN_UV_TILE_M = 5.0


def _addon_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def default_texture_root() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "textures")


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


def _scan_texture_folder(folder: str) -> TextureSet | None:
    if not folder:
        return None
    try:
        folder = bpy.path.abspath(folder)
    except Exception:
        pass
    if not os.path.isdir(folder):
        return None

    color = _find_first_file(folder, ["_color", "albedo", "diffuse", "basecolor"])
    if color is None:
        color = _find_any_image(folder)
    if color is None:
        return None
    ao = _find_first_file(folder, ["ambientocclusion", "_ambientocclusion", "_ao", "ao"])
    roughness = _find_first_file(folder, ["_roughness", "roughness"])
    normal = _find_first_file(folder, ["_normalgl", "normalgl"])
    if normal is None:
        candidate = _find_first_file(folder, ["_normal", "normal"])
        if candidate is not None and "normaldx" not in os.path.basename(candidate).lower():
            normal = candidate
    displacement = _find_first_file(folder, ["_displacement", "displacement", "height"])
    return TextureSet(
        name=os.path.basename(os.path.normpath(folder)),
        color=color,
        ao=ao,
        roughness=roughness,
        normal=normal,
        displacement=displacement,
    )


def _pick_category_texture_set(
    category_dir: str,
    *,
    preferred_folder: str | None,
    seed: int,
) -> TextureSet | None:
    if preferred_folder:
        t = _scan_texture_folder(preferred_folder)
        if t is not None:
            return t

    sets = _collect_texture_sets(category_dir)
    if not sets:
        return None
    rng = random.Random(int(seed))
    return sets[rng.randrange(0, len(sets))]


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
        img.reload()
    except Exception:
        pass
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


def _ensure_planar_uv_xy(
    obj: bpy.types.Object,
    *,
    tile_m: float,
    uv_name: str = "UVMap",
) -> bool:
    mesh = obj.data
    if not isinstance(mesh, bpy.types.Mesh):
        return False

    if not mesh.vertices or not mesh.polygons:
        return False

    try:
        tile = max(0.001, float(tile_m))
    except Exception:
        tile = _DEFAULT_TERRAIN_UV_TILE_M

    min_x = float("inf")
    min_y = float("inf")
    for v in mesh.vertices:
        x = float(v.co.x)
        y = float(v.co.y)
        if x < min_x:
            min_x = x
        if y < min_y:
            min_y = y

    if min_x == float("inf") or min_y == float("inf"):
        return False

    created = False
    if not mesh.uv_layers:
        try:
            mesh.uv_layers.new(name=uv_name)
            created = True
        except Exception:
            return False

    uv_layer = mesh.uv_layers.active or mesh.uv_layers[0]
    try:
        mesh.uv_layers.active_index = mesh.uv_layers.find(uv_layer.name)
    except Exception:
        pass

    try:
        uv_data = uv_layer.data
        loops = mesh.loops
        verts = mesh.vertices
        for poly in mesh.polygons:
            for li in poly.loop_indices:
                vi = loops[li].vertex_index
                co = verts[vi].co
                uv_data[li].uv = ((float(co.x) - min_x) / tile, (float(co.y) - min_y) / tile)
    except Exception:
        return False

    try:
        mesh.update()
    except Exception:
        pass

    return created


def _new_node(nt: bpy.types.NodeTree, node_type: str, x: float, y: float) -> bpy.types.Node:
    try:
        n = nt.nodes.new(node_type)
    except RuntimeError:
        fallback = {"ShaderNodeSeparateColor": "ShaderNodeSeparateRGB"}.get(node_type)
        if fallback is None:
            raise
        n = nt.nodes.new(fallback)
    n.location = (x, y)
    return n


def reset_textures_data(*, texture_root: str | None) -> str:
    root = bpy.path.abspath(texture_root) if texture_root else default_texture_root()
    root = os.path.normpath(os.path.normcase(root))

    removed_mats = 0
    for name in ("RWB_Terrain_Mat", "RWB_Road_Mat"):
        mat = bpy.data.materials.get(name)
        if mat is None:
            continue
        try:
            bpy.data.materials.remove(mat, do_unlink=True)
            removed_mats += 1
        except Exception:
            pass

    removed_imgs = 0
    for img in list(bpy.data.images):
        fp = str(getattr(img, "filepath", "") or "")
        if not fp:
            continue
        try:
            fp_abs = os.path.normpath(os.path.normcase(bpy.path.abspath(fp)))
        except Exception:
            continue
        if not fp_abs.startswith(root):
            continue
        if getattr(img, "users", 0) != 0:
            continue
        try:
            bpy.data.images.remove(img)
            removed_imgs += 1
        except Exception:
            pass

    return f"Removed {removed_mats} materials, {removed_imgs} images"


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


def _mix_layers_height_aware(
    nt: bpy.types.NodeTree,
    a,
    b,
    factor,
    contrast: float = 0.2,
    *,
    x: float,
    y: float
) -> tuple:
    # a/b are tuples: (color, rough, normal, disp)
    # factor is 0..1 (0->a, 1->b)
    # contrast controls hardness of blend

    # Logic:
    # h1_mod = h1 + (1 - factor)
    # h2_mod = h2 + factor
    # diff = h2_mod - h1_mod
    # mask = smoothstep(-contrast, contrast, diff)
    
    # But wait, standard height blend logic is usually:
    # mask = (h1 + fac) > (h2 + (1-fac))  (if fac=0 is h1)
    # Let's align with mix factor convention: 0->A, 1->B
    # A_weight = (1 - factor)
    # B_weight = factor
    # A_val = hA + A_weight
    # B_val = hB + B_weight
    # if B_val > A_val -> show B (factor=1)
    
    # 1. Calculate weights
    sub = _new_node(nt, "ShaderNodeMath", x, y + 200)
    sub.operation = "SUBTRACT"
    sub.inputs[0].default_value = 1.0
    nt.links.new(factor, sub.inputs[1])
    w_a = sub.outputs["Value"]
    w_b = factor
    
    # 2. Add height
    add_a = _new_node(nt, "ShaderNodeMath", x + 200, y + 200)
    add_a.operation = "ADD"
    nt.links.new(a[3], add_a.inputs[0])
    nt.links.new(w_a, add_a.inputs[1])
    
    add_b = _new_node(nt, "ShaderNodeMath", x + 200, y)
    add_b.operation = "ADD"
    nt.links.new(b[3], add_b.inputs[0])
    nt.links.new(w_b, add_b.inputs[1])
    
    # 3. Diff = B_val - A_val
    diff = _new_node(nt, "ShaderNodeMath", x + 400, y + 100)
    diff.operation = "SUBTRACT"
    nt.links.new(add_b.outputs["Value"], diff.inputs[0])
    nt.links.new(add_a.outputs["Value"], diff.inputs[1])
    
    # 4. Smoothstep
    ramp = _new_node(nt, "ShaderNodeMapRange", x + 600, y + 100)
    c = max(0.001, float(contrast))
    ramp.inputs["From Min"].default_value = -c
    ramp.inputs["From Max"].default_value = c
    ramp.inputs["To Min"].default_value = 0.0
    ramp.inputs["To Max"].default_value = 1.0
    ramp.clamp = True
    if hasattr(ramp, "interpolation_type"):
        ramp.interpolation_type = "SMOOTHSTEP"
    nt.links.new(diff.outputs["Value"], ramp.inputs["Value"])
    
    new_factor = ramp.outputs["Result"]

    mix_c = _new_node(nt, "ShaderNodeMixRGB", x + 800, y)
    mix_c.blend_type = "MIX"
    nt.links.new(new_factor, mix_c.inputs["Fac"])
    nt.links.new(a[0], mix_c.inputs["Color1"])
    nt.links.new(b[0], mix_c.inputs["Color2"])

    mix_r = _new_node(nt, "ShaderNodeMix", x + 800, y - 220)
    mix_r.data_type = "FLOAT"
    nt.links.new(new_factor, mix_r.inputs["Factor"])
    nt.links.new(a[1], mix_r.inputs["A"])
    nt.links.new(b[1], mix_r.inputs["B"])

    mix_n = _new_node(nt, "ShaderNodeMix", x + 800, y - 440)
    mix_n.data_type = "VECTOR"
    nt.links.new(new_factor, mix_n.inputs["Factor"])
    nt.links.new(a[2], mix_n.inputs["A"])
    nt.links.new(b[2], mix_n.inputs["B"])
    norm = _new_node(nt, "ShaderNodeVectorMath", x + 1000, y - 440)
    norm.operation = "NORMALIZE"
    nt.links.new(mix_n.outputs["Result"], norm.inputs[0])

    mix_d = _new_node(nt, "ShaderNodeMix", x + 800, y - 660)
    mix_d.data_type = "FLOAT"
    nt.links.new(new_factor, mix_d.inputs["Factor"])
    nt.links.new(a[3], mix_d.inputs["A"])
    nt.links.new(b[3], mix_d.inputs["B"])

    return (mix_c.outputs["Color"], mix_r.outputs["Result"], norm.outputs["Vector"], mix_d.outputs["Result"])


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
        # If only one texture set, duplicate it to allow variation mixing
        picked = [picked[0], picked[0], picked[0]]

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
    
    # Generate layers with Random UV Transforms
    layers = []
    current_y = y
    
    # Random generator for UV transforms
    uv_rng = random.Random(int(seed) ^ 0x5555)
    
    for i, p in enumerate(picked):
        # Create a randomized mapping for this layer
        # Rotation: 0-360 random
        # Scale: 0.9-1.1 variation
        # Location: random offset
        
        mapping = _new_node(nt, "ShaderNodeMapping", x - 200, current_y)
        # Link original UV
        nt.links.new(uv_socket, mapping.inputs["Vector"])
        
        # Apply random transforms
        # Random Rotation Z
        mapping.inputs["Rotation"].default_value[2] = uv_rng.uniform(0.0, 6.28318)
        # Random Scale (uniform xy)
        s_var = uv_rng.uniform(0.9, 1.1)
        mapping.inputs["Scale"].default_value = (s_var, s_var, 1.0)
        # Random Location
        mapping.inputs["Location"].default_value = (uv_rng.uniform(-100.0, 100.0), uv_rng.uniform(-100.0, 100.0), 0.0)
        
        transformed_uv = mapping.outputs["Vector"]
        
        layers.append(_texture_set_nodes(nt, transformed_uv, p, x=x, y=current_y))
        current_y -= 450 # Stagger nodes vertically (increased spacing)
        
    # Mix layers based on Voronoi color channels
    # We have up to 4 layers: A, B, C, D
    # We have 3 smooth random values: R, G, B
    
    # Use Height Aware Mixing
    
    # Mix 0 and 1 using Red
    if len(layers) >= 2:
        mix01 = _mix_layers_height_aware(nt, layers[0], layers[1], sep.outputs[0], contrast=0.2, x=x + 1200, y=y)
    else:
        mix01 = layers[0]
        
    if len(layers) >= 3:
        # Mix (0-1) and 2 using Green
        mix012 = _mix_layers_height_aware(nt, mix01, layers[2], sep.outputs[1], contrast=0.2, x=x + 1400, y=y)
    else:
        mix012 = mix01
        
    if len(layers) >= 4:
        # Mix (0-1-2) and 3 using Blue
        mix0123 = _mix_layers_height_aware(nt, mix012, layers[3], sep.outputs[2], contrast=0.2, x=x + 1600, y=y)
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
    ground_texture_dir: str | None,
    rock_texture_dir: str | None,
    snow_texture_dir: str | None,
    ground_to_rock_ratio: float,
    rock_to_snow_ratio: float,
    height_blend: float,
    texture_scale: float,
) -> str | None:
    if terrain_obj.type != "MESH":
        return "Terrain object is not a mesh"

    mesh = terrain_obj.data
    if isinstance(mesh, bpy.types.Mesh) and not mesh.uv_layers:
        _ensure_planar_uv_xy(terrain_obj, tile_m=_DEFAULT_TERRAIN_UV_TILE_M)

    root = bpy.path.abspath(texture_root) if texture_root else default_texture_root()
    ground_set = _pick_category_texture_set(
        os.path.join(root, "Ground"),
        preferred_folder=ground_texture_dir,
        seed=int(seed) ^ 0x13579,
    )
    rock_set = _pick_category_texture_set(
        os.path.join(root, "Rock"),
        preferred_folder=rock_texture_dir,
        seed=int(seed) ^ 0x2468A,
    )
    snow_set = _pick_category_texture_set(
        os.path.join(root, "Snow"),
        preferred_folder=snow_texture_dir,
        seed=int(seed) ^ 0xABCDE,
    )

    if ground_set is None:
        return "No ground texture found"
    if rock_set is None:
        return "No rock texture found"
    if snow_set is None:
        return "No snow texture found"

    z = _mesh_z_bounds_local(terrain_obj)
    if z is None:
        return "Terrain has no vertices"
    min_z, max_z = z

    mat = _ensure_material("RWB_Terrain_Mat")
    nt = mat.node_tree
    if nt is None:
        return "Failed to create terrain material node tree"
    nt.nodes.clear()

    out = _new_node(nt, "ShaderNodeOutputMaterial", 1400, 0)
    bsdf = _new_node(nt, "ShaderNodeBsdfPrincipled", 1180, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    texcoord = _new_node(nt, "ShaderNodeTexCoord", 0, 160)
    uv = texcoord.outputs.get("UV") or texcoord.outputs[0]

    mapping = _new_node(nt, "ShaderNodeMapping", 200, 160)
    s = max(0.001, float(texture_scale))
    mapping.inputs["Scale"].default_value = (s, s, 1.0)
    nt.links.new(uv, mapping.inputs["Vector"])
    uv_scaled = mapping.outputs["Vector"]

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
    ground_layer = _texture_set_nodes(nt, uv_scaled, ground_set, x=0, y=520)
    rock_layer = _texture_set_nodes(nt, uv_scaled, rock_set, x=0, y=100)
    snow_layer = _texture_set_nodes(nt, uv_scaled, snow_set, x=0, y=-320)

    # Use Height Aware Mixing for Terrain Layers
    # Ground -> Rock
    mix_gr = _mix_layers_height_aware(nt, ground_layer, rock_layer, t1, contrast=0.2, x=760, y=320)
    
    # (Ground/Rock) -> Snow
    mix_rs = _mix_layers_height_aware(nt, mix_gr, snow_layer, t2, contrast=0.2, x=980, y=320)
    
    base_color = mix_rs[0]
    base_rough = mix_rs[1]
    base_norm = mix_rs[2]
    base_disp = mix_rs[3]
    
    nt.links.new(base_color, bsdf.inputs["Base Color"])
    nt.links.new(base_rough, bsdf.inputs["Roughness"])
    nt.links.new(base_norm, bsdf.inputs["Normal"])

    disp = _new_node(nt, "ShaderNodeDisplacement", 1400, -340)
    disp.inputs["Midlevel"].default_value = 0.5
    disp.inputs["Scale"].default_value = 0.06
    nt.links.new(base_disp, disp.inputs["Height"])
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

    try:
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
    except Exception as e:
        nt.nodes.clear()
        out = _new_node(nt, "ShaderNodeOutputMaterial", 300, 0)
        bsdf = _new_node(nt, "ShaderNodeBsdfPrincipled", 80, 0)
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
        return f"Road material build failed: {e}"


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

    if bool(getattr(scene_settings, "apply_terrain_textures", True)) and terrain_obj is not None:
        m = apply_terrain_material(
            terrain_obj,
            texture_root=root,
            seed=seed,
            ground_texture_dir=str(getattr(scene_settings, "terrain_ground_texture_dir", "") or ""),
            rock_texture_dir=str(getattr(scene_settings, "terrain_rock_texture_dir", "") or ""),
            snow_texture_dir=str(getattr(scene_settings, "terrain_snow_texture_dir", "") or ""),
            ground_to_rock_ratio=float(getattr(scene_settings, "terrain_ground_ratio", 0.4)),
            rock_to_snow_ratio=float(getattr(scene_settings, "terrain_rock_ratio", 0.75)),
            height_blend=float(getattr(scene_settings, "terrain_height_blend", 0.08)),
            texture_scale=float(getattr(scene_settings, "terrain_texture_scale", noise_scale)),
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

# `Route2World/texturing.py` 逻辑说明

本文件负责把 `Route2World/Texture` 目录中的贴图“按规则自动组装为 Blender 材质”，并应用到生成出来的地形 `RWB_Terrain` 与道路 `RWB_Road` 上。核心目标是：

- 贴图按命名规范自动引用（`Color/Roughness/NormalGL/AO/Displacement`）
- 同类材质（同一个类别目录下的多个材质包）能混合，并且每个区域都有一个“主导材质”
- 不同高度（Ground/Rock/Snow）按比例分层，并且陡峭区域用 Cliff 覆盖
- Road 采用同类混合逻辑，但混合更“贴合道路长条特性”

下面按“数据结构 → 贴图发现 → 节点构建 → 混合算法 → 地形/道路材质 → 外部调用”分解说明。

---

## 1. 输入与目录约定

### 1.1 贴图根目录

- 默认根目录：`default_texture_root()`（`texturing.py:17`）返回 `Route2World/Texture`
- 也可以在 UI 面板的 `Texture Root`（`Scene.route2world.texture_root_dir`）覆盖根目录（实际解析会走 `bpy.path.abspath`）

### 1.2 类别目录结构

`Texture` 下预期的类别目录：

- `Ground/`
- `Rock/`
- `Snow/`
- `Cliff/`
- `Road/`

每个类别目录里通常是“材质包文件夹”（例如 `Rock039_2K-JPG/`），文件夹内部按命名规范放置贴图。

---

## 2. 关键数据结构：`TextureSet`

`TextureSet`（`texturing.py:21-28`）描述“一个材质包”能提供的贴图路径集合：

- `color`：Base Color（sRGB）
- `ao`：Ambient Occlusion（Non-Color）
- `roughness`：Roughness（Non-Color）
- `normal`：Normal（优先 `NormalGL`，Non-Color）
- `displacement`：Displacement/Height（Non-Color）

注意：所有字段都允许为 `None`，在缺失时会用默认值节点兜底。

---

## 3. 贴图文件发现与命名规范匹配

### 3.1 文件扫描

`_collect_texture_sets(category_dir)`（`texturing.py:59`）负责扫描某个类别目录，返回 `TextureSet` 列表：

- 对子目录：认为是一个材质包，进入目录内找贴图文件（`texturing.py:68-89`）
- 对直接在类别目录下的图片文件：作为“只有 Color 的简化材质包”（`texturing.py:90-100`）

### 3.2 匹配规则（按文件名关键字）

使用 `_find_first_file(folder, patterns)`（`texturing.py:31`）在目录内匹配包含关键字的图片文件：

- `Color`：匹配 `_color/albedo/diffuse/basecolor`（找不到则退化为“目录内任意第一张图片”）
- `AO`：匹配 `ambientocclusion/_ambientocclusion/_ao/ao`
- `Roughness`：匹配 `_roughness/roughness`
- `Normal`：优先匹配 `*_NormalGL*`（`_normalgl/normalgl`），找不到时再找 `*_Normal*`，但会排除 `NormalDX`（`texturing.py:74-78`）
- `Displacement`：匹配 `_displacement/displacement/height`

### 3.3 图像载入与色彩空间

`_load_image(path, is_data=...)`（`texturing.py:105`）负责载入图片并设置色彩空间：

- `is_data=False`：尝试设为 `sRGB`（Color）
- `is_data=True`：尝试设为 `Non-Color`（AO/Roughness/Normal/Displacement）

---

## 4. 节点构建的“基础积木”

### 4.1 创建材质并清空节点

`_ensure_material(name)`（`texturing.py:121`）确保材质存在并启用节点；地形/道路入口会对 `node_tree.nodes` 与 `node_tree.links` 清空重建（`apply_terrain_material`: `texturing.py:504-509`；`apply_road_material`: `texturing.py:784-789`）。

### 4.2 绑定对象材质

`_set_active_material(obj, mat)`（`texturing.py:129`）把材质写入 `obj.data.materials[0]`。

### 4.3 地形高度范围

`_mesh_z_bounds_local(obj)`（`texturing.py:141`）遍历网格顶点，得到局部坐标的 `min_z/max_z`，用于后续“高度归一化”。

---

## 5. 单个材质包的节点：`_texture_set_nodes`

`_texture_set_nodes(nt, uv_socket, t, ...)`（`texturing.py:195`）把一个 `TextureSet` 转成 4 个输出插口：

1. `color_out`：Color 输出
2. `rough_out`：Roughness（float）
3. `normal_out`：Normal（vector）
4. `disp_out`：Displacement/Height（float）

具体规则：

- Color：
  - 有 `Color` 贴图：创建 `TexImage` 并连接 UV
  - 没有：用 `RGB(0.5,0.5,0.5)`
- AO：
  - 有 AO：`AO -> RGBToBW -> MixRGB(MULTIPLY)` 乘到 Base Color 上（`texturing.py:219-230`）
- Roughness：
  - 有 Roughness：`TexImage -> RGBToBW` 转成灰度 float（`texturing.py:237-242`）
  - 没有：用 `Value(0.65)`
- Normal：
  - 有 Normal：`TexImage -> NormalMap`
  - 没有：用 `CombineXYZ(Z=1)` 作为“平直法线”
- Displacement：
  - 有 Displacement：`TexImage -> RGBToBW`
  - 没有：用 `Value(0.0)`

---

## 6. 叠加两个“材质包输出”：`_mix_layers`

`_mix_layers(nt, a, b, factor, ...)`（`texturing.py:271`）把两个材质包输出 `a/b` 按 `factor` 混合，返回同样结构的 4 元组：

- Color：`MixRGB(MIX)`
- Roughness：`Mix(FLOAT)`
- Normal：`Mix(VECTOR)` 后再 `VectorMath(NORMALIZE)` 归一化，避免法线幅值被混合破坏
- Displacement：`Mix(FLOAT)`

---

## 7. “自动区域检测 + 主导材质随机权重 + 平滑过渡”

核心算法在 `_build_category_mix(...)`（`texturing.py:345`）。它解决“同类材质如何混合”并满足以下约束：

- 每个区域至少两种材质参与
- 每个区域都有一个主导材质
- 主导/次要占比不是固定值，而是随机落在范围内（例如 70–90% vs 10–30%）
- 区域边界过渡自动平滑

### 7.1 选材与上限

- `variants` 最少按 2 处理，且最多只取前 4 个材质包参与混合（性能限制，避免节点过多）（`texturing.py:375-376`）
- `seed` 用于随机打乱顺序，保证“同一个 seed 的结果可复现”

### 7.2 Voronoi 分区：自动检测“材质区域”

对前两个材质包 `A/B`：

- 用 `Voronoi Texture`（`ShaderNodeTexVoronoi`）驱动一个“分区场”（`texturing.py:393`）
- 把 Voronoi 的 `Color` 拆成 R/G（`SeparateRGB`）
  - `R` 作为区域选择字段：决定当前区域偏向 A 还是 B
  - `G` 作为随机数来源：在每个区域里生成不同权重

### 7.3 区域边界平滑（过渡处理）

使用 `_smoothstep`（`texturing.py:464`）围绕 `0.5` 做一个平滑阈值：

- `edge = 0.06`（`texturing.py:405-416`）
- `choice = smoothstep(R, 0.5-edge, 0.5+edge)`（`texturing.py:418`）

这让 Voronoi 分区边界从“硬切换”变成“软过渡”。

### 7.4 主导/次要权重随机化

对每个区域，`dominant_min/dominant_max` 定义“主导材质占比范围”：

- 主导范围：`[dominant_min, dominant_max]`
- 次要范围：`[1-dominant_max, 1-dominant_min]`（`texturing.py:382-383`）

然后：

- 用 `G` 分别映射到主导范围与次要范围（`MapRange`）：
  - `major`：映射到主导范围（`texturing.py:426-430`）
  - `minor`：映射到次要范围（`texturing.py:420-424`）
- 再用 `choice` 在 `major/minor` 间切换得到最终 `factor`（`texturing.py:432-436`）

因此在“主导区域”，`factor` 会落在 70–90%（示例）这样的范围；在“次要区域”，落在 10–30%。

### 7.5 额外材质（第 3/4 个）稀疏点缀

当参与混合的材质包超过 2 个时：

- 使用 `_sparse_mask_from_noise`（`texturing.py:303`）生成稀疏蒙版（有覆盖率 `coverage` 与边缘软化 `softness`）
- 对每个额外材质设置一个“最大混入比例 cap”，并随层数指数衰减（`0.45 ** (i - 1)`，`texturing.py:442-443`）
- 用 `mask * cap` 作为混合因子，将额外材质“点状/片状”叠加到当前结果上（`texturing.py:444-459`）

---

## 8. 地形材质：高度分层 + Cliff 覆盖

入口：`apply_terrain_material(...)`（`texturing.py:477`）

### 8.1 高度归一化

- 取地形局部 `min_z/max_z`（`texturing.py:499-503`）
- 用 `MapRange` 把顶点 `Position.Z` 映射为 `h ∈ [0,1]`（`texturing.py:523-543`）

### 8.2 Ground/Rock/Snow 高度层过渡

通过两条过渡曲线：

- `t1`：Ground → Rock 分界（`texturing.py:570`）
- `t2`：Rock → Snow 分界（`texturing.py:571`）

其中 `Height Blend` 控制过渡带宽（`texturing.py:545-550`），并用 `_smoothstep` 确保过渡平滑。

随后分别对 `Color/Roughness/Normal/Displacement` 做两段混合（`texturing.py:655-708`）得到 `base_*`。

注：`ground_w/rock_w/snow_w`（`texturing.py:576-592`）是中间计算出来的权重节点，目前未被后续直接使用（最终实际使用的是 `t1/t2` 两条曲线驱动混合）。

### 8.3 Cliff 覆盖（按陡峭度）

使用 `Geometry.Normal` 的 `Z` 分量：

- `abs_z = abs(normal.z)`
- `steep = 1 - abs_z`（越接近 1 越陡）`texturing.py:710-718`

再用 `_smoothstep(steep, cliff_start, cliff_end)` 得到 `cliff_f`（`texturing.py:720-724`）。

最后用 `cliff_f` 把 Cliff 叠到 base 的 `Color/Roughness/Normal/Displacement` 上（`texturing.py:726-756`）。

### 8.4 位移输出

- 通过 `ShaderNodeDisplacement` 把最终 displacement 接到 `Material Output` 的 `Displacement`（若该输入存在）（`texturing.py:757-762`）
- 地形默认 `Scale=0.06`（可视需求调小，避免过强位移）

---

## 9. 道路材质：同类混合 + 长条特性参数

入口：`apply_road_material(...)`（`texturing.py:768`）

关键点：

- 仍然走 `_build_category_mix` 生成 `road_layer`（`texturing.py:803-817`）
- 默认主导更强：`dominant_min=0.80, dominant_max=0.92`（更像“以某一种路面为主”）
- UV Mapping 的 scale 做了各向异性：`(noise_scale*1.2, noise_scale*0.25, 1.0)`（`texturing.py:798-801`），使纵向变化更平缓、横向变化更紧凑
- 位移输出存在时接入 `Displacement`，道路默认 `Scale=0.02`（`texturing.py:827-832`）

---

## 10. 外部入口：从 UI 配置应用材质

`apply_textures_from_scene_settings(scene_settings, terrain_obj, road_obj)`（`texturing.py:838`）是 `ops.py` 调用的统一入口：

- 从 `scene_settings` 读取：
  - `texture_root_dir`
  - `seed`
  - `texture_variants`
  - `texture_noise_scale`
  - `apply_terrain_textures` / `apply_road_textures`
  - 地形高度与 cliff 参数：`terrain_ground_ratio/terrain_rock_ratio/terrain_height_blend/terrain_cliff_slope_start/terrain_cliff_slope_end`
- 分别调用：
  - `apply_terrain_material`（`texturing.py:850-865`）
  - `apply_road_material`（`texturing.py:866-876`）

返回值是警告信息列表（字符串），用于在操作面板提示贴图缺失等问题。

---

## 11. 常见调整建议

- 想让“区域更大更连贯”：减小 `Mix Scale`（噪声/分区输入更平缓）
- 想让“混合更明显/更碎”：增大 `Mix Scale` 或增大 `Texture Variants`（但注意上限为 4）
- 位移太强/闪烁：降低 `ShaderNodeDisplacement.Scale`（地形 `0.06`、道路 `0.02` 这两个默认值）
- Cliff 覆盖过多：提高 `Cliff Start/End`（让更陡才触发）

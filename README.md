# Route2World (Blender Add-on)

Route2World 是一个 Blender 插件：从 GPX 轨迹生成路线曲线、道路网格和程序化地形，并提供自动贴图、手绘区域遮罩、以及沿路散布资产（建筑/树/草）功能。

## 兼容性

- Blender：4.0+（在 5.0 上验证通过）
- 系统：跨平台（macOS/Windows/Linux）

## 安装

1. 确保插件目录位于 Blender 的 `scripts/addons` 下，并且目录名为 `Route2World`。
2. 打开 Blender：
   - `Edit > Preferences > Add-ons`
   - 搜索 `Route2World`
   - 勾选启用
3. 如果你是手动拷贝更新插件，建议重启 Blender 或点击 `Refresh` 后再启用。

macOS 常见路径示例：

`~/Library/Application Support/Blender/5.0/scripts/addons/Route2World`

## 快速上手（从 GPX 生成）

1. 打开 `3D Viewport`，按 `N` 打开右侧侧边栏。
2. 找到 `Route2World` 标签页。
3. 在 `GPX` 选择轨迹文件（`.gpx`）。
4. 按需设置：
   - `Objects`：是否生成 Route Curve / Road Mesh / Terrain
   - `Road`：道路宽度、抬高（避免 z-fighting）、嵌入、厚度
   - `Terrain`：边缘留白、细节、风格、随机种子与材质分层参数
5. 点击 `Generate`。

生成后默认会创建一个名为 `Route2World` 的 Collection，并在其中生成对象：

- `RWB_Route`：路线曲线（Curve）
- `RWB_Road`：道路网格（Mesh）
- `RWB_Terrain`：地形网格（Mesh）

## 自动贴图（Texture）

插件会根据贴图目录结构自动组装材质节点并赋予地形/道路。

### 贴图根目录

- 默认：插件自带 `Texture/` 目录
- 可在面板里用 `Texture Root` 指定自定义根目录

### 目录结构约定

`Texture/` 下预期包含这些类别目录（大小写按示例）：

- `Ground/`
- `Rock/`
- `Snow/`
- `Cliff/`
- `Road/`

每个类别目录下可以放多个“材质包文件夹”，文件夹里放贴图文件。插件会按文件名关键字尝试匹配：

- Color：`_Color` / `albedo` / `diffuse` / `basecolor`
- Roughness：`_Roughness`
- Normal：优先 `NormalGL`（会跳过 `NormalDX`）
- AO：`AmbientOcclusion` / `_AO`
- Displacement：`_Displacement` / `height`

### 重要参数

- `Texture Terrain` / `Texture Road`：是否给地形/道路应用材质
- `Texture Variants`：每个类别参与混合的材质数量（代码内部最多取 4）
- `Mix Scale`：噪声缩放，值越小区域越大越连贯，值越大变化越碎
- `Transition Width`：混合过渡宽度（越大过渡越柔）

## 手绘地形区域遮罩（Manual Painting）

点击 `Start Painting` 后会对 `RWB_Terrain` 创建/确保一个颜色属性，并切换到 `Vertex Paint`。

默认约定：

- 红色（R）：Ground
- 绿色（G）：Rock
- 蓝色（B）：Snow

你可以用顶点绘制在地形上手工控制不同区域的材质分布。

## 沿路散布资产（Procedural Scatter）

在主面板下方会有子面板 `Procedural`，用于沿路线两侧散布建筑、树和草。

### 资产目录（Source）

- 默认：插件自带 `Source/` 目录
- 可在面板里用 `Assets Root` 指定自定义资产根目录

默认结构约定：

- `Source/Building/`：建筑原型（`.glb`）
- `Source/Tree/`：树原型（`.glb`）
- `Source/Grass/`：草原型（`.glb`）

### Targets（目标对象）

- `Route`：路线曲线对象（不填时默认使用 `RWB_Route`）
- `Terrain`：地形对象，用于投射高度（推荐）

### Scatter（散布控制）

- `Side`：左右/双侧
- `Seed`：随机种子
- `Max Instances`：最大实例数（数量大时会影响性能）
- `Road No-Spawn (m)`：道路边缘的禁生成宽度

### 分类参数（Buildings/Trees/Grass）

每个类别都可以单独启用，并控制：

- `Spacing (m)`：目标间距
- `Probability`：生成概率
- `Min Distance (m)`：最小间距约束
- `Offset Min/Max (m)`：离道路中心线的偏移范围
- `Scale Min/Max`：缩放范围

建筑额外提供 cluster 参数，用于控制成簇分布的规模和范围。

散布结果会创建/使用：

- `Route2World`（顶层 Collection）
  - `RWB_Scatter`（散布输出 Collection）
- `RWB_AssetLibrary`（隐藏的原型库 Collection）

## 常见问题（Troubleshooting）

### 插件启用后看不到面板

- 确认在 `View3D > Sidebar`（按 `N`）查看右侧栏
- 确认启用的插件为 `Route2World`
- 确认插件目录名为 `Route2World`，并且目录里直接包含 `__init__.py`

### 点击 Generate 报 “GPX file not found”

- 确认已选择 `.gpx` 文件
- 如果使用相对路径，确保 Blender 能解析到正确的绝对路径

### 没有贴图或贴图缺失

- 确认 `Texture Root` 指向的目录下存在 `Ground/Rock/Snow/Cliff/Road`
- 检查贴图文件名是否包含常见关键字（例如 `_Color`、`_Roughness`、`NormalGL`）

### 散布时提示找不到资产目录或没有 .glb

- 确认 `Assets Root` 下存在 `Building/Tree/Grass` 子目录
- 确认目录中至少有一个 `.glb`

## 对外接口（给脚本/二次开发）

主要 UI 与操作符入口：

- `route2world.generate_from_gpx`
- `route2world.setup_paint_mask`
- `route2world.scatter_roadside_assets`

主要对象命名约定：

- `RWB_Route` / `RWB_Road` / `RWB_Terrain`

模块入口文件：

- `__init__.py`：注册入口
- `ui.py`：主面板与主参数
- `ops.py`：GPX 生成与绘制遮罩
- `texturing.py`：自动材质与贴图扫描逻辑
- `scatter_core.py` / `scatter_ops.py` / `scatter_ui.py`：散布系统

## License

代码许可：MIT（见 `Route2World/Route2World/LICENSE`）。

注意：`Source/` 与 `Texture/` 内的资源可能来自第三方或包含各自许可，请在分发或商用前自行确认其授权条款。

import bpy

TRANSLATIONS = {
    "zh_CN": {
        # Main Panel
        "Input": "输入",
        "GPX": "GPX文件",
        "GPX track file": "GPX轨迹文件",
        "Processing": "处理",
        "Mode": "模式",
        "Auto Generate": "自动生成",
        "Automatically generate terrain based on GPX": "根据GPX自动生成地形",
        "Download Terrain": "下载地形",
        "Download terrain from Mapbox": "从Mapbox下载地形",
        "Generate": "生成",
        "Build World": "生成世界",
        "Objects": "场景对象",
        "Create Route Curve": "创建路径曲线",
        "Create Road Mesh": "创建道路网格",
        "Create Terrain": "创建地形",
        "Terrain Settings": "地形设置",
        "Terrain Margin (m)": "地形边距 (米)",
        "Detail": "细节级别",
        "Style": "风格",
        "Seed": "随机种子",
        "Material Blending": "材质混合",
        "Ground Ratio": "地面比例",
        "Rock Ratio": "岩石比例",
        "Height Blend": "高度混合",
        "Cliff Start": "悬崖起始坡度",
        "Cliff End": "悬崖结束坡度",
        "Road Settings": "道路设置",
        "Road Width (m)": "道路宽度 (米)",
        "Road Offset (m)": "道路偏移 (米)",
        "Lift road above terrain to avoid z-fighting": "提升道路以避免重叠闪烁",
        "Road Embed (m)": "道路嵌入深度 (米)",
        "Road Thickness (m)": "道路厚度 (米)",
        "Road-Terrain Blend": "路面-地形过渡",
        "Enable Blend": "启用过渡",
        "Blend Start (m)": "过渡起始 (米)",
        "Blend End (m)": "过渡结束 (米)",
        "Textures": "材质纹理",
        "Texture Root": "纹理根目录",
        "Optional override. If empty, uses the add-on assets/textures folder": "可选覆盖。若为空，使用插件自带assets/textures文件夹",
        "Texture Terrain": "地形纹理",
        "Texture Road": "道路纹理",
        "Texture Variants": "纹理变体数",
        "Mix Scale": "混合缩放",
        "Transition Width": "过渡宽度",
        "Manual Tools": "手动工具",
        "Start Painting": "开始绘制",
        "Red=Ground, Green=Rock, Blue=Snow": "红=地面, 绿=岩石, 蓝=雪",
        
        # Scatter Panel
        "Targets": "目标设置",
        "Route": "路径对象",
        "Route curve object. If empty, uses object named RWB_Route": "路径曲线对象。若为空，使用名为RWB_Route的对象",
        "Terrain": "地形",
        "Terrain mesh for height projection (recommended)": "用于高度投射的地形网格（推荐）",
        "Assets Root": "资产根目录",
        "Scatter": "散布控制",
        "Side": "侧边",
        "Both": "两侧",
        "Left": "左侧",
        "Right": "右侧",
        "Max Instances": "最大实例数",
        "Road No-Spawn (m)": "道路避让距离 (米)",
        "Scatter Roadsides": "散布路边资产",
        "Scatter Assets": "散布资产",
        "Buildings": "建筑",
        "Building Spacing (m)": "建筑间距 (米)",
        "Building Probability": "建筑生成概率",
        "Building Min Distance (m)": "建筑最小距离 (米)",
        "Building Offset Min (m)": "建筑最小偏移 (米)",
        "Building Offset Max (m)": "建筑最大偏移 (米)",
        "Building Scale Min": "建筑最小缩放",
        "Building Scale Max": "建筑最大缩放",
        "Building Cluster Min": "建筑簇最小数量",
        "Building Cluster Max": "建筑簇最大数量",
        "Building Cluster Along (m)": "建筑簇沿路分布 (米)",
        "Building Cluster Out (m)": "建筑簇向外分布 (米)",
        "Trees": "树木",
        "Tree Spacing (m)": "树木间距 (米)",
        "Tree Probability": "树木生成概率",
        "Tree Min Distance (m)": "树木最小距离 (米)",
        "Tree Offset Min (m)": "树木最小偏移 (米)",
        "Tree Offset Max (m)": "树木最大偏移 (米)",
        "Tree Scale Min": "树木最小缩放",
        "Tree Scale Max": "树木最大缩放",
        "Grass": "草丛",
        "Grass Spacing (m)": "草丛间距 (米)",
        "Grass Probability": "草丛生成概率",
        "Grass Min Distance (m)": "草丛最小距离 (米)",
        "Grass Offset Min (m)": "草丛最小偏移 (米)",
        "Grass Offset Max (m)": "草丛最大偏移 (米)",
        "Grass Scale Min": "草丛最小缩放",
        "Grass Scale Max": "草丛最大缩放",
        
        # New Labels for Organization
        "Core Generation": "核心生成",
        "Detailed Settings": "详细设置",
        "Asset Types": "资产类型",
        "Mapbox Configuration": "Mapbox配置",
        "Mapbox Access Token": "Mapbox访问令牌",
        "Enter your Mapbox Access Token": "输入您的Mapbox访问令牌",
        "Default Processing Mode": "默认处理模式",
        "Download Quality": "下载质量",
        "High": "高",
        "Medium": "中",
        "Low": "低",
        "High resolution": "高分辨率",
        "Medium resolution": "中分辨率",
        "Low resolution": "低分辨率",
        
        # Common
        "Offset": "偏移",
        "Scale": "缩放",
        "Cluster": "簇",
        "Min": "最小",
        "Max": "最大",
        "Scatter Control": "散布控制",
        
    }
}

def t(text):
    # Check if we are in Chinese environment
    is_cn = False
    try:
        if bpy.app.translations.locale in {'zh_CN', 'zh_HANS'}:
            is_cn = True
        elif bpy.context.preferences.view.language in {'zh_CN', 'zh_HANS'}:
            is_cn = True
    except:
        pass
            
    if is_cn:
        return TRANSLATIONS.get("zh_CN", {}).get(text, text)
    return text

# 鄯善县文物数字化管理平台 - 版本信息

__version__ = "1.0"
__version_name__ = "初始版本"
__release_date__ = "2026-03-05"
__author__ = "文物数字化管理团队"

VERSION = {
    'version': __version__,
    'version_name': __version_name__,
    'release_date': __release_date__,
    'author': __author__,
    'description': '鄯善县文物数字化管理平台'
}

# 版本历史记录
VERSION_HISTORY = [
    {
        'version': '1.0',
        'release_date': '2026-03-05',
        'features': [
            '✓ 文物档案详情页（只读模式）',
            '✓ 文物一张图地图可视化',
            '✓ 项目管理功能',
            '✓ 坎儿井专项管理',
            '✓ 巡查记录管理',
            '✓ 手机端适配',
            '✓ 权限控制系统',
            '✓ 数据导入导出',
        ],
        'improvements': [
            '✓ 天地图API集成（与文物一张图统一）',
            '✓ 地图底图切换（卫星/电子/地形）',
            '✓ 两线范围（保护范围和建控地带）叠加显示',
            '✓ 自动设备检测和重定向',
            '✓ 安全的HTTPS部署',
        ]
    }
]

def get_version_string():
    """获取版本号字符串"""
    return f"v{VERSION['version']}"

def get_full_version_info():
    """获取完整版本信息"""
    return f"{VERSION['description']} {get_version_string()}"

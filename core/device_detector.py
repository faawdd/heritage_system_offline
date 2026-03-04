# core/device_detector.py
"""设备类型检测工具"""

def get_device_type(request):
    """
    根据User-Agent检测设备类型
    返回: 'mobile', 'tablet', 'desktop'
    """
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    
    # 移动设备关键词
    mobile_keywords = [
        'android', 'iphone', 'ipod', 'blackberry', 
        'windows phone', 'opera mini', 'mobile',
        'phone', 'webos', 'small'
    ]
    
    # 平板关键词
    tablet_keywords = [
        'ipad', 'android', 'tablet', 'kindle', 
        'playbook', 'nexus', 'xoom'
    ]
    
    # 检测是否是移动设备
    is_mobile = any(keyword in user_agent for keyword in mobile_keywords)
    
    # 检测是否是平板
    is_tablet = any(keyword in user_agent for keyword in tablet_keywords)
    
    # 排除平板和大屏幕设备
    if is_tablet and 'ipad' not in user_agent and 'kindle' not in user_agent:
        return 'tablet'
    
    if is_mobile:
        return 'mobile'
    
    return 'desktop'


def is_mobile_device(request):
    """快速检查是否为手机设备"""
    return get_device_type(request) == 'mobile'

#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'heritage_system.settings')
django.setup()

from django.test import RequestFactory
from core.views import heritage_detail_view
from core.models import HeritageSite

# 获取第一个文物
site = HeritageSite.objects.first()
if site:
    print(f"测试视图函数: heritage_detail_view(pk={site.id})")
    
    # 创建虚拟请求
    factory = RequestFactory()
    request = factory.get(f'/admin/heritage/{site.id}/detail/')
    request.user = None  # 这会使request.user为AnonymousUser
    
    # 设置user.is_staff为True（模拟已认证的工作人员）
    from django.contrib.auth.models import User
    user = User.objects.filter(is_staff=True).first()
    if user:
        request.user = user
        print(f"使用用户: {user.username}")
    
    try:
        response = heritage_detail_view(request, site.id)
        if hasattr(response, 'status_code'):
            print(f"✅ 视图返回状态码: {response.status_code}")
        else:
            print(f"✅ 视图返回: {type(response).__name__}")
    except Exception as e:
        print(f"❌ 视图执行错误: {e}")
        import traceback
        traceback.print_exc()
else:
    print("数据库中无文物数据")

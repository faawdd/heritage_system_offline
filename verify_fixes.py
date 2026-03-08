#!/usr/bin/env python
"""
快速测试脚本 - 验证修复是否有效

运行方法:
python verify_fixes.py
"""

import os
import sys
import django

# 配置 Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'heritage_system.settings')
sys.path.insert(0, os.path.dirname(__file__))

django.setup()

from django.contrib.auth.models import User
from core.models import HeritageSite, InspectionRecord
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from core.api_views import InspectionViewSet
from django.http import HttpRequest
import json

print("\n" + "="*70)
print("修复验证脚本 - App 巡查同步上传问题")
print("="*70 + "\n")

# 1. 检查后端 my_records 路由
print("✅ 检查 1: my_records 路由是否存在")
print("-" * 70)

try:
    from rest_framework.routers import DefaultRouter
    from core import api_views
    
    router = DefaultRouter()
    router.register(r'inspections', api_views.InspectionViewSet)
    
    # 获取所有路由
    routes = router.get_urls()
    my_records_route = None
    
    for route in routes:
        if 'my-records' in str(route.pattern):
            my_records_route = route
            break
    
    if my_records_route:
        print(f"✅ 找到 my-records 路由")
        print(f"   路由模式: {my_records_route.pattern}")
        print(f"   视图: {my_records_route.callback}")
    else:
        print("⚠️  未找到 my-records 路由，需要检查 API 配置")
        print("   已生成的路由:")
        for route in routes:
            if 'inspection' in str(route.pattern).lower():
                print(f"   - {route.pattern}")
    
except Exception as e:
    print(f"❌ 检查失败: {e}")
    import traceback
    traceback.print_exc()

# 2. 检查 InspectionViewSet 中的 my_records 方法
print("\n✅ 检查 2: InspectionViewSet 中的 my_records 方法")
print("-" * 70)

try:
    from core.api_views import InspectionViewSet
    
    if hasattr(InspectionViewSet, 'my_records'):
        print("✅ my_records 方法存在")
        
        # 获取方法信息
        method = getattr(InspectionViewSet, 'my_records')
        if hasattr(method, 'mapping'):
            print(f"   支持的 HTTP 方法: {method.mapping}")
    else:
        print("❌ my_records 方法不存在")
        
except Exception as e:
    print(f"❌ 检查失败: {e}")

# 3. 测试 API 端点
print("\n✅ 检查 3: 测试 my_records API 端点")
print("-" * 70)

try:
    # 获取测试用户
    test_user = User.objects.filter(groups__name='文物看护员').first()
    if not test_user:
        test_user = User.objects.first()
    
    if not test_user:
        print("❌ 没有可用的测试用户")
    else:
        print(f"✅ 使用测试用户: {test_user.username}")
        
        # 创建 API 请求
        factory = APIRequestFactory()
        viewset = InspectionViewSet.as_view({'get': 'my_records'})
        
        # 创建请求
        request = factory.get('/api/inspections/my-records/?page=1&page_size=20')
        force_authenticate(request, user=test_user)
        
        # 执行视图
        response = viewset(request)
        
        print(f"✅ 请求成功")
        print(f"   状态码: {response.status_code}")
        
        if response.status_code == 200:
            # 尝试获取数据
            if hasattr(response, 'data'):
                if isinstance(response.data, list):
                    print(f"   返回 {len(response.data)} 条记录")
                else:
                    print(f"   返回数据: {type(response.data)}")
        else:
            print(f"✅ 响应内容: {response.data if hasattr(response, 'data') else response.content}")
            
except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()

# 4. 检查 Admin 方法的异常处理
print("\n✅ 检查 4: Admin 显示方法的异常处理")
print("-" * 70)

try:
    from core.admin import InspectionAdmin
    
    admin_instance = InspectionAdmin(InspectionRecord, None)
    
    # 检查方法
    methods_to_check = [
        ('display_photo', 'display_photo'),
        ('location_display', 'location_display'),
        ('issue_summary', 'issue_summary'),
    ]
    
    all_good = True
    for method_name, _ in methods_to_check:
        if hasattr(admin_instance, method_name):
            print(f"✅ {method_name} 方法存在")
        else:
            print(f"❌ {method_name} 方法不存在")
            all_good = False
    
    if all_good:
        # 尝试调用这些方法
        test_record = InspectionRecord.objects.first()
        if test_record:
            print(f"\n   使用测试记录: {test_record.site.name}")
            
            # 测试 display_photo
            try:
                result = admin_instance.display_photo(test_record)
                print(f"✅ display_photo 执行成功: {result[:50] if len(str(result)) > 50 else result}")
            except Exception as e:
                print(f"❌ display_photo 执行失败: {e}")
            
            # 测试 location_display
            try:
                result = admin_instance.location_display(test_record)
                print(f"✅ location_display 执行成功: {result}")
            except Exception as e:
                print(f"❌ location_display 执行失败: {e}")
            
            # 测试 issue_summary
            try:
                result = admin_instance.issue_summary(test_record)
                print(f"✅ issue_summary 执行成功")
            except Exception as e:
                print(f"❌ issue_summary 执行失败: {e}")
        else:
            print("⚠️  没有可用的测试记录")
    
except Exception as e:
    print(f"❌ 检查失败: {e}")
    import traceback
    traceback.print_exc()

# 5. 检查 FormData 上传配置
print("\n✅ 检查 5: FormData 上传配置")
print("-" * 70)

try:
    with open('app/lib/services/api_service.dart', 'r', encoding='utf-8') as f:
        content = f.read()
        
    # 检查是否有使用 Options 和正确的处理
    if 'MultipartFile.fromFile' in content:
        print("✅ 使用了 MultipartFile.fromFile")
        
    if 'FormData.fromMap' in content:
        print("✅ 使用了 FormData.fromMap")
    
    # 检查是否移除了固定的 contentType
    if "_dio.post(" in content and "options: Options" in content:
        print("✅ post 请求中包含 Options 参数")
    
    # 检查 BaseOptions 中是否没有固定的 contentType
    if "contentType: 'application/json'" in content and "_dio.post" in content:
        # 检查这个是否在 BaseOptions 中
        lines = content.split('\n')
        has_fixed_contenttype = False
        for i, line in enumerate(lines):
            if "BaseOptions(" in line:
                # 查找下几行是否有固定的 contentType
                for j in range(i, min(i+10, len(lines))):
                    if "contentType: 'application/json'" in lines[j]:
                        has_fixed_contenttype = True
                        break
        
        if not has_fixed_contenttype:
            print("✅ BaseOptions 中没有固定 contentType (正确)")
        else:
            print("⚠️  BaseOptions 中仍有固定的 contentType，可能需要检查")
    
except Exception as e:
    print(f"❌ 检查失败: {e}")

# 总结
print("\n" + "="*70)
print("验证完成")
print("="*70)
print("\n下一步:")
print("1. 启动 Django 开发服务器: python manage.py runserver")
print("2. 重新编译 Flutter 应用: flutter pub get && flutter run -d 24129PN74C")
print("3. 测试app上传和同步功能")
print("4. 检查后台巡查记录列表是否正常显示")
print("\n")

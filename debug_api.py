#!/usr/bin/env python
"""
诊断脚本：测试API端点，模拟app提交数据

使用方法：
python manage.py shell < debug_api.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'heritage_system.settings')
django.setup()

from django.contrib.auth.models import User
from core.models import HeritageSite, InspectionRecord
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.test import APIClient
from django.core.files.uploadedfile import SimpleUploadedFile
import json

print("\n" + "="*60)
print("API 诊断脚本 - 巡查记录上传测试")
print("="*60 + "\n")

# 1. 检查用户
print("1️⃣ 检查用户...")
try:
    users = User.objects.all()
    print(f"   ✓ 系统中有 {users.count()} 个用户")
    
    # 查找文物看护员用户
    inspector_users = User.objects.filter(groups__name='文物看护员')
    print(f"   ✓ 文物看护员用户: {inspector_users.count()} 个")
    
    if inspector_users.count() > 0:
        test_user = inspector_users.first()
        print(f"   ✓ 使用测试用户: {test_user.username}")
    else:
        test_user = users.first()
        print(f"   ! 没有文物看护员，使用用户: {test_user.username}")
        
except Exception as e:
    print(f"   ❌ 错误: {e}")
    exit(1)

# 2. 检查文物点
print("\n2️⃣ 检查文物点...")
try:
    sites = HeritageSite.objects.all()
    print(f"   ✓ 系统中有 {sites.count()} 个文物点")
    
    if sites.count() > 0:
        test_site = sites.first()
        print(f"   ✓ 使用测试文物点: {test_site.name} (ID={test_site.id})")
    else:
        print("   ❌ 没有文物点，无法测试")
        exit(1)
        
except Exception as e:
    print(f"   ❌ 错误: {e}")
    exit(1)

# 3. 获取JWT Token
print("\n3️⃣ 获取JWT Token...")
try:
    refresh = RefreshToken.for_user(test_user)
    access_token = str(refresh.access_token)
    print(f"   ✓ Token 获取成功")
    print(f"   Token (前50字符): {access_token[:50]}...")
    
except Exception as e:
    print(f"   ❌ 错误: {e}")
    exit(1)

# 4. 测试JSON提交（不含照片）
print("\n4️⃣ 测试JSON提交（不含照片）...")
try:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
    
    payload = {
        'site': test_site.id,
        'is_normal': True,
        'issue_details': '正常',
        'latitude': 39.123,
        'longitude': 117.456,
    }
    
    response = client.post('/api/inspections/', payload, format='json')
    print(f"   Status Code: {response.status_code}")
    
    if response.status_code == 201:
        print(f"   ✓ 成功创建巡查记录")
        print(f"   Response: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    else:
        print(f"   ❌ 创建失败")
        print(f"   Response: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
        
except Exception as e:
    print(f"   ❌ 错误: {e}")
    import traceback
    traceback.print_exc()

# 5. 检查数据库中的巡查记录
print("\n5️⃣ 检查数据库中的巡查记录...")
try:
    records = InspectionRecord.objects.all()
    print(f"   ✓ 数据库中有 {records.count()} 条巡查记录")
    
    if records.count() > 0:
        latest = records.latest('inspect_time')
        print(f"   ✓ 最新记录: {latest.site.name} - {latest.inspector.username}")
        print(f"     ID: {latest.id}")
        print(f"     inspect_time: {latest.inspect_time}")
        print(f"     is_normal: {latest.is_normal}")
        print(f"     latitude: {latest.latitude}")
        print(f"     longitude: {latest.longitude}")
        
except Exception as e:
    print(f"   ❌ 错误: {e}")
    import traceback
    traceback.print_exc()

# 6. 测试获取我的巡查记录
print("\n6️⃣ 测试获取我的巡查记录...")
try:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
    
    response = client.get('/api/inspections/my-records/')
    print(f"   Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        if isinstance(data, list):
            print(f"   ✓ 成功获取 {len(data)} 条记录")
        else:
            print(f"   ✓ 成功获取数据")
    else:
        print(f"   ❌ 获取失败")
        print(f"   Response: {response.json()}")
        
except Exception as e:
    print(f"   ❌ 错误: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("诊断完成")
print("="*60 + "\n")

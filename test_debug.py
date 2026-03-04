#!/usr/bin/env python
import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'heritage_system.settings')
django.setup()

from core.models import HeritageSite, InspectionRecord

# 获取第一个文物
site = HeritageSite.objects.first()
if site:
    print(f'文物ID: {site.id}')
    print(f'文物名称: {site.name}')
    print(f'经度: {site.longitude}')
    print(f'纬度: {site.latitude}')
    
    # 检查坐标数据是否可以解析
    try:
        protection = json.loads(site.protection_zone) if site.protection_zone else []
        print(f'保护范围: {len(protection)} 个顶点' if protection else '保护范围: 无数据')
    except Exception as e:
        print(f'保护范围解析错误: {e}')
    
    try:
        control = json.loads(site.control_zone) if site.control_zone else []
        print(f'建控地带: {len(control)} 个顶点' if control else '建控地带: 无数据')
    except Exception as e:
        print(f'建控地带解析错误: {e}')
    
    # 检查巡查记录（使用正确的字段名 site）
    records = InspectionRecord.objects.filter(site=site).order_by('-inspect_time')[:10]
    print(f'巡查记录数: {records.count()}')
    
    if records.exists():
        for record in records[:3]:
            print(f'  - {record.inspect_time}: {record.inspector.username if record.inspector else "未知"}')
else:
    print('数据库中无文物数据')


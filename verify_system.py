#!/usr/bin/env python
"""
系统巡查功能验证脚本
用于检查看护员账户管理系统是否配置正确
"""

import os
import sys
import django

# 配置Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'heritage_system.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from django.contrib.auth.models import User, Group, Permission
from core.models import InspectionRecord, HeritageSite
from django.core.management import call_command

def check_system():
    """检查系统配置"""
    print("\n" + "="*60)
    print("🔍 文物看护员管理系统 - 完整性检查")
    print("="*60 + "\n")
    
    # 1. 检查用户组
    print("1️⃣  检查用户组...")
    try:
        group = Group.objects.get(name='文物看护员')
        print(f"   ✓ 找到'文物看护员'组")
        print(f"   - 成员数量: {group.user_set.count()}人")
        print(f"   - 权限数量: {group.permissions.count()}个")
        
        # 显示权限
        perms = [f"{p.content_type.app_label}.{p.codename}" for p in group.permissions.all()]
        for perm in perms:
            print(f"     • {perm}")
    except Group.DoesNotExist:
        print("   ✗ 未找到'文物看护员'组 - 需要运行 create_inspectors 命令")
    
    # 2. 检查看护员账户
    print("\n2️⃣  检查看护员账户...")
    inspector_users = User.objects.filter(username__startswith='inspector_')
    print(f"   ✓ 找到 {inspector_users.count()} 个看护员账户")
    
    if inspector_users.count() >= 18:
        print("   ✓ 已创建18个或以上账户")
        # 显示前3个和后3个
        for user in inspector_users[:3]:
            print(f"     • {user.username} - {user.email}")
        if inspector_users.count() > 6:
            print(f"     ... ({inspector_users.count() - 6}个其他)")
        for user in inspector_users[max(0, inspector_users.count()-3):]:
            print(f"     • {user.username} - {user.email}")
    else:
        print(f"   ⚠️  仅找到 {inspector_users.count()} 个账户，需要运行 python manage.py create_inspectors")
    
    # 3. 检查巡查记录权限
    print("\n3️⃣  检查巡查记录权限...")
    perms_needed = ['add_inspectionrecord', 'change_inspectionrecord', 'view_inspectionrecord']
    has_all_perms = all(
        Permission.objects.filter(
            codename=perm,
            content_type__app_label='core'
        ).exists() for perm in perms_needed
    )
    
    if has_all_perms:
        print("   ✓ 所有必需权限已配置")
        for perm in perms_needed:
            print(f"     • {perm}")
    else:
        print("   ✗ 缺少必需权限")
    
    # 4. 检查文物点数据
    print("\n4️⃣  检查文物点数据...")
    heritage_count = HeritageSite.objects.count()
    print(f"   ✓ 数据库中有 {heritage_count} 个文物点")
    
    if heritage_count == 0:
        print("   ⚠️  没有文物点数据，看护员无法添加巡查记录")
    
    # 5. 检查巡查记录
    print("\n5️⃣  检查巡查记录...")
    inspection_count = InspectionRecord.objects.count()
    print(f"   ✓ 数据库中有 {inspection_count} 条巡查记录")
    
    if inspection_count > 0:
        # 显示按看护员统计
        from django.db.models import Count
        stats = InspectionRecord.objects.values('inspector__username').annotate(count=Count('id'))
        print("   - 看护员巡查统计:")
        for stat in stats[:5]:
            print(f"     • {stat['inspector__username']}: {stat['count']}条")
        if stats.count() > 5:
            print(f"     ... ({stats.count() - 5}个其他)")
    
    # 6. 检查Django设置
    print("\n6️⃣  检查Django设置...")
    from django.conf import settings
    print(f"   ✓ 系统名称: {getattr(settings, 'SYSTEM_NAME', '未配置')}")
    print(f"   ✓ 系统版本: {getattr(settings, 'SYS_VERSION', '未配置')}")
    
    print("\n" + "="*60)
    print("✅ 检查完成!")
    print("="*60 + "\n")
    
    # 提供建议
    print("📋 后续建议:\n")
    print("1. 如果看护员账户不足18个，运行:")
    print("   python manage.py create_inspectors\n")
    
    print("2. 看护员首次登录建议修改密码")
    print("   management/commands/create_inspectors.py 中可查看默认密码模式\n")
    
    print("3. 若要重置所有密码:")
    print("   python manage.py create_inspectors --reset-passwords\n")
    
    print("4. 若要删除所有看护员账户:")
    print("   python manage.py create_inspectors --delete\n")
    
    print("5. 启动Django开发服务器测试:")
    print("   python manage.py runserver\n")
    
    print("6. 访问后台查看新菜单:")
    print("   http://localhost:8000/admin/\n")

if __name__ == '__main__':
    check_system()

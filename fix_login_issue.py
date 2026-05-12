#!/usr/bin/env python
"""
修复无法登陆问题 - 为旧数据库迁移 UserProfile 数据

用法:
  python fix_login_issue.py
  
这个脚本会：
  1. 检查数据库结构
  2. 创建缺失的 UserProfile 记录
  3. 验证用户数据完整性
"""
import os
import sys
import django
from pathlib import Path

# 配置 Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'heritage_system.settings')
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
django.setup()

from django.contrib.auth.models import User
from core.models import UserProfile
from django.db import connection
from django.db.utils import ProgrammingError, OperationalError


def check_table_exists(table_name):
    """检查数据表是否存在"""
    with connection.cursor() as cursor:
        try:
            cursor.execute(f"SELECT 1 FROM {table_name} LIMIT 1")
            return True
        except (ProgrammingError, OperationalError):
            return False


def get_applied_migrations():
    """获取已应用的迁移列表"""
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT app, name FROM django_migrations ORDER BY applied")
            return [(row[0], row[1]) for row in cursor.fetchall()]
    except Exception:
        return []


def run_migrations():
    """运行数据库迁移"""
    print("\n  执行: python manage.py migrate")
    from django.core.management import execute_from_command_line
    try:
        execute_from_command_line(['manage.py', 'migrate', '--no-input'])
        print("  ✓ 迁移完成")
        return True
    except Exception as e:
        print(f"  ❌ 迁移失败: {str(e)}")
        return False


def fix_login_issue():
    """修复登陆问题"""
    print("=" * 70)
    print("  heritage_system 登陆问题修复工具")
    print("=" * 70)
    
    # 1. 检查数据库表
    print("\n[1/4] 检查数据库表...")
    user_table_exists = check_table_exists('auth_user')
    profile_table_exists = check_table_exists('core_userprofile')
    
    print(f"  - auth_user 表存在: {user_table_exists}")
    print(f"  - core_userprofile 表存在: {profile_table_exists}")
    
    if not user_table_exists:
        print("\n❌ 错误: 用户表不存在，数据库需要初始化")
        return False
    
    # 2. 如果 UserProfile 表不存在，需要运行迁移
    if not profile_table_exists:
        print("\n[2/4] 检测到 UserProfile 表不存在，正在运行迁移...")
        if not run_migrations():
            print("\n❌ 迁移失败，请检查错误日志")
            return False
    else:
        print("\n[2/4] UserProfile 表已存在，跳过迁移")
    
    # 3. 为所有用户创建缺失的 UserProfile
    print("\n[3/4] 为现有用户创建缺失的 UserProfile...")
    try:
        users = User.objects.all()
        total_users = users.count()
        created_count = 0
        failed_users = []
        
        if total_users == 0:
            print("  ℹ️  系统中没有用户")
        else:
            for user in users:
                try:
                    profile, was_created = UserProfile.objects.get_or_create(user=user)
                    if was_created:
                        created_count += 1
                        print(f"  ✓ {user.username}")
                except Exception as e:
                    failed_users.append((user.username, str(e)))
                    print(f"  ❌ {user.username}: {str(e)}")
            
            print(f"\n  总结: 共 {total_users} 个用户，新建 {created_count} 个 UserProfile")
            
            if failed_users:
                print(f"  ⚠️  失败: {len(failed_users)} 个用户")
                return False
    except Exception as e:
        print(f"  ❌ 创建 UserProfile 失败: {str(e)}")
        return False
    
    # 4. 验证登陆功能
    print("\n[4/4] 验证用户数据完整性...")
    
    try:
        incomplete_users = []
        for user in User.objects.all():
            try:
                profile = UserProfile.objects.get(user=user)
            except UserProfile.DoesNotExist:
                incomplete_users.append(user.username)
        
        if incomplete_users:
            print(f"  ❌ 存在缺失 UserProfile 的用户: {', '.join(incomplete_users)}")
            return False
        else:
            print("  ✓ 所有用户的 UserProfile 都已准备好")
            
            # 尝试访问 user.profile 确保关系正常
            test_user = User.objects.first()
            if test_user:
                profile = test_user.profile
                print(f"  ✓ 验证关系访问: {test_user.username}.profile 可用")
    
    except Exception as e:
        print(f"  ❌ 验证失败: {str(e)}")
        return False
    
    print("\n" + "=" * 70)
    print("  ✅ 修复完成!")
    print("=" * 70)
    print("\n后续步骤:")
    print("  1. 重启应用: systemctl restart heritage_system")
    print("  2. 尝试登陆: 用之前的账号登陆测试")
    print("  3. 检查权限: 确保用户权限配置正确")
    print()
    return True


if __name__ == '__main__':
    try:
        success = fix_login_issue()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️  操作已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

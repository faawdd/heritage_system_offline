# 登陆问题诊断与修复指南

## 问题原因分析

当你停止上传 `db.sqlite3` 文件后，服务器上的旧数据库会被保留。但是，新代码中添加了 `UserProfile` 模型（来自迁移 `0008_userprofile.py`），旧数据库可能缺少这个表，导致登陆失败。

### 具体表现：
- 旧用户无法登陆
- 系统抛出 `UserProfile.DoesNotExist` 异常
- 或者 `core_userprofile` 表不存在

## 修复步骤

### 第一步：在服务器上应用数据库迁移

```bash
cd /path/to/heritage_system
source .venv/bin/activate
python manage.py migrate
```

这会创建所有缺失的表，包括 `UserProfile` 表。

### 第二步：为现有用户创建 UserProfile 记录

在服务器上运行 Python 脚本：

```bash
python manage.py shell
```

然后在 Django shell 中执行：

```python
from django.contrib.auth.models import User
from core.models import UserProfile

# 为所有现有用户创建 UserProfile
users = User.objects.all()
for user in users:
    profile, created = UserProfile.objects.get_or_create(user=user)
    if created:
        print(f"为 {user.username} 创建了 UserProfile")
    else:
        print(f"{user.username} 已有 UserProfile")

print(f"\n完成: 总共 {users.count()} 个用户")

# 验证
missing = []
for user in users:
    if not hasattr(user, 'profile') or user.profile is None:
        try:
            UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            missing.append(user.username)

if missing:
    print(f"\n⚠️  警告：以下用户缺失 UserProfile: {', '.join(missing)}")
else:
    print("\n✅ 所有用户都有 UserProfile")
```

### 第三步：重启应用并测试登陆

```bash
# 如果使用 gunicorn
systemctl restart heritage_system

# 或者如果使用 uwsgi
systemctl restart uwsgi

# 或者其他服务管理方式
```

然后用旧用户账号尝试登陆。

## 自动化修复脚本

或者，将下面的脚本保存为 `fix_db_userprofile.py` 并在服务器上运行：

```python
#!/usr/bin/env python
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'heritage_system.settings')
sys.path.insert(0, '/path/to/heritage_system')
django.setup()

from django.contrib.auth.models import User
from core.models import UserProfile

print("修复 UserProfile 缺失问题...")

users = User.objects.all()
created_count = 0

for user in users:
    profile, created = UserProfile.objects.get_or_create(user=user)
    if created:
        created_count += 1
        print(f"  ✓ {user.username}")

print(f"\n完成: 新建 {created_count}/{users.count()} 个 UserProfile")

# 验证
try:
    for user in users:
        _ = user.profile
    print("✅ 验证成功: 所有用户都能访问 profile")
except Exception as e:
    print(f"❌ 验证失败: {e}")
    sys.exit(1)
```

运行方式：
```bash
python fix_db_userprofile.py
```

## 预防措施

为了防止将来类似问题，建议：

1. **保持迁移记录**：每当部署新代码时，确保运行 `python manage.py migrate`
2. **自动迁移**：在启动脚本或 WSGI 应用初始化中自动运行迁移
3. **备份数据库**：定期备份 SQLite 数据库，保留版本历史
4. **生产环境检查清单**：
   - ☐ 代码更新后运行 `python manage.py migrate`
   - ☐ 检查所有系统表是否正确创建
   - ☐ 测试关键功能（特别是登陆和权限系统）

## 快速诊断

如果还有问题，可以运行以下诊断命令：

```bash
# 检查数据库状态
python manage.py check

# 查看待应用的迁移
python manage.py showmigrations

# 查看已应用的迁移
python manage.py showmigrations --list

# 检查用户数量
python manage.py shell -c "from django.contrib.auth.models import User; print(f'用户数: {User.objects.count()}')"

# 检查 UserProfile 数量
python manage.py shell -c "from core.models import UserProfile; print(f'UserProfile 数: {UserProfile.objects.count()}')"
```

## 技术背景

新增的 `UserProfile` 模型用于：
- 跟踪用户是否已修改初始密码（首次登陆提醒）
- 记录首次登陆时间
- 存储用户联系方式

这个模型通过 Django Signal 与 User 模型关联，确保每个用户都有一个对应的 Profile。

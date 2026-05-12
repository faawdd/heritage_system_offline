# 服务器登陆问题修复清单

## 问题诊断

**问题**: 停止上传 `db.sqlite3` 后，服务器上旧数据库被保留，但无法登陆账号

**根本原因**: 旧数据库缺少新代码中添加的 `UserProfile` 表

### 时间线

- **之前**: 每次部署都上传新的 `db.sqlite3`，完全覆盖旧数据库
- **现在**: 停止上传数据库，保留旧数据库中的数据
- **问题**：旧数据库的表结构与新代码不匹配

## 快速修复 (5 分钟)

### 第一步：在服务器上运行迁移

```bash
cd /path/to/heritage_system
source .venv/bin/activate

# 应用所有待处理的数据库迁移
python manage.py migrate
```

**输出应该包含**：
```
Running migrations:
  ...
  Applying core.0008_userprofile... OK
  ...
```

### 第二步：为现有用户创建 UserProfile

```bash
# 方法 A：使用自动修复脚本（推荐）
python fix_login_issue.py

# 方法 B：手动运行（如果脚本失败）
python manage.py shell << EOF
from django.contrib.auth.models import User
from core.models import UserProfile

for user in User.objects.all():
    UserProfile.objects.get_or_create(user=user)
    print(f"✓ {user.username}")

print(f"✅ 完成: {User.objects.count()} 个用户已处理")
EOF
```

### 第三步：重启应用

```bash
# 重启 Gunicorn / Uwsgi / systemd 服务
systemctl restart heritage_system

# 或者手动重启应用容器
docker restart heritage_system  # 如果使用 Docker
```

### 第四步：测试登陆

在浏览器中打开 `https://beichenhome.top:9081/admin/`，用旧账号登陆测试

## 详细说明

### 为什么会出现这个问题？

1. **迁移 0008** 在代码中添加了 `UserProfile` 模型
   ```python
   class UserProfile(models.Model):
       user = models.OneToOneField(User, on_delete=models.CASCADE)
       has_changed_password = models.BooleanField(default=False)
       first_login_at = models.DateTimeField(null=True, blank=True)
   ```

2. **旧数据库** 还没有这个表（因为从未运行过 `python manage.py migrate`）

3. **新代码** 的 `signals.py` 依赖这个模型：
   ```python
   @receiver(post_save, sender=User)
   def save_user_profile(sender, instance, **kwargs):
       profile = UserProfile.objects.get(user=instance)  # ← 如果表不存在就失败
   ```

4. **登陆时失败**：认证系统尝试保存用户时，信号处理程序找不到 UserProfile 表或记录

### 迁移文件列表

服务器需要应用以下迁移（如果还没有应用）：

```
✓ 0001_initial                    - 基础模型
✓ 0002_auto_20260303_1100        - 自动修改
✓ ...
✗ 0008_userprofile                - 用户密码修改追踪（需要应用）
✓ 0009_alter_projectaudit_options - 之后的迁移可能已经应用
```

查看当前状态：
```bash
python manage.py showmigrations core
```

### 修复涉及的文件

| 文件 | 作用 |
|------|------|
| `fix_login_issue.py` | 自动诊断和修复脚本 |
| `LOGIN_FIX_GUIDE.md` | 详细修复指南 |
| `core/models.py` | UserProfile 模型定义 |
| `core/signals.py` | UserProfile 创建信号处理 |
| `core/migrations/0008_userprofile.py` | 数据库迁移文件 |

## 故障排查

### 如果迁移失败

```bash
# 检查数据库状态
python manage.py check

# 查看错误详情
python manage.py migrate --verbosity 2

# 强制查看所有迁移
python manage.py showmigrations --plan
```

### 如果登陆还是失败

```bash
# 检查服务器日志
tail -f /var/log/heritage_system/error.log
tail -f /var/log/heritage_system/access.log

# Django 调试信息
python manage.py shell
>>> from django.contrib.auth.models import User
>>> from core.models import UserProfile
>>> user = User.objects.first()
>>> print(user.profile)  # 应该返回 UserProfile 对象
```

### 如果脚本执行有权限问题

```bash
# 检查数据库文件权限
ls -la db.sqlite3*
chmod 666 db.sqlite3

# 检查应用目录权限
chmod -R 755 /path/to/heritage_system
```

## 预防措施

为了防止将来再出现类似问题，建议：

### 1. 自动迁移检查

修改 `heritage_system/wsgi.py`：
```python
from django.core.wsgi import get_wsgi_application
from django.core.management import execute_from_command_line

# 在应用启动时自动运行迁移
execute_from_command_line(['manage.py', 'migrate', '--no-input'])

application = get_wsgi_application()
```

### 2. 部署脚本

创建 `deploy.sh`：
```bash
#!/bin/bash
cd /path/to/heritage_system
git pull
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate --no-input
python manage.py collectstatic --no-input
systemctl restart heritage_system
```

### 3. 定期检查

```bash
# 添加到 crontab，每周检查一次
0 3 * * 0 cd /path/to/heritage_system && .venv/bin/python fix_login_issue.py >> /var/log/heritage_system/weekly_check.log 2>&1
```

## 相关文档

- [项目结构说明](📑_项目探索总索引.md)
- [用户管理系统](用户管理功能实现完成报告.md)
- [权限管理](权限管理系统整理说明.md)
- [系统部署](fastapi_server/deploy/DEPLOY_PROD.md)

## 联系支持

如果按照本指南修复后仍有问题，请收集以下信息：

```bash
# 1. 迁移状态
python manage.py showmigrations

# 2. 用户和 UserProfile 数量
python manage.py shell -c "from django.contrib.auth.models import User; from core.models import UserProfile; print(f'Users: {User.objects.count()}, Profiles: {UserProfile.objects.count()}')"

# 3. 最近的错误日志
tail -100 /var/log/heritage_system/error.log
```

---

**最后更新**: 2026-05-12  
**适用版本**: Django 6.0.2+

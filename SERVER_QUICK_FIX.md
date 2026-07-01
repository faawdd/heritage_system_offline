# 服务器快速修复指南

## 一键修复 (推荐)

在服务器上执行：

```bash
cd /home/flower/heritage_system
chmod +x sync.sh
./sync.sh
```

这个脚本会自动：
1. ✓ 同步最新代码
2. ✓ 应用数据库迁移
3. ✓ **修复登陆问题**（为所有用户创建 UserProfile）
4. ✓ 收集静态文件
5. ✓ 重启服务
6. ✓ 验证服务状态

预计耗时：3-5 分钟

## 如果脚本执行失败

### 方案 A：分步执行

```bash
cd /home/flower/heritage_system
source venv/bin/activate

# 步骤 1：应用迁移
python manage.py migrate --no-input

# 步骤 2：修复 UserProfile
python manage.py shell << 'EOF'
from django.contrib.auth.models import User
from core.models import UserProfile

for user in User.objects.all():
    UserProfile.objects.get_or_create(user=user)
    print(f"✓ {user.username}")

print(f"✅ 完成: {User.objects.count()} 个用户")
EOF

# 步骤 3：收集静态文件
python manage.py collectstatic --noinput

# 步骤 4：重启服务
sudo systemctl restart heritage
sudo systemctl restart heritage_fastapi
```

### 方案 B：使用自动脚本（如果脚本失败）

```bash
python fix_login_issue.py
```

## 验证修复

修复后立即测试：

```bash
# 1. 检查 UserProfile 是否已创建
python manage.py shell -c "from core.models import UserProfile; print(f'✓ UserProfile 数量: {UserProfile.objects.count()}')"

# 2. 检查服务状态
sudo systemctl status heritage
sudo systemctl status heritage_fastapi

# 3. 查看最近的日志
tail -50 /var/log/heritage_system/error.log
```

## 登陆测试

在浏览器中访问：
- https://beichenhome.top:9081/admin/
- 用旧的用户账号登陆

## 常见问题

### Q: 脚本说 "UserProfile 修复失败，但继续重启服务"
**A:** 检查是否有权限问题
```bash
# 确保数据库文件可读写
ls -la db.sqlite3*
chmod 666 db.sqlite3
```

### Q: 服务重启后还是登陆不了
**A:** 查看应用日志
```bash
# Django 日志
tail -100 /var/log/heritage_system/error.log

# Systemd 日志
sudo journalctl -u heritage -n 50
sudo journalctl -u heritage_fastapi -n 50
```

### Q: 迁移显示 "no changes detected"
**A:** 这是正常的，说明迁移已经应用过了，继续执行下一步

## 脚本说明

改进的 `sync.sh` 包含：

| 步骤 | 动作 | 目的 |
|------|------|------|
| 1 | `git config` | 添加安全目录 |
| 2 | `git fetch` | 获取最新代码 |
| 3 | `git reset` | 强制同步到远程分支 |
| 4 | `chown/pip install/migrate` | 权限、依赖、迁移 |
| 5 | 创建 UserProfile | **修复登陆问题的关键** |
| 6 | `collectstatic` | 后台静态资源更新生效 |
| 7 | `systemctl restart` | 重启服务 |

---

**执行时间**: ~3-5 分钟  
**需要权限**: sudo (systemctl restart 需要)  
**备份**: 脚本执行前自动备份 git 状态

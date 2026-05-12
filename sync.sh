#!/bin/bash
# heritage_system 服务器同步和修复脚本
# 功能：自动同步代码、应用迁移、修复登陆问题、收集静态文件、重启服务

set -e  # 遇到错误立即退出

echo "=================================="
echo "heritage_system 服务器同步脚本"
echo "=================================="
echo ""

# 1. 解决可能存在的权限报错
echo "[1/7] 配置 git 安全目录..."
git config --global --add safe.directory /home/flower/heritage_system

# 2. 获取最新索引
echo "[2/7] 获取最新代码索引..."
git fetch --all

# 3. 自动获取当前分支名并强制重置
CURRENT_BRANCH=$(git symbolic-ref --short -q HEAD || echo "master")
echo "[3/7] 强制同步远程分支: origin/$CURRENT_BRANCH"
git reset --hard origin/$CURRENT_BRANCH

# 4. 权限与环境恢复
echo "[4/7] 恢复权限和环境..."
sudo chown -R flower: .
source venv/bin/activate
pip install -r requirements.txt -q

# 5. 应用数据库迁移
echo "[5/7] 应用数据库迁移..."
python manage.py migrate --no-input

# 6. 修复登陆问题 - 为现有用户创建 UserProfile
echo "[6/7] 修复用户 Profile 缺失问题..."
python manage.py shell << 'EOF'
from django.contrib.auth.models import User
from core.models import UserProfile
import sys

try:
    users = User.objects.all()
    created_count = 0
    failed_count = 0
    
    for user in users:
        try:
            profile, was_created = UserProfile.objects.get_or_create(user=user)
            if was_created:
                created_count += 1
                print(f"  ✓ 为 {user.username} 创建了 UserProfile")
        except Exception as e:
            failed_count += 1
            print(f"  ❌ 为 {user.username} 创建 UserProfile 失败: {str(e)}")
    
    total_users = users.count()
    print(f"\n总结: {total_users} 个用户，新建 {created_count} 个 Profile，失败 {failed_count} 个")
    
    if failed_count > 0:
        sys.exit(1)
except Exception as e:
    print(f"错误: {str(e)}")
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    echo "❌ UserProfile 修复失败，但继续重启服务..."
fi

# 7. 静态文件收集 (SimpleUI 大字体 CSS 生效的关键)
echo "[7/7] 收集静态文件..."
python manage.py collectstatic --noinput --no-color 2>&1 | grep -E "^(Copying|Post-processed|[0-9]+ static files)" || true

# 8. 重启服务
echo ""
echo "重启服务..."
sudo systemctl restart heritage_fastapi
sudo systemctl restart heritage

# 9. 验证服务状态
echo ""
echo "=================================="
echo "✅ 服务器端代码已强制更新并重启!"
echo "=================================="
echo ""
echo "服务状态:"
sudo systemctl status heritage_fastapi --no-pager | head -3
sudo systemctl status heritage --no-pager | head -3
echo ""
echo "后续步骤:"
echo "  1. 访问 https://beichenhome.top:9081/admin/"
echo "  2. 用旧账号登陆测试"
echo "  3. 检查权限配置"

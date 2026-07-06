#!/bin/bash
# heritage_system 服务器同步和修复脚本
# 功能：自动同步代码、应用迁移、修复登陆问题、收集静态文件、重启服务

set -Eeuo pipefail

echo "=================================="
echo "heritage_system 服务器同步脚本"
echo "=================================="
echo ""

BACKUP_DB_PATH=""
DB_FILE="data/database.db"

backup_database() {
    if [ -f "$DB_FILE" ]; then
        BACKUP_DB_PATH="$(mktemp /tmp/heritage_db_backup.XXXXXX)"
        cp "$DB_FILE" "$BACKUP_DB_PATH"
        echo "已备份当前数据库到: $BACKUP_DB_PATH"
    fi
}

restore_database() {
    if [ -n "$BACKUP_DB_PATH" ] && [ -f "$BACKUP_DB_PATH" ]; then
        cp "$BACKUP_DB_PATH" "$DB_FILE"
        echo "已恢复数据库文件"
    fi
}

cleanup_on_exit() {
    local exit_code=$?
    if [ "$exit_code" -ne 0 ]; then
        echo "检测到脚本异常退出(ExitCode=$exit_code)，开始回滚数据库..."
        restore_database
    fi
}

trap cleanup_on_exit EXIT

if [ -x ./push_code.sh ]; then
    read -rp "是否先执行上传脚本 push_code.sh 并推送到仓库? [y/N]: " RUN_PUSH
    case "$RUN_PUSH" in
        [Yy]*)
            echo "准备先执行代码上传脚本..."
            ./push_code.sh
            ;;
    esac
fi

backup_database

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

# 成功同步代码后立即恢复数据库快照，避免被 git reset 影响
restore_database

# 4. 权限与环境恢复
echo "[4/7] 恢复权限和环境..."
sudo chown -R flower: .
if [ -f .venv/bin/activate ]; then
    # 新环境优先使用 .venv
    source .venv/bin/activate
elif [ -f venv/bin/activate ]; then
    source venv/bin/activate
else
    echo "❌ 未找到可用虚拟环境(.venv/venv)，请先创建并安装依赖"
    exit 1
fi

pip install -r requirements.txt -q

# 可选：前端构建（若构建产物不入库，建议开启）
if [ -f frontend/package.json ]; then
    read -rp "是否执行前端构建 npm run build? [y/N]: " RUN_FRONTEND_BUILD
    case "$RUN_FRONTEND_BUILD" in
        [Yy]*)
            echo "构建前端静态资源..."
            (cd frontend && npm ci --silent && npm run build)
            ;;
    esac
fi

# 5. 应用数据库迁移
echo "[5/7] 应用数据库迁移..."
python manage.py sqlcipher_bootstrap

# 6. 修复登陆问题 - 为现有用户创建 UserProfile
echo "[6/7] 修复用户 Profile 缺失问题..."
if ! python manage.py shell << 'EOF'
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
then
    echo "❌ UserProfile 修复失败，但继续重启服务..."
fi

# 7. 静态文件收集（后台与前端静态资源更新的关键）
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

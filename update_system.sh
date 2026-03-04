#!/bin/bash

# --- 配置项 ---
PROJECT_DIR="/home/flower/heritage_system"
VENV_PATH="$PROJECT_DIR/venv"
LOG_FILE="$PROJECT_DIR/update_log.txt"

echo "------------------------------------------"
echo "🚀 开始更新文物一张图系统 - $(date '+%Y-%m-%d %H:%M:%S')"
echo "------------------------------------------"

cd $PROJECT_DIR || { echo "❌ 目录不存在"; exit 1; }

# 1. 安全备份数据库 (重要：防止迁移失败导致数据损坏)
if [ -f "db.sqlite3" ]; then
    echo "📦 正在备份数据库..."
    cp db.sqlite3 "db.sqlite3.bak_$(date +%Y%m%d_%H%M%S)"
fi

# 2. 激活虚拟环境
echo "🐍 激活虚拟环境..."
source "$VENV_PATH/bin/activate"

# 3. 安装依赖 (仅当 requirements.txt 变化时，这里直接运行也很快)
echo "📥 检查并更新依赖..."
pip install -r requirements.txt | grep -v "already satisfied"

# 4. 执行数据库迁移
echo "🗄️ 正在应用数据库迁移..."
python manage.py makemigrations --noinput
python manage.py migrate --noinput

# 5. 收集静态文件
echo "🎨 收集静态文件..."
python manage.py collectstatic --noinput

# 6. 重启 Systemd 服务
echo "🔄 重启 Gunicorn (heritage) 服务..."
sudo systemctl restart heritage

# 7. 检查服务状态
if systemctl is-active --quiet heritage; then
    echo "✅ 更新成功！系统已重新上线。"
else
    echo "❌ 警告：服务重启后未正常运行，请执行 'journalctl -u heritage -f' 查看日志。"
fi

echo "------------------------------------------"

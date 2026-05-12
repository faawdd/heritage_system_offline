#!/bin/bash
# heritage_system 服务器代码上传脚本
# 功能：提交并推送当前代码到远程仓库，默认不包含数据库文件

set -e

PROJECT_ROOT="/home/flower/heritage_system"
cd "$PROJECT_ROOT"

echo "=================================="
echo "heritage_system 代码上传脚本"
echo "=================================="
echo ""

git config --global --add safe.directory "$PROJECT_ROOT"

CURRENT_BRANCH=$(git symbolic-ref --short -q HEAD || echo "master")
echo "当前分支: $CURRENT_BRANCH"

if git ls-files --error-unmatch db.sqlite3 >/dev/null 2>&1; then
    echo "检测到 db.sqlite3 仍被 Git 跟踪，准备从仓库中移除"
    git rm --cached -f db.sqlite3
fi

if git ls-files --error-unmatch db.sqlite3.bak_20260303_234321 >/dev/null 2>&1; then
    git rm --cached -f db.sqlite3.bak_20260303_234321
fi

echo ""
echo "请输入提交说明（直接回车使用默认说明）："
read -r COMMIT_MESSAGE
if [ -z "$COMMIT_MESSAGE" ]; then
    COMMIT_MESSAGE="chore: sync code $(date '+%Y-%m-%d %H:%M')"
fi

git add .gitignore sync.sh push_code.sh
git add manage.py core heritage_system fastapi_server templates static requirements.txt *.md 2>/dev/null || true

if git diff --cached --quiet; then
    echo "没有可提交的代码变更"
    exit 0
fi

git commit -m "$COMMIT_MESSAGE"
git push origin "$CURRENT_BRANCH"

echo ""
echo "✅ 代码已提交并推送到远程仓库"
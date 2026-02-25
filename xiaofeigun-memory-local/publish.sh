#!/bin/bash
# GitHub 发布脚本
# 请手动运行此脚本

echo "🪄 发布 xiaofeigun-memory-local 到 GitHub"
echo ""
echo "步骤："
echo ""
echo "1. 登录 GitHub:"
echo "   邮箱: xiaofeigun_kimi@hotmail.com"
echo "   密码: xiAofeiguN2026Kimi"
echo ""
echo "2. 创建新仓库:"
echo "   访问: https://github.com/new"
echo "   仓库名: xiaofeigun-memory-local"
echo "   描述: 🪄 小飞棍轻量级本地记忆搜索系统 - BM25-based local memory search for OpenClaw"
echo "   选择: Public"
echo "   勾选: Add a README file (可选)"
echo ""
echo "3. 推送代码:"
echo "   cd /root/.openclaw/workspace/skills/xiaofeigun-memory-local"
echo "   git remote add origin https://github.com/xiaofeigun/xiaofeigun-memory-local.git"
echo "   git branch -M main"
echo "   git push -u origin main"
echo ""
echo "4. 完成！🎉"
echo ""
echo "或者直接运行以下命令:"
echo ""
cat << 'EOF'
cd /root/.openclaw/workspace/skills/xiaofeigun-memory-local
git remote add origin https://github.com/xiaofeigun/xiaofeigun-memory-local.git 2>/dev/null || true
git branch -M main
git push -u origin main
EOF

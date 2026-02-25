#!/bin/bash
# SSH 方式发布到 GitHub

echo "🔑 使用 SSH 方式发布到 GitHub"
echo ""
echo "步骤 1: 添加 SSH 公钥到 GitHub"
echo "================================"
echo ""
echo "1. 登录 GitHub: https://github.com/login"
echo "   邮箱: xiaofeigun_kimi@hotmail.com"
echo "   密码: xiAofeiguN2026Kimi"
echo ""
echo "2. 添加 SSH 密钥:"
echo "   访问: https://github.com/settings/keys"
echo "   点击: New SSH key"
echo "   标题: xiaofeigun-server"
echo "   类型: Authentication Key"
echo ""
echo "3. 复制以下公钥内容粘贴:"
echo "--------------------------------"
cat ~/.ssh/id_ed25519.pub
echo "--------------------------------"
echo ""
echo "步骤 2: 创建仓库"
echo "================================"
echo ""
echo "访问: https://github.com/new"
echo "仓库名: xiaofeigun-memory-local"
echo "描述: 🪄 小飞棍轻量级本地记忆搜索系统"
echo "选择: Public"
echo ""
echo "步骤 3: 推送代码"
echo "================================"
echo ""
echo "运行以下命令:"
echo ""
cat << 'EOF'
cd /root/.openclaw/workspace/skills/xiaofeigun-memory-local
git remote remove origin 2>/dev/null || true
git remote add origin git@github.com:xiaofeigun/xiaofeigun-memory-local.git
git branch -M main
git push -u origin main
EOF
echo ""
echo "如果第一次连接 GitHub，会提示确认指纹，输入 yes 即可"
echo ""
echo "🎉 完成！"

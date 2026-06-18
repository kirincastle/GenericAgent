#!/usr/bin/env bash
# ga_sync.sh — 跨机同步工具
# 用法:
#   ./ga_sync.sh          → 交互式菜单
#   ./ga_sync.sh pull     → 拉取最新代码+记忆
#   ./ga_sync.sh push     → 推送本地变更（代码+记忆+git跟踪的文件）
#   ./ga_sync.sh status   → 检查同步状态
#   ./ga_sync.sh auto     → 自动模式：先pull，提示是否push

set -euo pipefail
cd "$(git rev-parse --show-toplevel 2>/dev/null || echo '.')"

BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'rtk-integration')"
REMOTE="origin"

echo "📡 GA Sync — 分支: $BRANCH"
echo "========================================"

pull() {
    echo "🔄 拉取最新代码+记忆..."
    git pull "$REMOTE" "$BRANCH" 2>&1 || {
        echo "⚠️  git pull 失败"
        echo "   可能原因: 本地有未提交变更、网络不通、SSH 密钥未配置"
        echo "   手动处理: git status → 解决冲突 → 重试"
        exit 1
    }
    echo ""
    echo "📊 相比远程的本地未推送变更:"
    git log --oneline "$REMOTE/$BRANCH..HEAD" 2>/dev/null | head -10 || echo "(无)"
    echo "✅ pull 完成"
}

push() {
    echo "🔼 推送本地变更..."
    # 检查是否有未提交变更
    if [[ -z "$(git status --porcelain)" ]]; then
        echo "  没有需要提交的变更"
        exit 0
    fi
    echo ""
    echo "📋 待提交变更:"
    git status --short
    echo ""
    read -rp "提交说明 (留空则自动生成): " msg
    if [[ -z "$msg" ]]; then
        # 自动生成基于变更类的提交说明
        changed=$(git status --short | awk '{print $NF}' | tr '\n' ' ')
        msg="sync: $(date +%Y%m%d-%H%M) — $HOSTNAME"
    fi
    git add -A
    git commit -m "$msg" 2>&1 || echo "⚠️  无变更可提交"
    git push "$REMOTE" "$BRANCH" 2>&1 || {
        echo "⚠️  git push 失败"
        echo "   可能原因: 远程有更新、权限不足"
        echo "   手动处理: git pull --rebase → 重试"
        exit 1
    }
    echo "✅ push 完成"
}

status_check() {
    echo "📊 同步状态:"
    echo "  本地分支: $BRANCH"
    echo "  远程: $REMOTE"
    echo ""
    
    # 本地未提交
    local_unstaged=$(git status --short | wc -l)
    echo "  本地未提交变更: $local_unstaged 个文件"
    if [[ $local_unstaged -gt 0 ]]; then
        git status --short
    fi
    
    echo ""
    # 与远程差异
    ahead=$(git rev-list --count "$REMOTE/$BRANCH..HEAD" 2>/dev/null || echo 0)
    behind=$(git rev-list --count "HEAD..$REMOTE/$BRANCH" 2>/dev/null || echo 0)
    echo "  📤 领先远程: $ahead 个 commit"
    echo "  📥 落后远程: $behind 个 commit"
    
    if [[ $behind -gt 0 ]]; then
        echo "  ⚠️  需要 git pull"
    fi
    if [[ $ahead -gt 0 || $local_unstaged -gt 0 ]]; then
        echo "  ⚠️  需要 git push"
    fi
    if [[ $behind -eq 0 && $ahead -eq 0 && $local_unstaged -eq 0 ]]; then
        echo "  ✅ 完全同步"
    fi
}

case "${1:-menu}" in
    pull)   pull ;;
    push)   push ;;
    status) status_check ;;
    auto)
        pull
        echo ""
        if [[ -n "$(git status --porcelain)" ]]; then
            echo "📋 本地有变更:"
            git status --short
            read -rp "一键 push? [Y/n] " yn
            [[ "$yn" != "n" ]] && push
        else
            echo "✅ 无本地变更，无需 push"
        fi
        ;;
    *)
        echo "用法: ga_sync.sh {pull|push|status|auto}"
        echo ""
        status_check
        echo ""
        echo "推荐工作流:"
        echo "  1️⃣ 开始工作前:  ./ga_sync.sh pull"
        echo "  2️⃣ 完成工作后:  ./ga_sync.sh push"
        echo "  3️⃣ 快速同步:    ./ga_sync.sh auto"
        ;;
esac

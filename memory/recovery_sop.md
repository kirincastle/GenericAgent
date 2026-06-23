---
type: sop
title: "GenericAgent 恢复 SOP — 换电脑/重装 100% 恢复"
tags: ["recovery", "setup", "disaster"]
intent: "在新机器上第一次运行 GA 时，直接说以下任意一句即可启动恢复流程："
---
# GenericAgent 恢复 SOP — 换电脑/重装 100% 恢复

## 触发词
在新机器上第一次运行 GA 时，直接说以下任意一句即可启动恢复流程：
- **"恢复GA"**
- **"新机恢复"**
- **"换电脑了"**

AI 会自动按本 SOP 检查记忆文件完整性、验证配置、报告缺失项。

## 一句话回答

**可以通过 GitHub 恢复大多数内容**，但有 3 样东西需要**手动备份**。

## 恢复清单

### ✅ GitHub 自动恢复（git clone 即可）
- [x] 全部源代码 (`llmcore.py`, `model_registry.py`, tools...)
- [x] 全部 SOP 和技能 (`memory/*.md`, `memory/*.py`) — 包括 L0/L1/L3
- [x] **L2 知识库** (`memory/global_mem.txt`) — 所有项目事实和教训
- [x] **L1 索引** (`memory/global_mem_insight.txt`)
- [x] **neat-freak 技能** (`memory/neat-freak/SKILL.md`)
- [x] **oc2api 部署 SOP** (`memory/oc2api_deploy_sop.md`)
- [x] **CLAUDE.md** （项目指引）
- [x] **模型注册表** (`model_registry.py`)
- [x] 安装脚本 (`assets/ga_install.sh`)

### ⚠️ 需要手动备份（一次性的）
| 项目 | 位置 | 备份方法 | 恢复方法 |
|------|------|----------|----------|
| **API 密钥** | `mykey.py` | 复制到密码管理器/安全云盘 | 新机器 git clone → 手动粘贴 |
| **SSH 密钥** | `~/.ssh/id_*` | `tar czf ~/ga_backup_ssh.tar.gz ~/.ssh/` | 解压到 `~/.ssh/`，`chmod 600` |
| **Tailscale 状态** | `tailscale status` | N/A — 手动登录 | `tailscale up` 重新登录 |

### 🔄 可重新生成（无需备份）
| 项目 | 原因 |
|------|------|
| `model_registry_cache.json` | `python model_registry.py --refresh` 自动下载 |
| `temp/` | 临时运行产物 |
| 浏览器 Cookie/会话 | TMWebDriver 自动重建 |
| Python 虚拟环境 | `pip install .` 或 `uv sync` 重新安装 |

## 完整恢复步骤

### 第一步：机器初始化
```bash
# 基础环境
sudo apt update && sudo apt install -y git python3 python3-pip uv
# 或 macOS: brew install python uv git

# 配置 Git
git config --global user.name "你的名字"
git config --global user.email "你的邮箱"
```

### 第二步：克隆代码
```bash
git clone git@github.com:kirincastle/external.git
cd external/genericagent
```

> 如果用 HTTPS：`git clone https://github.com/kirincastle/external.git`

### 第三步：恢复 API 密钥
```bash
# 从密码管理器获取 mykey.py 内容
# 手动创建文件：
vim mykey.py
```

`mykey.py` 模板参考 `mykey_template.py` 或询问 AI 助手（它会根据 session 记录帮你生成）。

### 第四步：恢复 SSH 密钥（用于 jpkbb 部署）
```bash
# 从备份恢复
tar xzf ~/ga_backup_ssh.tar.gz -C ~/
chmod 600 ~/.ssh/id_*
```

### 第五步：安装依赖
```bash
uv sync
# 或
pip install -e .
```

### 第六步：验证
```bash
# 验证模型注册表
python model_registry.py --check-cfg

# 验证记忆文件完整性
ls memory/global_mem.txt memory/global_mem_insight.txt memory/neat-freak/SKILL.md

# 运行一句测试
./ga_cli/ga-cli-install.cmd  # Windows
# 或
bash assets/ga_install.sh     # Linux/macOS
```

### 第七步：恢复 Tailscale（如需访问 jpkbb）
```bash
tailscale up
# 浏览器登录后确认子网路由
ping 100.127.66.71
```

### 第八步：设置自动 commit+push（每 30 分）
```bash
# 每台机器只需设置一次
crontab -e
# 添加一行（更换路径为你的实际 repo 位置）：
*/30 * * * * /home/moclaw/.local/bin/auto-commit.sh /path/to/genericagent --push
```

`auto-commit.sh` 脚本已在 git 外独立存在（`~/.local/bin/auto-commit.sh`），新机需要：
1. 从旧机复制 or 从密码管理器/云盘获取这个脚本
2. 放到 `~/.local/bin/auto-commit.sh`
3. `chmod +x ~/.local/bin/auto-commit.sh`
4. 添加 crontab 条目

之后每 30 分钟自动 commit+push，无需手动操作。

### 第八步：重建模型缓存
```bash
python model_registry.py --refresh
```

## 一键备份命令（定期执行）
```bash
# 备份不可恢复的敏感文件
cd ~
tar czf ~/ga_backup_$(date +%Y%m%d).tar.gz \
    projects/external/genericagent/mykey.py \
    .ssh/
# 推送到安全位置（加密云盘/密码管理器）
```

## 多机同步工作流 — 保持会话一致 + GA 最新

### 核心原则
- **代码 + 记忆（L1/L2/L3）** → git sync（自动）
- **会话文件（model_responses/*.txt）** → 可选同步（见下方选项）
- **秘密文件（mykey.py, ~/.ssh/）** → 每台机独立放置，不同步

### 推荐工作流（必须）
```bash
# 机器 A — 开始工作前
./ga_sync.sh pull

# 机器 A — 工作完成后
# 先跑 /neat（把学到的东西写入记忆）
./ga_sync.sh push

# 机器 B — 换机器时
./ga_sync.sh pull   # 拿到机器 A 的最新代码 + 记忆
```

### 会话同步（可选）
若你想在机器 B 继续机器 A 未完成的对话（会话连续性），需要同步 `temp/model_responses/`。

**选项 A: 不同步（推荐）**
- 每台机器有自己独立的会话
- 知识通过 neat-freak → L2 记忆蒸馏，跨机共享
- 优点：简单，无冲突

**选项 B: rsync 到 jpkbb（中心服务器）**
```bash
# 机器 A 推送会话
rsync -az temp/model_responses/ root@100.127.66.71:/opt/ga-sessions/

# 机器 B 拉取会话
rsync -az root@100.127.66.71:/opt/ga-sessions/ temp/model_responses/
```

**选项 C: 云盘同步**
```bash
# 将 temp/ 软链到云盘同步目录
ln -sf ~/Dropbox/ga-sessions/ temp/model_responses
# 或
ln -sf ~/GoogleDrive/ga-sessions/ temp/model_responses
```

### 保持 GA 最新
```bash
# 随时检查同步状态
./ga_sync.sh status

# 懒人一键同步（pull + 检查 → 可选 push）
./ga_sync.sh auto
```

### 推荐习惯
1. **每天结束前**：跑 `/neat` → `./ga_sync.sh push`
2. **每天开始时**：`./ga_sync.sh pull`
3. **每周一次**：`./ga_sync.sh auto`
4. **遇到冲突**：`git pull --rebase` 后重试 push

## 变更历史
- **2026-06-18**: 创建。`memory/global_mem.txt` 等关键记忆文件加入 git 跟踪。

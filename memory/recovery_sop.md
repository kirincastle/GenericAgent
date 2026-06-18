# GenericAgent 恢复 SOP — 换电脑/重装 100% 恢复

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

## 恢复后首次对话建议
新机器上第一次运行 GA 时，对 AI 说：
> "我刚换了新电脑，这是 git clone 的全新环境。检查所有记忆文件是否完整，确认 mykey.py 是否正确，然后告诉我缺少什么。"

## 变更历史
- **2026-06-18**: 创建。`memory/global_mem.txt` 等关键记忆文件加入 git 跟踪。

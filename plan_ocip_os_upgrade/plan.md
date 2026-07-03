<!-- EXECUTION PROTOCOL (每轮必读)
1. file_read(plan.md)，找到第一个 [ ] 项
2. 该步标注了SOP → file_read 该SOP的🔑速查段
3. 执行该步骤 + Mini验证产出
4. file_patch 标记 [ ] → [✓]+简要结果，然后回到步骤1继续下一个[ ]
5. 所有步骤（包括验证步骤）标记完成后 → 终止检查：file_read(plan.md)确认0个[ ]残留
⚠ 禁止凭记忆执行 | 禁止跳过验证步骤 | 禁止未经终止检查就结束 | 禁止停下来输出纯文字汇报
💡 搬砖活（读大量代码/文件/网页/重复操作）优先委托subagent，保持主agent上下文干净
-->

# Oracle Cloud VPS OS Upgrade Plan

**需求**：将 17 台 Oracle Cloud VPS 中旧版 OS 的 13 台升级到最新稳定版（Ubuntu 24.04 LTS / Debian 12）。先测试 2 台、总结经验写 SOP，再 subagent 批量 rollout。

**约束**：无统一管理工具 | root SSH 登录（main_vps_key）| Ubuntu 需 2 步（20.04→22.04→24.04）| Debian 直升（11→12）| Docker 生产流量不可中断

## Host Inventory

| Host | IP | OS | Docker Compose Dirs | Containers | Status |
|------|----|----|---------------------|------------|--------|
| amtaa | | Ubuntu 20.04.4 | /root/docker-v2ray-php-nginx-dns01, /root/docker-cloudflared | 5 | ⬆ upgrade |
| amtab | | Ubuntu 20.04.6 | /root/docker-v2ray-php-nginx-dns01 | 6 | ⬆ upgrade |
| amtac | | Ubuntu 20.04.6 | /root/docker-v2ray-php-nginx-dns01 | 5 | ⬆ upgrade |
| jpkaaa | 150.230.193.48 | Ubuntu 20.04.6 | /root/docker-v2ray-php-nginx-dns01, /root/bitwarden | 6+ | ⬆ upgrade |
| jpkab | 158.101.83.250 | Ubuntu 20.04.6 | /root/docker-v2ray-php-nginx-dns01, /root/docker-cloudflared | 6 | ⬆ upgrade |
| jpkac | | Ubuntu 20.04.6 | /root/docker-v2ray-php-nginx-dns01 | 5 | ⬆ upgrade |
| jpkbc | | Ubuntu 20.04.6 | /root/docker-v2ray-php-nginx-dns01 | 5 | ⬆ upgrade |
| krkab | | Ubuntu 20.04.6 | /root/docker-v2ray-php-nginx-dns01, /etc/apt/docker-v2ray-php-nginx-dns01 | 6 | ⬆ upgrade |
| krkac | | Ubuntu 20.04.6 | /root/docker-v2ray-php-nginx-dns01 | 5 | ⬆ upgrade |
| krkad | | Ubuntu 20.04.6 | /root/docker-v2ray-php-nginx-dns01 | 6 | ⬆ upgrade |
| krkca | | Ubuntu 20.04.6 | /root/docker-v2ray-php-nginx-dns01 | 6 | ⬆ upgrade |
| krkcb | | Ubuntu 20.04.6 | /root/docker-v2ray-php-nginx-dns01 | 6 | 🔄 upgrading |
| krkaa | | Debian 11 | /root/docker-v2ray-php-nginx-dns01 | 5 | 🔄 upgrading |
| jpkba | | Ubuntu 24.04.4 | *(none)* | ? | ✅ skip |
| jpkbb | | Ubuntu 24.04.4 | /etc/ssh/docker-v2ray..., /opt/cliproxy, /opt/mimocode2api, /root/codex-console, /root/docker-v2ray..., /root/new-api, /root/rustdesk | 10 | ✅ skip |
| krrea | | Debian 12 | /root/docker-v2ray-php-nginx-dns01 | 5 | ✅ skip |
| krreb | | Debian 12 | /root/docker-v2ray-php-nginx-dns01 | 1 | ✅ skip |

## Phase 0 — Docker Backup & Preflight (新增)

在升级之前，对所有 17 台 VPS 做 Docker compose 数据备份。确保升级失败后可完整恢复 Docker 服务。

1. [✓] **P0-1: 执行 Docker compose 备份脚本 — 所有 17 台 VPS**
   SOP: (无)
   操作：subagent Map 模式 → 17 台并行备份 → 总计 7.5G（jpkab 含 ISO 已清理）→ 用时 57min
   依赖：无
   产出：每台 VPS 的 Docker compose 配置 tar.gz 存档

2. [✓] **P0-2: 拉取备份到本地**
   SOP: (无)
   操作：subagent 自动 SCP 回本地 → 17/17 完成
   依赖：1
   产出：/home/moclaw/backups/ocip/ 共 171M

## Phase 1 — 测试升级（手动，本 session）

3. [✓] **P1-1: Debian 11→12 测试升级 — krkaa** ✅
   SOP: (无)
   操作：subagent 并行部署 → SSH krkaa → apt update && upgrade → 改 sources.list bullseye→bookworm → apt update && upgrade && full-upgrade → autoremove → 重启 → 验证服务正常
   依赖：2
   产出：升级成功/失败记录 + 坑点
   **结果: Debian 11→12 成功. Kernel 5.10→6.1. Docker 8容器正常. Nginx HTTP 200. 3个坑已处理.**

4. [✓] **P1-2: Ubuntu 20.04→22.04→24.04 测试升级 — krkcb** ✅
   SOP: (无)
   操作：subagent 并行部署 → SSH krkcb → `do-release-upgrade -f DistUpgradeViewNonInteractive` 双段自动完成
   依赖：2
   产出：升级成功/失败记录 + 坑点
   **结果: Ubuntu 20.04→24.04 成功. Kernel 5.4→5.15. Docker 6容器正常. Nginx 301 OK. 自动双段升级无人工干预.**

5. [✓] **P1-3: 编写升级 SOP** ✅
   SOP: lessons_sop.md
   操作：已写完 6420 bytes，含步骤/坑点/health check/rollback/dispatch 章节 `ocip_os_upgrade_sop.md`
   依赖：3, 4
   产出：/home/moclaw/projects/external/genericagent/memory/ocip_os_upgrade_sop.md
## Phase 2 — 批量执行（subagent）

6. [D] **P2-1: Ubuntu 20.04 批量升级（subagent Map 模式）**
   SOP: subagent.md, ocip_os_upgrade_sop.md
   说明：krkaa(Debian) 已处理。剩余 11 台 Ubuntu 20.04: amtaa, amtab, amtac, jpkaaa, jpkab, jpkac, jpkbc, krkab, krkac, krkad, krkca
   操作：用 subagent Map 模式分发升级 SOP 执行。每台执行 20.04→22.04→24.04
   依赖：5
   产出：每台升级结果日志

## Phase 3 — 验证

7. [ ] **P3-1: 验证所有已升级 VPS**
   SOP: verify_sop.md
   操作：SSH 每台已升级 VPS → lsb_release -a → 关键服务运行状态 → disk 余量 → docker ps 状态
   依赖：6
   产出：验证报告

8. [ ] **P3-2: 记录 lessons & handoff 结算**
   SOP: lessons_sop.md
   操作：更新 L2 global_mem.txt 记录升级后 OS 版本 | 创建 handoff | 运行 /neat 清理
   依赖：7
   产出：handoff 记录

## 验证检查点

9. [ ] **[VERIFY] 启动独立验证 subagent**
   SOP: verify_sop.md plan_sop.md
   操作：读 plan_sop.md 第四章 → 准备 verify_context.json → 启动验证 subagent → 读取 VERDICT
   ⚠ 不可跳过

---
type: handoff
title: "Session Handoff — 2026-06-19 (codegraph + migration-dashboard + oc2api)"
date: "2026-06-19"
status: "done"
tags: [codegraph, migration-dashboard, oc2api, hive]
---
# Session Handoff — 2026-06-19

## 本次完成

### 1. codegraph 取代 graphify
- **决策**: 禁用 graphify，只用 codegraph（FTS5 全文搜索 + 调用链追踪，无需隔夜索引）
- **动作**:
  - `ga.py` 修好 tool 路径（mccg/2go-mccg 指向 ssh/ping）
  - 删除 mccg/2go-mccg 的 graphify-out
  - agentmain.py：graphify → codegraph 参数重映射
  - codegraph_db.py：支持多个项目共用同一个 .codegraph 目录

### 2. migration-dashboard 移植（Hive Master 执行）
- **项目**: `/home/moclaw/projects/migration-dashboard`
- **目标**: 从 mccg 移植 5 个功能到 migration-dashboard 的 tools/
- **执行**: agentmain.py --reflect + goal_mode.py + goal_hive_sop（~2h Master + workers）
- **14 个提交**（hive-master + hive-worker，但 git author 显示 Ethan Wu）
- **10 个文件改动**，141 行新增

#### 5 Issues 完成情况
| Issue | 功能 | 涉及文件 |
|:------|:-----|:---------|
| ① | Vendor FortiGate/PaloAlto | `models.go` + `backup.go` |
| ② | SSH Shell mode + PTY | `ssh.go` + `RunShellCommands` |
| ③ | Stale session 5-min timeout | `customcli.go` |
| ④ | SSE 流式输出 | `customcli_stream.go` + `web/server.go` |
| ⑤ | Device-level 命令 | `customcli.go` + `getDeviceCommands` |

- **验证**: VERIFICATION_v1~v4.md, FINAL_DELIVERY.md 已生成
- **测试**: `tools/backup_test.go` 新增（未跟踪）

### 3. oc2api + xray + worker.js 节点手动更新方案
- **项目**: `/home/moclaw/projects/oc2api` + `/home/moclaw/projects/edge_tunnel`
- **架构**: CF Worker(worker.js) → KV(config.json) → oc2api(:8000) → xray SOCKS5
- **发现**: worker.js **无自动定时刷新**，纯 request-driven
  - `/sub` 每次实时读 KV 生成节点
  - `SUBUpdateTime:3` 只是 Clash header，非 worker 定时器
- **现有 rotate 链路**: rotateXrayProxy() → sync-sub.py → xray 重启 → syncSocks5FromXrayConfig()
- **缺失**: rotate 前需 `POST admin/config.json` 改 worker 配置
- **状态**: 待实现（用户要求先别写代码）

### 4. Hive 框架知识沉淀
- `/home/moclaw/projects/external/genericagent` Hive 框架已稳定
- goal_mode.py 支持 24h budget, wake-check-continue 循环
- BBS (:9101) Master-Worker 通讯
- Master idle loop 行为已知

## 未处理 / 待办

### 高优先级
1. **oc2api 手动节点更新** — 实现 oc2api → `POST admin/config.json` → 触发生效（用户明确说要搞）
2. **Hive Master 仍在 idle loop** — 已 kill（PID 336788 + BBS 336314）

### 低优先级
- master.log 558KB 含完整执行记录
- backup_test.go 未提交

## 项目路径速查

| 项目 | 路径 |
|:-----|:-----|
| GenericAgent | `/home/moclaw/projects/external/genericagent` |
| migration-dashboard | `/home/moclaw/projects/migration-dashboard` |
| oc2api | `/home/moclaw/projects/oc2api` |
| edge_tunnel (worker.js) | `/home/moclaw/projects/edge_tunnel` |

## Suggested Skills
- `/okf-frontmatter` — 维护 docs 用
- `/codebase-design` — 如需重构 oc2api proxy 模块
- `/tdd` — 如需为 migration-dashboard 新功能写测试
- `/handoff` — 下轮继续时用

# Session Handoff — 2026-06-18

## 本次完成

### 1. probeModelStatus 优化
- **问题**: 每 10min 探测全部模型（含 paid）→ 浪费请求 + 日志噪音
- **Fix**: 只探测名字含 "free" 或 "big-pickle" 的模型；也只透传这些 free 模型到下游
- **部署**: v3.024（oc2api），编译→rsync→systemd 生产部署

### 2. GUI 加载问题诊断（学习记录）
- **症状**: v3.024 部署后管理面板大量 "加载中"
- **误诊**: 怀疑 JS 语法问题（window.onload 末尾 `({})`）
- **根因**: 后端服务刚重启，模型探测/代理健康尚未完成第一轮循环
- **教训**: GUI "加载中" → 先检查后端服务状态，非 JS 语法问题

### 3. Cache Hit 0% 深度调查
- 确认 goal mode/reflect 模式调用全部 cached=0（554/554）
- 根因: 不同 LLM 配置下 cache 不共享，非本次可解

### 4. Neat-freak 知识清理（本轮）
- oc2api docs: 新建 handoff-2026-06-18.md，更新 CLAUDE.md（行号 + 文档引用），更新 architecture.md（prob 细节）
- GenericAgent: 更新 handoff.md、global_mem.txt（L2）、global_mem_insight.txt（L1）

## 未处理 / 待办

### Cache Hit 跨 LLM 不共享
- goal mode / agentmain 使用不同 LLM 实例 → cache 隔离
- 非本次 scope，需架构级改动

## 新 Session 快速恢复
```
L1: global_mem_insight.txt → 技能索引
L2: global_mem.txt → 稳定事实 (+ probeModelStatus, GUI Lesson)
docs/handoff.md → 本文件（会话记录 + 待办）
```

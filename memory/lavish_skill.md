---
type: sop
title: "Lavish Skill — HTML 产物协作编辑"
tags: ["skill", "html", "editor"]
intent: "agent 生成了复杂的 HTML 产物，需要精确反馈（框选元素/选中文本）。"
---
# Lavish Skill — HTML 产物协作编辑

## 何时使用

agent 生成了复杂的 HTML 产物，需要精确反馈（框选元素/选中文本）。

## 用法

```bash
# 启动 lavish 编辑你的 HTML 文件
npx lavish-axi your-artifact.html

# 在浏览器中：
# - 框选元素 → 生成精准反馈
# - 选中文本 → 给出修改意见
# 反馈自动结构化发给 agent
```

## 原理

- 纯本地，零云端依赖
- AXI 格式（Agent-executable Interface）：一种 agent 可执行的文件注释协议
- 浏览器中的选择/框选被转换为 agent 可理解的指令

## 本系统整合

- 当 agent 产出 HTML 且需要精细化调整时，在回复中提示用户 `npx lavish-axi <path>`

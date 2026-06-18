---
type: readme
title: "GenericAgent — Project Guide for AI"
tags: [genericagent]
intent: "Project overview and usage guide"
---
# GenericAgent — Project Guide for AI

## Overview

GenericAgent (GA) — self-evolving autonomous agent framework. ~3K lines seed code, 9 atomic tools, ~100-line agent loop.

## Project Structure

| Path | Purpose |
|------|---------|
| `ga.py` | Agent loop entry point |
| `agent_loop.py` | Core ~100-line agent loop |
| `agentmain.py` | Agent main process, orchestration |
| `llmcore.py` | LLM core interaction |
| `memory/` | **Agent skill library** — auto-loaded by `get_global_memory()`. Contains SOPs, skills, integrations |
| `frontends/` | UI frontends (TUI v3, Streamlit, Telegram, Discord, Lark) |
| `docs/` | Installation & setup guides for humans |
| `temp/` | Runtime working directory |
| `reflect/` | Reflection/watchdog modules |
| `plugins/` | Plugin system |
| `tools/` | Additional tools |
| `ga_cli/` | CLI interface |

## Git Workflow

- **Branch**: `rtk-integration` (long-term working branch)
- **Main**: stable/release merges only
- **Remotes**:
  - `origin` → `git@github.com:kirincastle/GenericAgent.git` (personal fork, SSH)
  - `upstream` → `https://github.com/Lsdefine/GenericAgent.git`
- **Rule**: all changes on `rtk-integration`, push to own fork

## Key Commands

| Command | Description |
|---------|-------------|
| `python ga.py` | Run agent |
| `python frontends/tui_v3.py` | TUI frontend |
| `python launch.pyw` | Streamlit UI |
| `python frontends/tgapp.py` | Telegram bot |
| `python frontends/dcapp.py` | Discord bot |
| `python frontends/fsapp.py` | Lark/Feishu bot |
| `agentmain --reflect` | Watchdog/reflect mode |
| `python -m memory.<module>` | Run memory module directly |

## System Prompt Architecture

The system prompt is built by `ga.py` → `get_global_memory()`:
1. **L1 Insight** (`memory/global_mem_insight.txt`) — minimal index, always injected
2. **L2 Facts** (`memory/global_mem.txt`) — stable project facts, always injected
3. **L3 SOPs/Skills** (files in `memory/`) — loaded by pattern, injected only when relevant
4. **Skill search** (`memory/skill_search`) — mechanism for dynamic skill discovery

## Deep-Doc Pointers

| Topic | Location | Audience |
|-------|----------|----------|
| Architecture & Layered Memory | README.md §Architecture | Human + AI |
| Self-evolution mechanism | README.md §Self-Evolution | Human + AI |
| Agent red lines / behavioral rules | `memory/global_mem_insight.txt` [RULES] | AI |
| GUI automation (computer use) | `memory/computer_use.md` + `docs/computer-usage.md` | AI (detail) + Human (overview) |
| Keyboard/mouse control | `memory/ljqCtrl_sop.md`, `memory/ljqCtrl.py` | AI |
| Memory management | `memory/memory_management_sop.md` | AI |
| Memory cleanup (neat-freak) | `memory/neat-freak/SKILL.md` | AI |
| Vision / OCR | `memory/vision_sop`, `memory/ocr_utils.py` | AI |
| Web automation | `memory/web_setup_sop`, `memory/tmwebdriver_sop` | AI |
| Autonomous operation | `memory/autonomous_operation_sop.md` | AI |
| Task scheduling | `memory/scheduled_task_sop.md` | AI |
| Planning | `memory/plan_sop.md` | AI |
| UI detection | `memory/ui_detect.py` | AI |
| Mobile automation | `memory/adb_ui.py` | AI |
| RTK token processing | `memory/rtk_integration.py`, `memory/rtk_tool.py` | AI |
| Response compression (caveman) | `memory/caveman/SKILL.md` | AI |
| Matt Pocock engineering skills | `memory/mattpocock_integration.py` (index + on-demand), `../temp/.agents/skills/` (18 skills) | AI |
| Subagent coordination | `memory/subagent.md` | AI |
| Installation (EN) | `docs/installation.md` | Human |
| Installation (ZH) | `docs/installation_zh.md` | Human |
| macOS desktop install | `docs/macos_desktop_installation_zh.md` | Human |
| Getting started | `docs/GETTING_STARTED.md` | Human |
| Feishu/Lark setup | `docs/SETUP_FEISHU.md` | Human |
| Session history / handoff | `docs/handoff.md` | Human + AI |

## Red Lines

- **Never** `kill` python unconditionally — may kill self. Use exact PID.
- **No** pyautogui — use `ljqCtrl` for keyboard/mouse.
- **No** fullscreen capture — prefer window capture.
- **No** duckduckgo — always Google for web search.
- **No** file path guessing — use `es` for filename search, check `cwd` first.
- **Never** assert without evidence — cross-verify numbers on detail pages.
- Key/secret files: reference only, never read or move.
- Encoding: use `file_read`, not PS `cat`/`type`.
- Processes: never `os.kill` for liveness check.
- Windows: prefer `win32gui` title enumeration for GUI state.

## Coding Conventions

- Python, PEP 8.
- Import memory modules directly (in PATH, no fake prefixes).
- Memory files: `.md` for SOPs, `.py` for executable modules.
- Git: `rtk-integration` branch, commit with meaningful messages.

## Environment

- Python 3.x, dependencies in `pyproject.toml`.
- Key config: `mykey.py` (template: `mykey_template.py` / `mykey_template_en.py`).
- Chrome extension for web automation (bundled).

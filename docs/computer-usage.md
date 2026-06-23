---
type: reference
title: "Computer Usage — GUI Automation Overview"
tags: [genericagent, documentation]
intent: "Technical reference document"
schema_source: okf
---
# Computer Usage — GUI Automation Overview

GenericAgent can interact with GUI applications on Windows, macOS, and Linux through a layered automation pipeline. This document describes the capability at a high level; detailed agent instructions live in `memory/computer_use.md`.

## Automation Pipeline

```
Human request → Agent reasoning → Tool selection → OS-level GUI control → Result
```

The agent uses OS-native accessibility APIs and input simulation, not computer vision or image recognition.

### Detection / Location Tools

| Tool | Purpose |
|------|---------|
| **Window enumeration** (win32gui / macOS Accessibility API) | Locate target windows by title, class, geometry |
| **UI Automation tree** (UIA on Windows, AX on macOS) | Navigate control tree for precise interaction |
| **Coordinate-based fallback** | Physical pixel coordinates when control tree unavailable |
| **OCR** (RapidOCR-based) | Read text from screen regions |

### Interaction Tools

| Action | Method |
|--------|--------|
| Click | Control tree activation (preferred) or physical coordinate click |
| Keyboard input | Per-character simulation via OS APIs |
| Screenshot | Window capture (not fullscreen) |

## Platform Support

| Platform | Primary API | Fallback |
|----------|-------------|----------|
| Windows | UIA (UI Automation) | win32gui + SendInput |
| macOS | Accessibility API (AX) | CGEvent + AX |
| Linux | X11/Sway | - |

## Setup

The agent can self-configure by being told: *"Probe this system and set up your computer-use capability."*

It will detect the OS, install dependencies (`pywin32`, `pyobjc`, etc.), and persist the configuration to memory.

## Dependencies

- **Windows**: `pywin32`, `comtypes` (for UIA)
- **macOS**: `pyobjc-framework-ApplicationServices`, `pyobjc-framework-Quartz`
- **Linux**: `python-xlib` (X11) or `i3ipc` (Sway)

## See Also

- [Agent instructions (detailed)](../memory/computer_use.md) — full SOP with tool tables, timing rules, and platform-specific commands
- [Keyboard/mouse control SOP](../memory/ljqCtrl_sop.md)
- [UI detection module](../memory/ui_detect.py)
- [OCR utilities](../memory/ocr_utils.py)
- [Vision SOP](../memory/vision_sop.md)

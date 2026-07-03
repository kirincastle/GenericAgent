#!/usr/bin/env python3
"""
GA session → agent-session-search (Codex JSONL) converter.

Reads GA's model_responses_*.txt files from temp/model_responses/
and writes Codex-format JSONL files to ~/.codex/sessions/ga_import/
so agent-session-search can index them like native Codex sessions.
"""

import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

GA_TEMP = Path(os.environ.get("GA_TEMP", "/home/moclaw/projects/external/genericagent/temp"))
SRC_DIR = GA_TEMP / "model_responses"
NAMES_FILE = SRC_DIR / "session_names.json"
OUT_DIR = Path(os.environ.get("GA_SESSION_OUT", str(GA_TEMP / "session_search")))

# Regex patterns
PROMPT_RE = re.compile(r"^=== Prompt === (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s*$")
RESPONSE_RE = re.compile(
    r"^=== Response === (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) model=(\S+)\s*$"
)

def parse_timestamp(ts_str: str) -> str:
    """Convert '2026-06-23 17:07:06' to ISO format."""
    dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
    return dt.replace(tzinfo=timezone.utc).isoformat()


def parse_ga_file(filepath: Path):
    """
    Parse a GA model_responses_*.txt file.
    Yields (type, timestamp, model, content_json) tuples.
    type is 'Prompt' or 'Response'.
    """
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\n")
        pm = PROMPT_RE.match(line)
        if pm:
            ts = pm.group(1)
            i += 1
            # Collect JSON body (may be multi-line)
            body_lines = []
            while i < len(lines) and not PROMPT_RE.match(lines[i]) and not RESPONSE_RE.match(lines[i]):
                body_lines.append(lines[i])
                i += 1
            body = "".join(body_lines).strip()
            yield ("Prompt", ts, None, body)
            continue

        rm = RESPONSE_RE.match(line)
        if rm:
            ts = rm.group(1)
            model = rm.group(2)
            i += 1
            # Collect JSON body (may be multi-line)
            body_lines = []
            while i < len(lines) and not PROMPT_RE.match(lines[i]) and not RESPONSE_RE.match(lines[i]):
                body_lines.append(lines[i])
                i += 1
            body = "".join(body_lines).strip()
            yield ("Response", ts, model, body)
            continue

        i += 1


def extract_text(content_items):
    """Extract text content from a GA content items array."""
    texts = []
    if isinstance(content_items, list):
        for item in content_items:
            if isinstance(item, dict):
                t = item.get("type", "")
                if t == "text" and item.get("text"):
                    texts.append(item["text"])
                elif t == "thinking":
                    texts.append(f"[thinking] {item.get('thinking', '')}")
                elif t == "tool_use":
                    texts.append(f"[tool_use: {item.get('name', '')}] {json.dumps(item.get('input', {}), ensure_ascii=False)}")
                elif t == "tool_result":
                    txt = item.get("content", "")
                    if isinstance(txt, list):
                        txt = " ".join(
                            t.get("text", "") if isinstance(t, dict) else str(t)
                            for t in txt
                        )
                    texts.append(f"[tool_result] {txt}")
                elif t == "input_text":
                    texts.append(item.get("text", ""))
                elif t == "input_text" and isinstance(item.get("text"), str):
                    texts.append(item["text"])
    return "\n".join(texts)


def parse_prompt_body(body_str: str):
    """Parse a Prompt JSON body. Returns role, content list."""
    try:
        data = json.loads(body_str)
    except json.JSONDecodeError:
        return "user", [{"type": "input_text", "text": body_str}]

    role = data.get("role", "user")
    content = data.get("content", [])
    # Convert GA content types to Codex types
    mapped = []
    for item in content if isinstance(content, list) else [{"type": "text", "text": str(content)}]:
        if not isinstance(item, dict):
            item = {"type": "text", "text": str(item)}
        t = item.get("type", "text")
        text = item.get("text") or item.get("content") or ""
        if t == "tool_result":
            tool_content = item.get("content", "")
            if isinstance(tool_content, list):
                text = " ".join(c.get("text", "") if isinstance(c, dict) else str(c) for c in tool_content)
            else:
                text = str(tool_content) if tool_content else ""
            mapped.append({"type": "tool_result", "text": text, "tool_use_id": item.get("tool_use_id", "")})
        elif t == "text":
            mapped.append({"type": "input_text", "text": text})
        else:
            mapped.append({"type": "input_text", "text": str(item)})
    return role, mapped


def parse_response_body(body_str: str):
    """Parse a Response JSON array body. Returns role, content list."""
    try:
        data = json.loads(body_str)
    except json.JSONDecodeError:
        return "assistant", [{"type": "text", "text": body_str}]

    if not isinstance(data, list):
        return "assistant", [{"type": "text", "text": body_str}]

    mapped = []
    for item in data:
        if not isinstance(item, dict):
            mapped.append({"type": "text", "text": str(item)})
            continue
        t = item.get("type", "text")
        if t == "thinking":
            mapped.append({"type": "thinking", "thinking": item.get("thinking", "")})
        elif t == "text":
            mapped.append({"type": "text", "text": item.get("text", "")})
        elif t == "tool_use":
            mapped.append({
                "type": "tool_use",
                "name": item.get("name", ""),
                "input": item.get("input", {}),
                "id": item.get("id", ""),
            })
        elif t == "tool_result":
            tc = item.get("content", "")
            if isinstance(tc, list):
                tc = " ".join(c.get("text", "") if isinstance(c, dict) else str(c) for c in tc)
            mapped.append({"type": "tool_result", "content": str(tc)})
        else:
            mapped.append(item)
    return "assistant", mapped


def ga_file_to_codex_jsonl(filepath: Path, session_name: str = None):
    """
    Convert a single GA file to Codex JSONL records.
    Yields JSON strings (one per line).
    """
    session_id = str(uuid.uuid4())
    filename = filepath.name
    # Extract numeric id from filename
    m = re.search(r"model_responses_(\d+)\.txt", filename)
    numeric_id = m.group(1) if m else session_id[:8]

    created_iso = datetime.now(timezone.utc).isoformat()

    # session_meta
    meta = {
        "type": "session_meta",
        "timestamp": created_iso,
        "payload": {
            "session_id": session_id,
            "id": session_id,
            "created_at": created_iso,
            "cwd": str(GA_TEMP),
            "originator": "genericagent",
            "cli_version": "1.0.0",
            "source": "cli",
            "thread_source": "user",
            "model_provider": "genericagent",
            "title": session_name or f"GA-{numeric_id}",
        }
    }
    yield json.dumps(meta, ensure_ascii=False)

    entries = list(parse_ga_file(filepath))
    turn_counter = 0

    for entry_type, ts, model, body in entries:
        timestamp_iso = parse_timestamp(ts) if ts else created_iso
        event_ts = parse_timestamp(ts) if ts else created_iso

        if entry_type == "Prompt":
            role, content = parse_prompt_body(body)
            # event_msg for user message
            text_preview = extract_text(content)[:200] if content else ""
            evt = {
                "type": "event_msg",
                "timestamp": event_ts,
                "payload": {
                    "type": "user_message",
                    "message": text_preview,
                    "images": [],
                    "text_elements": []
                }
            }
            yield json.dumps(evt, ensure_ascii=False)

            # response_item for the actual message
            item = {
                "type": "response_item",
                "timestamp": timestamp_iso,
                "payload": {
                    "type": "message",
                    "role": role,
                    "content": content,
                }
            }
            yield json.dumps(item, ensure_ascii=False)

        elif entry_type == "Response":
            role, content = parse_response_body(body)

            # event_msg for agent reasoning (if thinking exists)
            thinking_text = ""
            for c in content if isinstance(content, list) else []:
                if isinstance(c, dict) and c.get("type") == "thinking":
                    thinking_text = c.get("thinking", "")
                    break
            if thinking_text:
                evt = {
                    "type": "event_msg",
                    "timestamp": event_ts,
                    "payload": {
                        "type": "agent_reasoning",
                        "text": thinking_text
                    }
                }
                yield json.dumps(evt, ensure_ascii=False)

            # response_item for the actual response
            # Filter out thinking items for the message content
            msg_content = [c for c in content if isinstance(c, dict) and c.get("type") != "thinking"]

            # If there's text content, emit as assistant message
            if msg_content:
                item = {
                    "type": "response_item",
                    "timestamp": timestamp_iso,
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": msg_content,
                        "model": model,
                    }
                }
                yield json.dumps(item, ensure_ascii=False)

            turn_counter += 1


def main():
    # Load session names
    names = {}
    if NAMES_FILE.exists():
        try:
            names = json.loads(NAMES_FILE.read_text(encoding="utf-8"))
        except Exception:
            names = {}

    # Find all GA session files
    files = sorted(SRC_DIR.glob("model_responses_*.txt"))
    if not files:
        print(f"No session files found in {SRC_DIR}")
        sys.exit(1)

    # Ensure output directory
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    converted = 0
    errors = 0

    for fpath in files:
        session_name = names.get(fpath.name)
        out_name = fpath.stem + ".jsonl"
        out_path = OUT_DIR / out_name

        # Skip if already converted (check if output exists with same size or newer)
        if out_path.exists():
            # Quick size check: if output is > 100 bytes, skip
            if out_path.stat().st_size > 100:
                print(f"  SKIP  {fpath.name} (already converted)")
                continue

        try:
            records = list(ga_file_to_codex_jsonl(fpath, session_name))
            with open(out_path, "w", encoding="utf-8") as f:
                f.write("\n".join(records) + "\n")
            converted += 1
            print(f"  OK    {fpath.name} → {out_name} ({len(records)} records)")
        except Exception as e:
            errors += 1
            print(f"  FAIL  {fpath.name}: {e}", file=sys.stderr)

    print(f"\nDone. {converted} converted, {errors} errors, output in {OUT_DIR}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
GA-ACP Adapter — bridges GenericAgent to OpenAB via ACP stdio JSON-RPC.
"""

import sys
import json
import os
import threading
import uuid
import traceback

GA_DIR = os.path.dirname(os.path.abspath(__file__))
if GA_DIR not in sys.path:
    sys.path.insert(0, GA_DIR)
os.chdir(GA_DIR)

from agentmain import GenericAgent

agent = GenericAgent()
_selected_llm = False


def init_agent():
    global _selected_llm
    if _selected_llm:
        return
    try:
        agent.next_llm(0)
    except Exception as e:
        sys.stderr.write(f"[ga-acp] WARN next_llm: {e}\n")
    agent.verbose = False
    agent.inc_out = True
    agent.peer_hint = False
    t = threading.Thread(target=agent.run, daemon=True)
    t.start()
    _selected_llm = True
    sys.stderr.write("[ga-acp] GA runner started\n")
    sys.stderr.flush()


init_agent()

_current_task = {"active": False, "req_id": None}
_lock = threading.Lock()


def _write_json(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def handle(req):
    method = req.get("method", "")
    rid = req.get("id")
    params = req.get("params", {})

    # ── initialize ────────────────────────────────────────────────────
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": rid,
            "result": {
                "protocolVersion": "2025-01-01",
                "capabilities": {
                    "streaming": True,
                    "cancellation": True,
                },
                "serverInfo": {"name": "ga-acp", "version": "0.1.0"},
            },
        }

    # ── session/new ───────────────────────────────────────────────────
    if method == "session/new":
        return {
            "jsonrpc": "2.0",
            "id": rid,
            "result": {"sessionId": params.get("id", "default"), "status": "created"},
        }

    # ── session/close ─────────────────────────────────────────────────
    if method == "session/close":
        return {
            "jsonrpc": "2.0",
            "id": rid,
            "result": {"sessionId": params.get("id", "default"), "status": "closed"},
        }

    # ── session/prompt ────────────────────────────────────────────────
    if method == "session/prompt":
        prompt_blocks = params.get("prompt", [])
        message = ""
        for block in prompt_blocks:
            if isinstance(block, dict) and block.get("type") == "text":
                message += block.get("text", "")
        session_id = params.get("sessionId", "default")

        # Run prompt in background thread
        t = threading.Thread(
            target=_run_prompt, args=(rid, session_id, message), daemon=True
        )
        t.start()

        # Return immediately — OpenAB expects streaming via notifications
        return {
            "jsonrpc": "2.0",
            "id": rid,
            "result": {"sessionId": session_id, "status": "streaming"},
        }

    # ── cancel ────────────────────────────────────────────────────────
    if method in ("tasks/cancel", "session/cancel", "cancel"):
        with _lock:
            if _current_task["active"]:
                agent.abort()
        return {"jsonrpc": "2.0", "id": rid, "result": {"status": "cancelled"}}

    # ── shutdown / exit ───────────────────────────────────────────────
    if method in ("shutdown", "exit"):
        _write_json({"jsonrpc": "2.0", "id": rid, "result": {"status": "shutting_down"}})
        sys.exit(0)

    return {
        "jsonrpc": "2.0",
        "id": rid,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def _run_prompt(rid, session_id, message):
    """Run GA prompt in background, stream via tasks/output, send final JSON-RPC response with stopReason."""
    dq = agent.put_task(message, source="acp")
    with _lock:
        _current_task["active"] = True
        _current_task["req_id"] = rid

    full = ""
    try:
        while True:
            item = dq.get()
            if agent.stop_sig:
                break

            if "next" in item:
                chunk = item["next"]
                full += chunk
                _write_json({
                    "jsonrpc": "2.0",
                    "method": "tasks/output",
                    "params": {
                        "id": rid,
                        "sessionId": session_id,
                        "content": [{"type": "text", "text": chunk}],
                        "status": "running",
                    },
                })

            if "done" in item:
                full = item["done"]
                # Send final notification with full content
                _write_json({
                    "jsonrpc": "2.0",
                    "method": "tasks/output",
                    "params": {
                        "id": rid,
                        "sessionId": session_id,
                        "content": [{"type": "text", "text": full}],
                        "status": "completed",
                    },
                })
                break
    except Exception as e:
        sys.stderr.write(f"[ga-acp] prompt error: {e}\n")
        sys.stderr.flush()
    finally:
        with _lock:
            _current_task["active"] = False

    # Send the final response (this has id = rid, so OpenAB resolves the pending request)
    _write_json({
        "jsonrpc": "2.0",
        "id": rid,
        "result": {
            "sessionId": session_id,
            "stopReason": "end_turn",
            "usage": {
                "inputTokens": 0,
                "outputTokens": len(full),
                "totalTokens": 0,
            },
        },
    })


def main():
    if "--test" in sys.argv:
        idx = sys.argv.index("--test")
        if idx + 1 < len(sys.argv):
            prompt = sys.argv[idx + 1]
            sys.stderr.write(f"[ga-acp] TEST: {prompt}\n")
            dq = agent.put_task(prompt, source="test")
            while True:
                item = dq.get()
                if "next" in item:
                    print(item["next"], end="", flush=True)
                if "done" in item:
                    print()
                    break
            return

    sys.stderr.write("[ga-acp] Adapter ready, listening on stdin...\n")
    sys.stderr.flush()

    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle(req)
            if resp:
                _write_json(resp)
        except json.JSONDecodeError as e:
            _write_json({
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": f"Parse error: {e}"},
            })
        except Exception as e:
            sys.stderr.write(f"[ga-acp] ERROR {traceback.format_exc()}\n")
            sys.stderr.flush()


if __name__ == "__main__":
    main()

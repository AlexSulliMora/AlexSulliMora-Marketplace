#!/usr/bin/env python3
"""PostToolUse hook for Agent and SendMessage tools.

Writes one entry per dispatch to <cwd>/coauthor/audit/<worker>.md and a
reference line in the open turn of coauthor.md. Stdlib only. Silent if
<cwd>/coauthor/ is absent or the captured tool is not Agent/SendMessage.

Tool-name note: the documented sub-agent dispatch tool is `Agent` (per
https://code.claude.com/docs/en/hooks). Documented Agent tool_input fields
are `prompt`, `description`, `subagent_type`, `model`. SendMessage is not in
the public hooks doc; field guesses (`to`, `agent_id`, `message`) may need
adjusting. When the worker name can't be resolved we dump the full event to
`<audit>/.unknown-event-<ts>.json` so real payloads can be inspected.

Concurrency note: each append is built as a single string and written with
one `f.write(block)` call; this avoids interleaving when multiple Agent
dispatches finish concurrently. No fcntl/flock.
"""

from __future__ import annotations

import hashlib
import json as _json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_common import (  # noqa: E402
    audit_dir,
    now_iso,
    read_event,
    sanitize_worker,
)


CAPTURED_TOOLS = {"Agent", "SendMessage"}


def resolve_worker(tool_name: str, tool_input: dict, prompt_or_msg: str) -> tuple[str, bool]:
    """Return (worker_name, resolved). `resolved=False` => fell through to hash."""
    if tool_name == "Agent":
        # Documented field is `subagent_type`. `name` retained as a defensive
        # fallback in case a custom Agent variant exposes a friendly name.
        candidate = tool_input.get("subagent_type") or tool_input.get("name")
    elif tool_name == "SendMessage":
        candidate = tool_input.get("to") or tool_input.get("agent_id")
    else:
        candidate = None
    safe = sanitize_worker(candidate or "")
    if safe:
        return safe, True
    h = hashlib.sha1((prompt_or_msg or "").encode("utf-8")).hexdigest()[:8]
    return f"unnamed-{h}", False


def main() -> int:
    event = read_event()
    tool_name = event.get("tool_name", "")
    if tool_name not in CAPTURED_TOOLS:
        return 0
    audit = audit_dir(event)
    if audit is None:
        return 0

    tool_input = event.get("tool_input") or {}
    tool_result = event.get("tool_result") or {}

    if tool_name == "Agent":
        prompt = tool_input.get("prompt") or tool_input.get("description") or ""
    else:
        prompt = tool_input.get("message") or tool_input.get("prompt") or ""

    if isinstance(tool_result, dict):
        response = (
            tool_result.get("response")
            or tool_result.get("output")
            or tool_result.get("result")
            or ""
        )
        agent_id = tool_result.get("agent_id") or ""
    else:
        response = str(tool_result)
        agent_id = ""

    if not isinstance(response, str):
        response = _json.dumps(response, indent=2)

    worker, resolved = resolve_worker(tool_name, tool_input, prompt)
    ts = now_iso()
    session_id = event.get("session_id", "")

    if not resolved:
        # Couldn't pull a name from documented or guessed fields. Drop the
        # whole event so the user can see what keys the build actually emits.
        try:
            ts_safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", ts)
            dbg_path = audit / f".unknown-event-{ts_safe}.json"
            dbg_path.write_text(_json.dumps(event, indent=2, default=str), encoding="utf-8")
        except Exception:
            pass

    entry = (
        f"\n## {ts}\n\n"
        f"**Tool**: {tool_name}\n"
        f"**Session**: {session_id}\n"
        f"**Agent ID**: {agent_id}\n\n"
        f"### Prompt\n\n"
        f"{prompt.rstrip() if isinstance(prompt, str) else prompt}\n\n"
        f"### Response\n\n"
        f"{response.rstrip()}\n\n"
        f"---\n"
    )

    # Single open + single write to avoid interleaving with concurrent
    # dispatches finishing at the same time.
    worker_file = audit / f"{worker}.md"
    with worker_file.open("a", encoding="utf-8") as f:
        f.write(entry)

    coauthor_md = audit / "coauthor.md"
    if coauthor_md.exists():
        ref_block = f"- Called `{worker}` at {ts}\n"
        with coauthor_md.open("a", encoding="utf-8") as f:
            f.write(ref_block)
    return 0


if __name__ == "__main__":
    sys.exit(main())

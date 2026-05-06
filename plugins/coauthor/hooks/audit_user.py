#!/usr/bin/env python3
"""UserPromptSubmit hook: open a new turn block in coauthor.md.

Stdlib only. Silent (exit 0) if <cwd>/coauthor/ does not exist.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_common import NO_STAGE, audit_dir, now_iso, read_event  # noqa: E402


STAGE_COMMANDS = {"/scope", "/plan", "/work", "/review", "/finalize"}


def detect_stage(prompt: str, prior_stage: str) -> str:
    stripped = (prompt or "").lstrip()
    first = stripped.split(None, 1)[0] if stripped else ""
    if first in STAGE_COMMANDS:
        return first[1:]
    return prior_stage or NO_STAGE


def main() -> int:
    event = read_event()
    audit = audit_dir(event)
    if audit is None:
        return 0

    prompt = event.get("user_prompt") or event.get("prompt") or ""

    stage_file = audit / ".stage"
    prior = stage_file.read_text(encoding="utf-8").strip() if stage_file.exists() else NO_STAGE
    stage = detect_stage(prompt, prior)
    stage_file.write_text(stage + "\n", encoding="utf-8")

    block = (
        f"\n## Turn {now_iso()}\n"
        f"**Stage**: {stage}\n\n"
        f"### User\n\n"
        f"{prompt.rstrip()}\n\n"
        f"### Dispatches\n\n"
    )

    coauthor_md = audit / "coauthor.md"
    with coauthor_md.open("a", encoding="utf-8") as f:
        f.write(block)
    return 0


if __name__ == "__main__":
    sys.exit(main())

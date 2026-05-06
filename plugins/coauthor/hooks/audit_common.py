"""Shared helpers for coauthor audit hooks. Stdlib only."""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Sentinel used in audit_user.py and compile_audit.py for turns with no
# active workflow stage. Defined once here so both modules import the same
# literal.
NO_STAGE = "(none)"


def cwd_from_event(event: dict) -> Path:
    """Resolve the working directory the hook should act in."""
    cwd = event.get("cwd") or os.getcwd()
    return Path(cwd)


def audit_dir(event: dict) -> Path | None:
    """Return <cwd>/coauthor/audit/, or None if <cwd>/coauthor/ doesn't exist.

    The hook is silent when the project hasn't opted in (no coauthor/ dir).
    """
    cwd = cwd_from_event(event)
    coauthor = cwd / "coauthor"
    if not coauthor.is_dir():
        return None
    audit = coauthor / "audit"
    audit.mkdir(parents=True, exist_ok=True)
    return audit


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sanitize_worker(name: str) -> str:
    """Sanitize an arbitrary string into a filename-safe worker token."""
    name = (name or "").strip()
    if not name:
        return ""
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
    return safe.strip("._-")[:64]


def read_event() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    import json
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def silent_exit() -> None:
    """No-op return; callers should `return` after invoking, not rely on exit."""
    return

#!/usr/bin/env python3
"""Stop hook: append the assistant's final response to the open turn.

Stop fires on every Stop event (compaction, sub-agent stop, normal end). We
guard against double-appending a `### Coauthor` block to the same turn, and
cache the JSONL byte offset per session so each Stop only parses the new
tail of the transcript instead of re-reading the whole file.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_common import audit_dir, read_event  # noqa: E402


OFFSET_CACHE_NAME = ".last_jsonl_offset"


def _content_is_tool_result(content) -> bool:
    """True iff `content` is a list whose blocks are all tool_result blocks."""
    if not isinstance(content, list) or not content:
        return False
    for block in content:
        if not isinstance(block, dict):
            return False
        if block.get("type") != "tool_result":
            return False
    return True


def _load_offset_cache(audit: Path) -> dict:
    p = audit / OFFSET_CACHE_NAME
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_offset_cache(audit: Path, cache: dict) -> None:
    p = audit / OFFSET_CACHE_NAME
    try:
        p.write_text(json.dumps(cache), encoding="utf-8")
    except Exception:
        pass


def _read_jsonl_entries(
    transcript_path: str,
    start_offset: int,
) -> tuple[list[dict], int]:
    """Read entries from `start_offset` to EOF. Return (entries, new_offset).

    On any read error, returns ([], start_offset) and the caller should fall
    back. If `start_offset` is past EOF, returns ([], file_size).
    """
    p = Path(transcript_path)
    if not p.is_file():
        return [], start_offset
    try:
        size = p.stat().st_size
        if start_offset > size:
            return [], size
        with p.open("rb") as f:
            f.seek(start_offset)
            raw = f.read()
        new_offset = start_offset + len(raw)
    except Exception:
        return [], start_offset

    entries: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception:
            continue
    return entries, new_offset


def extract_last_turn_assistant_text(
    transcript_path: str | None,
    audit: Path | None = None,
    session_id: str = "",
) -> str:
    """Return concatenated assistant text for the most recent turn.

    Uses an offset cache at `<audit>/.last_jsonl_offset` keyed by session_id.
    On hit, only the JSONL tail since the last Stop is parsed; we walk that
    tail to find the latest real user-input boundary and collect assistant
    text after it. On a miss (no cache, missing file, or offset > EOF), falls
    back to a full scan and rebuilds the cache.
    """
    if not transcript_path:
        return ""
    p = Path(transcript_path)
    if not p.is_file():
        return ""

    cache = _load_offset_cache(audit) if audit is not None else {}
    cached_offset = int(cache.get(session_id, 0)) if session_id else 0

    try:
        size = p.stat().st_size
    except Exception:
        return ""

    # Try incremental read first.
    incremental_entries: list[dict] = []
    used_full_scan = False
    if cached_offset and cached_offset <= size:
        incremental_entries, _ = _read_jsonl_entries(transcript_path, cached_offset)
        # If no real user-input boundary appears in the tail, the boundary
        # must lie before cached_offset; fall back to full scan to find it.
        has_user_boundary = False
        for e in incremental_entries:
            if e.get("type") != "user":
                continue
            msg = e.get("message")
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            if isinstance(content, str) or (
                isinstance(content, list) and not _content_is_tool_result(content)
            ):
                has_user_boundary = True
                break
        if not has_user_boundary:
            used_full_scan = True
    else:
        used_full_scan = True

    if used_full_scan:
        try:
            raw_lines = p.read_text(encoding="utf-8").splitlines()
        except Exception:
            return ""
        entries: list[dict] = []
        for line in raw_lines:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except Exception:
                continue
    else:
        entries = incremental_entries

    # Find boundary: most recent user entry that is not a tool_result list.
    boundary = -1
    for i in range(len(entries) - 1, -1, -1):
        e = entries[i]
        if e.get("type") != "user":
            continue
        msg = e.get("message")
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if isinstance(content, str):
            boundary = i
            break
        if isinstance(content, list) and not _content_is_tool_result(content):
            boundary = i
            break

    text_out = ""
    if boundary >= 0:
        pieces: list[str] = []
        for e in entries[boundary + 1:]:
            if e.get("type") != "assistant":
                continue
            msg = e.get("message")
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            text_blocks: list[str] = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") != "text":
                    continue
                t = block.get("text")
                if isinstance(t, str) and t:
                    text_blocks.append(t)
            if text_blocks:
                pieces.append("\n\n".join(text_blocks))
        text_out = "\n\n".join(pieces)

    # Update cache to current EOF for this session.
    if audit is not None and session_id:
        cache[session_id] = size
        _save_offset_cache(audit, cache)

    return text_out


def _coauthor_already_appended(text: str) -> bool:
    """True if the most recent `## Turn` block already has a `### Coauthor`."""
    last_turn = text.rfind("\n## Turn ")
    if last_turn < 0:
        last_turn = text.find("## Turn ")
    if last_turn < 0:
        return False
    tail = text[last_turn:]
    return "### Coauthor" in tail


def main() -> int:
    event = read_event()
    audit = audit_dir(event)
    if audit is None:
        return 0

    coauthor_md = audit / "coauthor.md"
    if not coauthor_md.exists():
        # Stop fired without a preceding open turn; skip silently.
        return 0
    text = coauthor_md.read_text(encoding="utf-8")
    if "## Turn " not in text:
        return 0
    if _coauthor_already_appended(text):
        # A Coauthor block already exists for the current turn (Stop fires on
        # compaction and sub-agent stops too); don't append a second one.
        return 0

    transcript_path = event.get("transcript_path")
    session_id = event.get("session_id", "") or ""
    response = extract_last_turn_assistant_text(transcript_path, audit, session_id)
    body = response.rstrip() if response else "_(no orchestrator text captured)_"

    transcript_comment = (
        f"<!-- transcript_path: {transcript_path} -->\n" if transcript_path else ""
    )

    block = (
        f"\n### Coauthor\n\n"
        f"{transcript_comment}"
        f"{body}\n\n"
        f"---\n"
    )
    with coauthor_md.open("a", encoding="utf-8") as f:
        f.write(block)
    return 0


if __name__ == "__main__":
    sys.exit(main())

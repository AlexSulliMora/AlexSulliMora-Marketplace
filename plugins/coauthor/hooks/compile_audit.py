#!/usr/bin/env python3
"""Compile <cwd>/coauthor/audit/coauthor.md + worker logs into transcript.html.

Stdlib only. Produces a single self-contained HTML file with embedded CSS,
no JS, collapsible dispatch sections, and a sticky sidebar TOC grouped by
stage.
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_common import NO_STAGE  # noqa: E402


STAGES = ("scope", "plan", "work", "review", "finalize", NO_STAGE)


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------

TURN_RE = re.compile(r"^## Turn (.+)$", re.MULTILINE)
STAGE_RE = re.compile(r"^\*\*Stage\*\*:\s*(.+)$", re.MULTILINE)
DISPATCH_REF_RE = re.compile(r"^- Called `([^`]+)` at (.+)$", re.MULTILINE)
TRANSCRIPT_PATH_RE = re.compile(r"<!--\s*transcript_path:\s*(.+?)\s*-->")


def parse_coauthor_md(text: str) -> list[dict]:
    """Parse coauthor.md into a list of turn dicts."""
    turns: list[dict] = []
    matches = list(TURN_RE.finditer(text))
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end]
        ts = m.group(1).strip()

        stage_m = STAGE_RE.search(block)
        stage = stage_m.group(1).strip() if stage_m else NO_STAGE

        # Split into User / Dispatches / Coauthor
        sections = _split_sections(block)
        dispatches = []
        if "Dispatches" in sections:
            for ref in DISPATCH_REF_RE.finditer(sections["Dispatches"]):
                dispatches.append({"worker": ref.group(1), "timestamp": ref.group(2).strip()})

        coauthor_raw = sections.get("Coauthor", "")
        tp_match = TRANSCRIPT_PATH_RE.search(coauthor_raw)
        transcript_path = tp_match.group(1).strip() if tp_match else ""
        # Strip transcript_path comment from the visible coauthor body.
        coauthor_clean = TRANSCRIPT_PATH_RE.sub("", coauthor_raw).strip()
        # Treat the empty-placeholder string as empty for backfill purposes.
        if coauthor_clean == "_(no orchestrator text captured)_":
            coauthor_clean = ""

        turns.append({
            "timestamp": ts,
            "stage": stage,
            "user": sections.get("User", "").strip(),
            "dispatches": dispatches,
            "coauthor": coauthor_clean,
            "transcript_path": transcript_path,
        })
    return turns


# --------------------------------------------------------------------------
# JSONL backfill
# --------------------------------------------------------------------------

def _content_is_tool_result(content) -> bool:
    if not isinstance(content, list) or not content:
        return False
    for block in content:
        if not isinstance(block, dict):
            return False
        if block.get("type") != "tool_result":
            return False
    return True


def _segment_jsonl_into_turns(transcript_path: str) -> list[str]:
    """Return one assistant-text string per user-input turn in the JSONL.

    A turn starts at each user entry whose `message.content` is not a
    tool_result list. Assistant text blocks within the turn are concatenated
    with blank lines. Malformed lines / entries are skipped silently.
    """
    p = Path(transcript_path)
    if not p.is_file():
        return []
    try:
        raw_lines = p.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []

    entries: list[dict] = []
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception:
            continue

    segments: list[list[str]] = []
    current: list[str] | None = None
    for e in entries:
        etype = e.get("type")
        msg = e.get("message") if isinstance(e.get("message"), dict) else None
        if etype == "user" and msg is not None:
            content = msg.get("content")
            is_real_user = isinstance(content, str) or (
                isinstance(content, list) and not _content_is_tool_result(content)
            )
            if is_real_user:
                current = []
                segments.append(current)
                continue
        if etype == "assistant" and msg is not None and current is not None:
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
                current.append("\n\n".join(text_blocks))

    return ["\n\n".join(seg) for seg in segments]


def backfill_coauthor_from_jsonl(turns: list[dict]) -> None:
    """Mutate `turns` in place: fill empty `coauthor` from the session JSONL.

    Matches the Nth turn block in coauthor.md to the Nth user-input segment
    in the JSONL referenced by `transcript_path`. If counts differ, log to
    stderr and leave that file's turns alone.
    """
    # Group turns by transcript_path (one session per JSONL).
    by_path: dict[str, list[int]] = {}
    for i, turn in enumerate(turns):
        tp = turn.get("transcript_path") or ""
        if tp:
            by_path.setdefault(tp, []).append(i)

    for tp, idxs in by_path.items():
        segments = _segment_jsonl_into_turns(tp)
        if len(segments) != len(idxs):
            print(
                f"compile_audit: turn count mismatch for {tp}: "
                f"{len(idxs)} turn blocks vs {len(segments)} JSONL segments; "
                f"skipping backfill",
                file=sys.stderr,
            )
            continue
        for turn_idx, seg in zip(idxs, segments):
            if not turns[turn_idx]["coauthor"] and seg.strip():
                turns[turn_idx]["coauthor"] = seg.strip()


def _split_sections(block: str) -> dict[str, str]:
    out: dict[str, str] = {}
    headings = list(re.finditer(r"^### (User|Dispatches|Coauthor)\s*$", block, re.MULTILINE))
    for i, h in enumerate(headings):
        start = h.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(block)
        body = block[start:end]
        # Strip trailing horizontal rules
        body = re.sub(r"\n---\s*\n?$", "\n", body)
        out[h.group(1)] = body
    return out


WORKER_ENTRY_RE = re.compile(r"^## (.+?)\s*$", re.MULTILINE)


def parse_worker_log(text: str) -> dict[str, dict]:
    """Return {timestamp -> entry dict} for a worker log."""
    entries: dict[str, dict] = {}
    matches = list(WORKER_ENTRY_RE.finditer(text))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        ts = m.group(1).strip()

        tool = _extract_meta(body, "Tool")
        session = _extract_meta(body, "Session")
        agent_id = _extract_meta(body, "Agent ID")

        prompt = _extract_subsection(body, "Prompt")
        response = _extract_subsection(body, "Response")

        entries[ts] = {
            "timestamp": ts,
            "tool": tool,
            "session": session,
            "agent_id": agent_id,
            "prompt": prompt,
            "response": response,
        }
    return entries


def _extract_meta(body: str, key: str) -> str:
    m = re.search(rf"^\*\*{re.escape(key)}\*\*:\s*(.*)$", body, re.MULTILINE)
    return m.group(1).strip() if m else ""


def _extract_subsection(body: str, name: str) -> str:
    m = re.search(rf"^### {re.escape(name)}\s*$", body, re.MULTILINE)
    if not m:
        return ""
    start = m.end()
    nxt = re.search(r"^### |^---\s*$", body[start:], re.MULTILINE)
    end = start + nxt.start() if nxt else len(body)
    return body[start:end].strip()


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

CSS = """
* { box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  margin: 0;
  background: #fafaf7;
  color: #222;
  line-height: 1.55;
}
.layout { display: grid; grid-template-columns: 240px 1fr; min-height: 100vh; }
nav.toc {
  position: sticky; top: 0; align-self: start;
  height: 100vh; overflow-y: auto;
  background: #f0efe9; border-right: 1px solid #ddd;
  padding: 1rem 0.75rem; font-size: 0.85rem;
}
nav.toc h2 { font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.05em; color: #666; margin: 0 0 0.5rem; }
nav.toc .stage-group { margin-bottom: 0.85rem; }
nav.toc .stage-label {
  font-weight: 600; color: #333;
  border-bottom: 1px solid #ccc; padding-bottom: 0.15rem; margin-bottom: 0.25rem;
}
nav.toc ul { list-style: none; padding: 0; margin: 0.25rem 0 0 0.4rem; }
nav.toc li { margin: 0.15rem 0; }
nav.toc a { color: #335; text-decoration: none; }
nav.toc a:hover { text-decoration: underline; }
main { padding: 2rem 2.5rem; max-width: 80ch; }
h1 { margin-top: 0; }
.turn { margin: 2rem 0 3rem; padding-bottom: 1.5rem; border-bottom: 1px solid #ddd; }
.turn-meta { color: #666; font-size: 0.85rem; margin-bottom: 0.75rem; }
.turn-meta .stage-pill {
  display: inline-block; background: #e6e2d6; color: #444;
  padding: 0.05rem 0.5rem; border-radius: 3px; margin-left: 0.4rem;
  font-family: monospace; font-size: 0.8rem;
}
section.user, section.coauthor { margin: 1rem 0; }
section h3 { font-size: 0.95rem; text-transform: uppercase; letter-spacing: 0.04em; color: #555; margin-bottom: 0.4rem; }
pre.content {
  background: #fff; border: 1px solid #ddd; border-radius: 4px;
  padding: 0.85rem 1rem; white-space: pre-wrap; word-wrap: break-word;
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Consolas, monospace;
  font-size: 0.86rem; line-height: 1.5;
}
section.coauthor pre.content { background: #f7f5ee; }
details.dispatch {
  border: 1px solid #d6d2c5; border-radius: 4px; margin: 0.5rem 0;
  background: #fdfcf6;
}
details.dispatch[open] { background: #fff; }
details.dispatch summary {
  cursor: pointer; padding: 0.5rem 0.75rem; font-size: 0.88rem;
  list-style: none;
}
details.dispatch summary::-webkit-details-marker { display: none; }
details.dispatch summary::before { content: "▸ "; color: #888; }
details.dispatch[open] summary::before { content: "▾ "; }
details.dispatch summary .worker-name { font-family: monospace; font-weight: 600; color: #224; }
details.dispatch summary .tool-tag {
  display: inline-block; background: #e0dccc; color: #555;
  font-size: 0.72rem; padding: 0.05rem 0.35rem; border-radius: 3px; margin-left: 0.35rem;
}
details.dispatch summary .ts { color: #888; font-size: 0.78rem; margin-left: 0.4rem; }
details.dispatch .body { padding: 0 0.85rem 0.85rem; }
details.dispatch h4 { font-size: 0.78rem; color: #666; margin: 0.85rem 0 0.3rem; text-transform: uppercase; letter-spacing: 0.05em; }
.warning {
  border: 1px solid #d4a; background: #fef0f4; color: #842;
  padding: 0.5rem 0.85rem; border-radius: 4px; font-size: 0.85rem;
}
.dispatches-list { margin: 0.5rem 0; }
.section-orphan { margin-top: 4rem; border-top: 2px solid #aaa; padding-top: 1.5rem; }
"""


def render_html(turns: list[dict], worker_logs: dict[str, dict[str, dict]]) -> str:
    # Group turns by stage (preserve listed stage order, then any extras)
    stage_buckets: dict[str, list[tuple[int, dict]]] = {}
    for i, turn in enumerate(turns):
        stage_buckets.setdefault(turn["stage"], []).append((i, turn))
    stage_order = [s for s in STAGES if s in stage_buckets]
    stage_order += [s for s in stage_buckets if s not in STAGES]

    # Track which (worker, ts) references were resolved for orphan detection
    referenced: set[tuple[str, str]] = set()

    # ---- TOC ----
    toc_parts = ['<nav class="toc"><h2>Transcript</h2>']
    for stage in stage_order:
        toc_parts.append('<div class="stage-group">')
        toc_parts.append(f'<div class="stage-label">{html.escape(stage)}</div><ul>')
        for idx, turn in stage_buckets[stage]:
            anchor = f"turn-{idx}"
            label = html.escape(turn["timestamp"])
            toc_parts.append(f'<li><a href="#{anchor}">{label}</a></li>')
        toc_parts.append('</ul></div>')
    toc_parts.append('</nav>')

    # ---- Main ----
    body_parts = ['<main><h1>Coauthor transcript</h1>']
    for i, turn in enumerate(turns):
        anchor = f"turn-{i}"
        body_parts.append(f'<article class="turn" id="{anchor}">')
        body_parts.append(
            f'<div class="turn-meta">{html.escape(turn["timestamp"])}'
            f'<span class="stage-pill">{html.escape(turn["stage"])}</span></div>'
        )
        body_parts.append('<section class="user"><h3>User</h3>')
        body_parts.append(f'<pre class="content">{html.escape(turn["user"])}</pre></section>')

        if turn["dispatches"]:
            body_parts.append('<section class="dispatches"><h3>Dispatches</h3><div class="dispatches-list">')
            for d in turn["dispatches"]:
                worker = d["worker"]
                ts = d["timestamp"]
                referenced.add((worker, ts))
                entry = worker_logs.get(worker, {}).get(ts)
                body_parts.append(_render_dispatch(worker, ts, entry))
            body_parts.append('</div></section>')

        if turn["coauthor"]:
            body_parts.append('<section class="coauthor"><h3>Coauthor</h3>')
            body_parts.append(f'<pre class="content">{html.escape(turn["coauthor"])}</pre></section>')

        body_parts.append('</article>')

    # ---- Orphan dispatches ----
    orphans: list[tuple[str, dict]] = []
    for worker, entries in worker_logs.items():
        for ts, entry in entries.items():
            if (worker, ts) not in referenced:
                orphans.append((worker, entry))
    if orphans:
        body_parts.append('<section class="section-orphan"><h2>Orphan dispatches</h2>')
        body_parts.append('<p>Worker log entries with no matching reference in <code>coauthor.md</code>.</p>')
        for worker, entry in orphans:
            body_parts.append(_render_dispatch(worker, entry["timestamp"], entry))
        body_parts.append('</section>')

    body_parts.append('</main>')

    return (
        "<!DOCTYPE html>\n<html><head><meta charset=\"utf-8\">"
        "<title>Coauthor transcript</title>"
        f"<style>{CSS}</style></head><body><div class=\"layout\">"
        + "".join(toc_parts)
        + "".join(body_parts)
        + "</div></body></html>\n"
    )


def _render_dispatch(worker: str, ts: str, entry: dict | None) -> str:
    if entry is None:
        return (
            '<details class="dispatch"><summary>'
            f'<span class="worker-name">{html.escape(worker)}</span>'
            '<span class="tool-tag">missing</span>'
            f'<span class="ts">{html.escape(ts)}</span>'
            '</summary><div class="body">'
            f'<div class="warning">No matching entry found in <code>{html.escape(worker)}.md</code> '
            f'for timestamp <code>{html.escape(ts)}</code>.</div>'
            '</div></details>'
        )
    return (
        '<details class="dispatch"><summary>'
        f'<span class="worker-name">{html.escape(worker)}</span>'
        f'<span class="tool-tag">{html.escape(entry["tool"])}</span>'
        f'<span class="ts">{html.escape(ts)}</span>'
        '</summary><div class="body">'
        '<h4>Prompt</h4>'
        f'<pre class="content">{html.escape(entry["prompt"])}</pre>'
        '<h4>Response</h4>'
        f'<pre class="content">{html.escape(entry["response"])}</pre>'
        '</div></details>'
    )


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> int:
    cwd = Path(os.getcwd())
    audit = cwd / "coauthor" / "audit"
    if not audit.is_dir():
        print(f"audit directory not found at {audit}", file=sys.stderr)
        return 1

    coauthor_md = audit / "coauthor.md"
    if not coauthor_md.is_file():
        print(f"coauthor.md not found at {coauthor_md}", file=sys.stderr)
        return 1

    text = coauthor_md.read_text(encoding="utf-8")
    turns = parse_coauthor_md(text)
    backfill_coauthor_from_jsonl(turns)

    worker_logs: dict[str, dict[str, dict]] = {}
    for p in audit.iterdir():
        if not p.is_file() or p.suffix != ".md" or p.name == "coauthor.md":
            continue
        worker = p.stem
        worker_logs[worker] = parse_worker_log(p.read_text(encoding="utf-8"))

    out_html = render_html(turns, worker_logs)
    out_path = audit / "transcript.html"
    out_path.write_text(out_html, encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())

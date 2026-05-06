#!/usr/bin/env python3
"""Mechanical AI-tell checker for prose artifacts.

Deterministic regex- and heuristic-based checks. No grading, no rewriting.
Stdlib only.

CLI:
    python check.py [--format=text|json] <file> [<file> ...]

Exit code: 0 if no violations, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path


STATISTICAL_CONTEXT_TERMS = (
    "standard error",
    "covariance",
    "estimator",
    "inference",
    "regression",
    "asymptotic",
    "robust standard",
    "heteroskedast",
    "cluster",
)

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "of", "in", "on",
    "at", "to", "for", "by", "with", "from", "as", "is", "are", "was",
    "were", "be", "been", "being", "this", "that", "these", "those", "it",
    "its", "we", "i", "you", "he", "she", "they", "them", "their", "his",
    "her", "our", "your", "my", "have", "has", "had", "do", "does", "did",
    "will", "would", "can", "could", "should", "may", "might", "must",
    "shall", "not", "no", "yes", "so", "than", "such", "also", "only",
    "very", "just", "into", "out", "over", "under", "again", "more",
    "most", "other", "some", "any", "all", "each", "both", "which",
    "who", "whom", "what", "when", "where", "why", "how", "there", "here",
}

HEDGES = ("might", "could", "possibly", "perhaps", "maybe", "seem",
          "seems", "appear", "appears", "likely", "arguably", "may")

THROAT_CLEARING = (
    r"Let me explain\b",
    r"Let me\b",
    r"To start\b",
    r"In summary\b",
    r"In conclusion\b",
    r"I'll\b",
)

ENGAGEMENT_BAIT = (
    r"\blet me know if\b",
    r"\bhappy to\b",
    r"\bwant me to\b",
    r"\bfeel free to\b",
)

EMPTY_EMPHASIS = ("real", "genuine", "actual", "truly", "actually")

CLOSING_RECAPS = ("In summary", "To summarize", "In conclusion", "Overall",
                  "Taken together")


@dataclass
class Violation:
    file: str
    line: int
    col: int
    pattern_id: str
    snippet: str
    suggestion: str


def _line_col(text: str, idx: int) -> tuple[int, int]:
    """Return 1-indexed (line, col) for character index idx."""
    upto = text[:idx]
    line = upto.count("\n") + 1
    last_nl = upto.rfind("\n")
    col = idx - last_nl if last_nl >= 0 else idx + 1
    return line, col


def _snippet(text: str, idx: int, length: int = 60) -> str:
    line_start = text.rfind("\n", 0, idx) + 1
    line_end = text.find("\n", idx)
    if line_end == -1:
        line_end = len(text)
    return text[line_start:line_end].strip()[:length]


def _split_sentences(text: str) -> list[tuple[int, str]]:
    """Return (start_index, sentence) pairs. Naive splitter."""
    out: list[tuple[int, str]] = []
    start = 0
    for m in re.finditer(r"[.!?](?:\s+|$)", text):
        end = m.end()
        out.append((start, text[start:end]))
        start = end
    if start < len(text):
        out.append((start, text[start:]))
    return out


def check_banned_words(path: str, text: str) -> list[Violation]:
    violations: list[Violation] = []
    banned = {
        "prose": "rephrase or use a more specific term (writing, draft, paragraph)",
        "delve": "use 'examine', 'study', or simply remove",
        "comprehensive": "use 'full', 'complete', or specify what is covered",
        "smoke test": ("use 'sanity check' for high-level plausibility checks, "
                       "'trial run' for first-pass tests"),
    }
    for word, fix in banned.items():
        for m in re.finditer(rf"\b{re.escape(word)}\b", text, re.IGNORECASE):
            line, col = _line_col(text, m.start())
            violations.append(Violation(
                path, line, col, "banned-word",
                _snippet(text, m.start()),
                f"banned word '{word}': {fix}",
            ))
    # leverage as a verb: heuristic — followed by article/noun (not preceded by 'the' or 'high')
    for m in re.finditer(r"\bleverage[sd]?\b", text, re.IGNORECASE):
        before = text[max(0, m.start() - 15):m.start()].lower()
        if re.search(r"\b(the|high|low|much|more|less|some|any)\s*$", before):
            continue
        line, col = _line_col(text, m.start())
        violations.append(Violation(
            path, line, col, "leverage-verb",
            _snippet(text, m.start()),
            "'leverage' as verb: use 'use', 'apply', or 'exploit'",
        ))
    # robust outside statistical context
    for m in re.finditer(r"\brobust\b", text, re.IGNORECASE):
        sent_start = text.rfind(".", 0, m.start()) + 1
        sent_end = text.find(".", m.end())
        if sent_end == -1:
            sent_end = len(text)
        sentence = text[sent_start:sent_end].lower()
        if any(term in sentence for term in STATISTICAL_CONTEXT_TERMS):
            continue
        line, col = _line_col(text, m.start())
        violations.append(Violation(
            path, line, col, "robust-non-stat",
            _snippet(text, m.start()),
            "'robust' outside statistical context: keep if statistical, otherwise use 'reliable', 'durable', or specify",
        ))
    return violations


def check_banned_patterns(path: str, text: str) -> list[Violation]:
    violations: list[Violation] = []
    for m in re.finditer(r"\bit'?s not [^,.\n]{1,40},\s*it'?s\b", text, re.IGNORECASE):
        line, col = _line_col(text, m.start())
        violations.append(Violation(
            path, line, col, "not-x-its-y",
            _snippet(text, m.start()),
            "'it's not X, it's Y' construction: state the positive claim directly",
        ))
    # Narrow trigger: only fire on the rhetorical pattern preceded by a
    # framing phrase like "it is", "we want", "the goal is", "this is".
    # The bare "X, not Y" form is too broad — it flags legitimate technical
    # contrastive emphasis ("ATEs, not ATTs", "OLS, not IV", "reduce, not
    # eliminate"). The cleaner "it's not X, it's Y" check above handles the
    # main rhetorical case; this narrowed rule catches close variants.
    rhetorical_lead = (
        r"(?:\bit\s+is\b|\bthis\s+is\b|\bthat\s+is\b|"
        r"\bwe\s+want\b|\bwe\s+need\b|"
        r"\bthe\s+goal\s+is\b|\bthe\s+point\s+is\b)\s+"
    )
    for m in re.finditer(rhetorical_lead + r"(\w+),\s+not\s+(\w+)\b", text, re.IGNORECASE):
        line, col = _line_col(text, m.start())
        violations.append(Violation(
            path, line, col, "x-not-y",
            _snippet(text, m.start()),
            "'X, not Y' construction: rephrase as a direct positive claim",
        ))
    return violations


def check_surface_verb(path: str, text: str) -> list[Violation]:
    violations: list[Violation] = []
    # surface followed by determiner or capitalized noun-like token
    for m in re.finditer(r"\bsurface[sd]?|surfacing\b", text, re.IGNORECASE):
        after = text[m.end():m.end() + 30]
        # skip "the surface" or "a surface" (noun usage)
        before = text[max(0, m.start() - 10):m.start()].lower()
        if re.search(r"\b(the|a|an|its|on|under|water'?s|earth'?s)\s+$", before):
            continue
        if re.match(r"\s+(the|a|an|this|that|these|those|[A-Z]\w+|\w+(ing|ion|ity|ness|s)\b)", after):
            line, col = _line_col(text, m.start())
            violations.append(Violation(
                path, line, col, "surface-verb",
                _snippet(text, m.start()),
                "'surface' as verb: use 'reveal', 'expose', 'identify', 'raise'",
            ))
    return violations


def _is_in_list_or_heading(text: str, idx: int) -> bool:
    line_start = text.rfind("\n", 0, idx) + 1
    line_end = text.find("\n", idx)
    if line_end == -1:
        line_end = len(text)
    line = text[line_start:line_end]
    return bool(re.match(r"^\s*([-*+]|\d+\.|#+)\s", line))


def check_throat_clearing(path: str, text: str) -> list[Violation]:
    violations: list[Violation] = []
    for pat in THROAT_CLEARING:
        # Capture the phrase itself in group(1) so we can locate its start
        # directly via m.start(1), avoiding off-by-one arithmetic from the
        # variable-length boundary group.
        for m in re.finditer(rf"(?:^|\n\s*\n\s*|\.\s+)({pat})", text):
            offset = m.start(1)
            line, col = _line_col(text, offset)
            violations.append(Violation(
                path, line, col, "throat-clearing",
                _snippet(text, offset),
                "throat-clearing opener: cut and start with the substantive sentence",
            ))
    return violations


def check_engagement_bait(path: str, text: str) -> list[Violation]:
    violations: list[Violation] = []
    for pat in ENGAGEMENT_BAIT:
        for m in re.finditer(pat, text, re.IGNORECASE):
            line, col = _line_col(text, m.start())
            violations.append(Violation(
                path, line, col, "engagement-bait",
                _snippet(text, m.start()),
                "engagement bait: cut; the user will follow up if they want more",
            ))
    return violations


def check_empty_emphasis(path: str, text: str) -> list[Violation]:
    violations: list[Violation] = []
    pattern = r"\b(" + "|".join(EMPTY_EMPHASIS) + r")\b"
    for m in re.finditer(pattern, text, re.IGNORECASE):
        line, col = _line_col(text, m.start())
        violations.append(Violation(
            path, line, col, "empty-emphasis",
            _snippet(text, m.start()),
            f"empty emphasis '{m.group(1)}': flag for human review — keep only if disambiguating",
        ))
    return violations


def check_hedge_stacking(path: str, text: str) -> list[Violation]:
    violations: list[Violation] = []
    # split on clause boundaries
    for m in re.finditer(r"[^.!?;\n]+", text):
        clause = m.group()
        hits = []
        for h in HEDGES:
            for hm in re.finditer(rf"\b{h}\b", clause, re.IGNORECASE):
                hits.append(hm.start())
        if len(hits) > 1:
            offset = m.start() + hits[0]
            line, col = _line_col(text, offset)
            violations.append(Violation(
                path, line, col, "hedge-stacking",
                _snippet(text, offset),
                f"{len(hits)} hedges in one clause: keep at most one",
            ))
    return violations


def check_long_parentheticals(path: str, text: str) -> list[Violation]:
    violations: list[Violation] = []
    for m in re.finditer(r"\(([^()\n]{1,500})\)", text):
        inner = m.group(1)
        # only mid-sentence: parens not at sentence/line start
        before = text[max(0, m.start() - 2):m.start()]
        if re.match(r"^\s*$", before) or before.endswith("\n"):
            continue
        if len(inner.split()) > 12:
            line, col = _line_col(text, m.start())
            violations.append(Violation(
                path, line, col, "long-parenthetical",
                _snippet(text, m.start()),
                f"parenthetical with {len(inner.split())} words mid-sentence: integrate or cut",
            ))
    return violations


def check_em_dash(path: str, text: str) -> list[Violation]:
    violations: list[Violation] = []
    for start, sentence in _split_sentences(text):
        for m in re.finditer(r"—| -- ", sentence):
            prior = sentence[:m.start()]
            if "," in prior or ";" in prior:
                continue
            offset = start + m.start()
            line, col = _line_col(text, offset)
            violations.append(Violation(
                path, line, col, "em-dash-no-prior-punct",
                _snippet(text, offset),
                "em-dash in sentence with no prior comma/semicolon: restructure or use comma/semicolon",
            ))
    return violations


DATETIME_TOKENS = {
    "YYYY", "MM", "DD", "HH", "MIN", "SS", "TZ", "ISO", "UTC",
    "YYYY-MM-DD", "YYYY-MM", "HH:MM:SS",
}


def _load_acronym_ignore(path: str) -> set[str]:
    """Load per-project ignore list from <cwd>/coauthor/.acronym-ignore.

    The path argument is the file under check; we resolve cwd by walking up
    looking for a `coauthor/` sibling, falling back to the actual cwd. Lines
    starting with `#` are comments; blank lines ignored.
    """
    candidates = []
    p = Path(path).resolve()
    for parent in [p.parent, *p.parents]:
        candidates.append(parent / "coauthor" / ".acronym-ignore")
    candidates.append(Path.cwd() / "coauthor" / ".acronym-ignore")
    seen: set[str] = set()
    tokens: set[str] = set()
    for c in candidates:
        cs = str(c)
        if cs in seen:
            continue
        seen.add(cs)
        if not c.is_file():
            continue
        for raw in c.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            tokens.add(line)
        break
    return tokens


def check_undefined_acronyms(path: str, text: str) -> list[Violation]:
    violations: list[Violation] = []
    # Mask code blocks, inline code, and angle-bracket placeholders by
    # replacing their non-newline characters with spaces. This preserves
    # all character offsets (and therefore line/column) so reported
    # positions translate directly to the original text.
    def _mask(s: str, pattern: str, flags: int = 0) -> str:
        def repl(mo: re.Match) -> str:
            return "".join(ch if ch == "\n" else " " for ch in mo.group())
        return re.sub(pattern, repl, s, flags=flags)

    text_no_code = _mask(text, r"```.*?```", re.DOTALL)
    text_no_code = _mask(text_no_code, r"`[^`\n]+`")
    text_no_code = _mask(text_no_code, r"<[^>\n]+>")
    ignore = _load_acronym_ignore(path) | DATETIME_TOKENS
    defined: set[str] = set()
    seen_undefined: set[str] = set()
    for m in re.finditer(r"\b[A-Z]{2,6}\b", text_no_code):
        token = m.group()
        if token in ignore:
            continue
        # also skip combined date/time forms like YYYY-MM-DD: check surrounding text
        ctx_around = text_no_code[max(0, m.start() - 1):m.end() + 12]
        skip_combined = False
        for combo in ("YYYY-MM-DD", "YYYY-MM", "HH:MM:SS"):
            if combo in text_no_code[max(0, m.start() - 12):m.end() + 12]:
                # token is part of a combined datetime form
                if token in {"YYYY", "MM", "DD", "HH", "SS"}:
                    skip_combined = True
                    break
        if skip_combined:
            continue
        # check if previously defined: look for "Word Word (TOKEN)" within prior 200 chars
        window = text_no_code[max(0, m.start() - 200):m.start()]
        if re.search(rf"\(\s*{re.escape(token)}\s*\)", window):
            defined.add(token)
            continue
        # check if this position itself is the definition: preceded by close-paren expansion
        # pattern: "(TOKEN)" inline — treat as definition site
        ctx = text_no_code[max(0, m.start() - 2):m.end() + 1]
        if ctx.startswith("(") and ctx.endswith(")"):
            defined.add(token)
            continue
        if token in defined or token in seen_undefined:
            continue
        seen_undefined.add(token)
        # Offsets in text_no_code match the original text because masking
        # preserves character positions.
        line, col = _line_col(text, m.start())
        violations.append(Violation(
            path, line, col, "undefined-acronym",
            _snippet(text, m.start()),
            f"acronym '{token}' used before definition: expand on first use as 'Full Form ({token})'",
        ))
    return violations


def check_repetition(path: str, text: str) -> list[Violation]:
    violations: list[Violation] = []
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text)
    positions = [m.start() for m in re.finditer(r"\b[a-zA-Z]{3,}\b", text)]
    window = 200
    flagged: set[tuple[str, int]] = set()
    # For docs shorter than the window, run a single pass over the whole doc
    # so short documents still get a repetition check. For longer docs, slide
    # the window across all valid start positions.
    if len(words) < window:
        starts = [0] if words else []
    else:
        starts = list(range(len(words) - window + 1))
    for i in starts:
        chunk = words[i:i + window]
        counts = Counter(w.lower() for w in chunk)
        for w, c in counts.items():
            if c > 5 and w not in STOPWORDS:
                key = (w, i // window)
                if key in flagged:
                    continue
                flagged.add(key)
                offset = positions[i]
                line, col = _line_col(text, offset)
                violations.append(Violation(
                    path, line, col, "repetition",
                    _snippet(text, offset),
                    f"'{w}' appears {c} times in 200-word window: vary wording",
                ))
    # sentence-opening tri-grams
    sentences = [s.strip() for _, s in _split_sentences(text) if s.strip()]
    trigrams: Counter[str] = Counter()
    for s in sentences:
        toks = re.findall(r"\b\w+\b", s)
        if len(toks) >= 3:
            tri = " ".join(t.lower() for t in toks[:3])
            trigrams[tri] += 1
    for tri, c in trigrams.items():
        if c >= 3:
            # find first occurrence in text
            m = re.search(re.escape(tri), text, re.IGNORECASE)
            if m is None:
                continue
            line, col = _line_col(text, m.start())
            violations.append(Violation(
                path, line, col, "opening-trigram-repeat",
                _snippet(text, m.start()),
                f"sentence-opening trigram '{tri}' used {c} times: vary sentence structure",
            ))
    return violations


def check_closing_summary(path: str, text: str) -> list[Violation]:
    violations: list[Violation] = []
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        return violations
    last = paragraphs[-1].lstrip()
    for recap in CLOSING_RECAPS:
        if last.lower().startswith(recap.lower()):
            offset = text.rfind(last[:30])
            if offset < 0:
                offset = 0
            line, col = _line_col(text, offset)
            violations.append(Violation(
                path, line, col, "closing-summary",
                last[:80],
                "closing summary paragraph: cut or rewrite as a substantive final point",
            ))
            break
    # also flag if last paragraph is mostly header restatement (heuristic skipped — too noisy)
    return violations


CHECKS = [
    check_banned_words,
    check_banned_patterns,
    check_surface_verb,
    check_throat_clearing,
    check_engagement_bait,
    check_empty_emphasis,
    check_hedge_stacking,
    check_long_parentheticals,
    check_em_dash,
    check_undefined_acronyms,
    check_repetition,
    check_closing_summary,
]


def check_file(path: str) -> list[Violation]:
    text = Path(path).read_text(encoding="utf-8")
    out: list[Violation] = []
    for fn in CHECKS:
        out.extend(fn(path, text))
    out.sort(key=lambda v: (v.file, v.line, v.col))
    return out


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("files", nargs="+")
    args = parser.parse_args(argv)

    all_violations: list[Violation] = []
    for path in args.files:
        all_violations.extend(check_file(path))

    if args.format == "json":
        print(json.dumps([asdict(v) for v in all_violations], indent=2))
    else:
        for v in all_violations:
            print(f"{v.file}:{v.line}:{v.col} [{v.pattern_id}] {v.snippet}")
            print(f"  -> {v.suggestion}")

    return 1 if all_violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

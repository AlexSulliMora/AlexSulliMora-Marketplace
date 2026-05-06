#!/usr/bin/env python3
"""Mechanical Quarto-HTML style checker for `.qmd` and rendered `.html` files.

Deterministic regex- and heuristic-based checks. No grading, no rewriting.
Stdlib only. Source of truth for the conventions:
`${CLAUDE_PLUGIN_ROOT}/skills/quarto-html-report/SKILL.md`.

CLI:
    python check.py [--format=text|json] <file> [<file> ...]

Exit code: 0 if no violations, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path


REQUIRED_YAML_KEYS = (
    ("embed-resources", "true"),
    ("page-layout", "full"),
    ("toc-depth", "2"),
    ("code-fold", "true"),
)


@dataclass
class Violation:
    file: str
    line: int
    col: int
    pattern_id: str
    snippet: str
    suggestion: str


def _line_col(text: str, idx: int) -> tuple[int, int]:
    upto = text[:idx]
    line = upto.count("\n") + 1
    last_nl = upto.rfind("\n")
    col = idx - last_nl if last_nl >= 0 else idx + 1
    return line, col


def _snippet(text: str, idx: int, length: int = 80) -> str:
    line_start = text.rfind("\n", 0, idx) + 1
    line_end = text.find("\n", idx)
    if line_end == -1:
        line_end = len(text)
    return text[line_start:line_end].strip()[:length]


def _extract_yaml_frontmatter(text: str) -> tuple[str, int] | None:
    """Return (yaml_text, start_offset_of_yaml_body) or None."""
    m = re.match(r"---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
    if not m:
        return None
    return m.group(1), m.start(1)


def check_yaml_frontmatter(path: str, text: str) -> list[Violation]:
    if not path.endswith(".qmd"):
        return []
    fm = _extract_yaml_frontmatter(text)
    violations: list[Violation] = []
    if fm is None:
        violations.append(Violation(
            path, 1, 1, "missing-frontmatter", text[:80].strip(),
            "`.qmd` HTML reports require a YAML frontmatter block; copy the template at "
            "${CLAUDE_PLUGIN_ROOT}/skills/quarto-html-report/template.qmd",
        ))
        return violations
    yaml_text, yaml_offset = fm
    for key, expected in REQUIRED_YAML_KEYS:
        pat = re.compile(rf"^\s*{re.escape(key)}\s*:\s*(\S.*)$", re.MULTILINE)
        m = pat.search(yaml_text)
        if m is None:
            line, col = _line_col(text, yaml_offset)
            violations.append(Violation(
                path, line, col, "missing-yaml-key", _snippet(text, yaml_offset),
                f"YAML frontmatter missing required key '{key}: {expected}' "
                f"(see ${{CLAUDE_PLUGIN_ROOT}}/skills/quarto-html-report/SKILL.md)",
            ))
            continue
        actual = m.group(1).strip().strip("\"'")
        if actual.lower() != expected.lower():
            offset = yaml_offset + m.start()
            line, col = _line_col(text, offset)
            violations.append(Violation(
                path, line, col, "wrong-yaml-value", _snippet(text, offset),
                f"YAML key '{key}' should be '{expected}' (found '{actual}')",
            ))
    return violations


def check_fmt_date_iso(path: str, text: str) -> list[Violation]:
    violations: list[Violation] = []
    for m in re.finditer(r"\bfmt_date\s*\(", text):
        depth = 1
        i = m.end()
        while i < len(text) and depth > 0:
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
            i += 1
        call_text = text[m.start():i]
        if 'date_style="iso"' not in call_text and "date_style='iso'" not in call_text:
            line, col = _line_col(text, m.start())
            violations.append(Violation(
                path, line, col, "fmt-date-no-iso", _snippet(text, m.start()),
                "fmt_date(...) call missing date_style=\"iso\"; without it dates render as "
                "'m_day_year'",
            ))
    return violations


def check_gt_scroll_wrapper(path: str, text: str) -> list[Violation]:
    violations: list[Violation] = []
    has_gt_scroll = ('class="gt-scroll"' in text) or ("class='gt-scroll'" in text)
    has_show_table_helper = re.search(r"\bdef\s+show_table\s*\(", text) is not None
    for m in re.finditer(r"\.as_raw_html\s*\(\s*\)", text):
        if has_gt_scroll or has_show_table_helper:
            continue
        line, col = _line_col(text, m.start())
        violations.append(Violation(
            path, line, col, "missing-gt-scroll", _snippet(text, m.start()),
            "great_tables emission not wrapped in <div class=\"gt-scroll\">; sticky thead and "
            "horizontal scroll require the wrapper",
        ))
    return violations


def check_sub_missing_emdash(path: str, text: str) -> list[Violation]:
    violations: list[Violation] = []
    for m in re.finditer(r"\bsub_missing\s*\(", text):
        depth = 1
        i = m.end()
        while i < len(text) and depth > 0:
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
            i += 1
        call_text = text[m.start():i]
        if 'missing_text="—"' in call_text or "missing_text='—'" in call_text:
            continue
        line, col = _line_col(text, m.start())
        violations.append(Violation(
            path, line, col, "sub-missing-not-emdash", _snippet(text, m.start()),
            "sub_missing(...) should use missing_text=\"—\" (em-dash) per the Quarto skill "
            "convention",
        ))
    return violations


def check_css_rules(path: str, text: str) -> list[Violation]:
    if not path.endswith(".qmd") and not path.endswith(".html"):
        return []
    style_blocks = re.findall(r"<style[^>]*>(.*?)</style>", text, re.DOTALL | re.IGNORECASE)
    if not style_blocks:
        return [Violation(
            path, 1, 1, "missing-style-block", "",
            "no <style> block found; copy the embedded CSS from "
            "${CLAUDE_PLUGIN_ROOT}/skills/quarto-html-report/template.qmd",
        )]
    css = "\n".join(style_blocks)
    violations: list[Violation] = []
    has_full_width = re.search(r"width\s*:\s*100%", css) and re.search(
        r"min-width\s*:\s*max-content", css
    )
    if not has_full_width:
        violations.append(Violation(
            path, 1, 1, "missing-table-width-rule", "",
            "CSS missing 'width: 100%; min-width: max-content' for table width; narrow tables "
            "will not fill page width",
        ))
    has_sticky_override = re.search(
        r"\.gt-scroll\s*>\s*div\s*\{[^}]*overflow\s*:\s*visible\s*!important",
        css,
        re.DOTALL,
    )
    if not has_sticky_override:
        violations.append(Violation(
            path, 1, 1, "missing-sticky-thead-override", "",
            "CSS missing the '.gt-scroll > div { overflow: visible !important; ... }' "
            "override; sticky thead will not stick without it",
        ))
    return violations


def check_pre_wrap(path: str, text: str) -> list[Violation]:
    violations: list[Violation] = []
    style_blocks = re.findall(r"<style[^>]*>(.*?)</style>", text, re.DOTALL | re.IGNORECASE)
    css = "\n".join(style_blocks)
    has_global_pre_wrap = (
        re.search(r"pre\s*[,{][^}]*white-space\s*:\s*pre-wrap", css, re.DOTALL)
        is not None
    )
    has_wrap_pre_class = "wrap-pre" in text
    if has_global_pre_wrap or has_wrap_pre_class:
        return violations
    for m in re.finditer(r"<pre[^>]*>", text, re.IGNORECASE):
        line, col = _line_col(text, m.start())
        violations.append(Violation(
            path, line, col, "pre-no-wrap", _snippet(text, m.start()),
            "<pre> block without 'wrap-pre' wrapper or global 'white-space: pre-wrap' CSS; "
            "Python output will show a horizontal scrollbar",
        ))
    return violations


CHECKS = [
    check_yaml_frontmatter,
    check_fmt_date_iso,
    check_gt_scroll_wrapper,
    check_sub_missing_emdash,
    check_css_rules,
    check_pre_wrap,
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

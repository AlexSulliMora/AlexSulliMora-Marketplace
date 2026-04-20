#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# ///
"""PreToolUse hook: inject style preferences into Agent tool dispatches.

When the Agent tool is called with a subagent_type that matches a known
reviewer or paper-pipeline creator agent, prepend the relevant
preferences-file contents to the prompt field of tool_input. The review
cascade then scores the dispatched agent under the preferences the user
configured in ${CLAUDE_PLUGIN_ROOT}/preferences/.

Fails silently on any error (pass-through), so a broken hook never blocks a
tool call — agents fall back to reading their preferences file directly per
the pointer in their body.
"""

import json
import sys
from pathlib import Path


# Mapping from subagent_type → list of preference filenames (relative to
# the plugin's preferences/ directory). Reviewer agents get one file each;
# paper-pipeline creator agents get multiple (writing + structure, plus
# presentation-style for the presentation-builder).
AGENT_PREFS: dict[str, list[str]] = {
    # reviewers
    "writing-reviewer":      ["writing-style.md"],
    "structure-reviewer":    ["structure-style.md"],
    "math-reviewer":         ["math-style.md"],
    "factual-reviewer":      ["factual-style.md"],
    "consistency-reviewer":  ["consistency-style.md"],
    "presentation-reviewer": ["presentation-style.md"],
    "simplicity-reviewer":   ["simplicity-style.md"],
    "code-reviewer":         ["code-style.md"],
    "adversarial-reviewer":  ["adversarial-style.md"],
    # paper-pipeline creators
    "paper-summarizer":      ["writing-style.md", "structure-style.md"],
    "extension-proposer":    ["writing-style.md", "structure-style.md"],
    "presentation-builder":  ["writing-style.md", "structure-style.md", "presentation-style.md"],
}


def plugin_preferences_dir() -> Path:
    """Resolve the preferences directory relative to this hook file.

    The hook lives at <plugin-root>/hooks/inject-preferences.py. The
    preferences directory is at <plugin-root>/preferences/. Resolving
    relative to __file__ makes the hook location-agnostic — it works
    whether the plugin is installed under ~/.claude/plugins/, referenced
    from a marketplace directory, or anywhere else.
    """
    return Path(__file__).resolve().parent.parent / "preferences"


def build_injection_prefix(subagent_type: str, prefs_dir: Path) -> str | None:
    """Build the preference prefix to prepend to the tool_input prompt.

    Returns None if no preference files exist for the agent or the
    directory is missing.
    """
    pref_files = AGENT_PREFS.get(subagent_type)
    if not pref_files:
        return None

    blocks: list[str] = []
    for fname in pref_files:
        path = prefs_dir / fname
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        blocks.append(f"## Injected preferences — {fname}\n\n{content}")

    if not blocks:
        return None

    return "\n\n---\n\n".join(blocks) + "\n\n---\n\n# Your task\n\n"


def main() -> None:
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        return

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})

    if tool_name != "Agent":
        return

    subagent_type = tool_input.get("subagent_type", "")
    if subagent_type not in AGENT_PREFS:
        return

    prefs_dir = plugin_preferences_dir()
    if not prefs_dir.exists():
        return

    prefix = build_injection_prefix(subagent_type, prefs_dir)
    if prefix is None:
        return

    updated_input = dict(tool_input)
    updated_input["prompt"] = prefix + tool_input.get("prompt", "")

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": (
                f"Injected preferences for {subagent_type} from CASM-tools"
            ),
            "updatedInput": updated_input,
        }
    }
    print(json.dumps(output))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Fail-safe: never block a tool call on hook error.
        pass

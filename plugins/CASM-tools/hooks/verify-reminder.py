#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# ///
"""PostToolUse hook: reminds to verify Quarto compilation after editing .qmd files.

Triggers on Write|Edit tool calls that modify .qmd files in paper-extension/ directories.
Non-blocking — outputs a reminder to stderr and exits 0.
Throttled to one reminder per file per 60 seconds to avoid spam.
"""

import json
import sys
import os
import time
import hashlib
from pathlib import Path


THROTTLE_SECONDS = 60


def get_project_hash():
    """Generate a hash from the current working directory."""
    cwd = os.getcwd()
    return hashlib.md5(cwd.encode()).hexdigest()[:12]


def get_cache_path():
    """Get path to throttle cache."""
    home = Path.home()
    session_dir = home / ".claude" / "sessions" / get_project_hash()
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir / "verify-reminder-cache.json"


def main():
    try:
        input_data = json.loads(sys.stdin.read())
        tool_input = input_data.get("tool_input", {})

        # Get the file path being edited/written
        file_path = tool_input.get("file_path", "")

        # Only trigger for .qmd files in paper-extension directories
        if not file_path.endswith(".qmd"):
            sys.exit(0)

        if "paper-extension" not in file_path:
            sys.exit(0)

        # Skip files in logs directories (these are intermediate versions)
        basename_dir = os.path.basename(os.path.dirname(file_path))
        if basename_dir.endswith("-logs"):
            sys.exit(0)

        # Throttle: check if we recently reminded about this file
        cache_path = get_cache_path()
        cache = {}
        if cache_path.exists():
            with open(cache_path) as f:
                cache = json.load(f)

        now = time.time()
        last_reminder = cache.get(file_path, 0)

        if now - last_reminder < THROTTLE_SECONDS:
            sys.exit(0)

        # Update cache
        cache[file_path] = now
        with open(cache_path, "w") as f:
            json.dump(cache, f)

        # Non-blocking reminder
        filename = os.path.basename(file_path)
        print(
            f"Reminder: {filename} was modified. "
            f"Run `quarto render {file_path}` to verify compilation before finalizing.",
            file=sys.stderr,
        )
        sys.exit(0)

    except Exception:
        # Fail-safe: never block
        sys.exit(0)


if __name__ == "__main__":
    main()

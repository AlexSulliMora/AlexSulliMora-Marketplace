#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# ///
"""Stop hook: reminds to update session log after N responses without an update.

Tracks the number of Claude responses since the last session log modification.
After REMIND_THRESHOLD responses, outputs a non-blocking reminder.
After BLOCK_THRESHOLD responses, blocks until the session log is updated.

State is stored per-project in ~/.claude/sessions/[project_hash]/.
"""

import json
import sys
import os
import hashlib
from pathlib import Path


REMIND_THRESHOLD = 10
BLOCK_THRESHOLD = 15


def get_project_hash():
    """Generate a hash from the current working directory."""
    cwd = os.getcwd()
    return hashlib.md5(cwd.encode()).hexdigest()[:12]


def get_state_path():
    """Get path to state file."""
    home = Path.home()
    session_dir = home / ".claude" / "sessions" / get_project_hash()
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir / "session-log-reminder-state.json"


def find_latest_log(project_dir):
    """Find the most recently modified session log in any paper-extension/session-logs/ dir."""
    latest_path = None
    latest_mtime = 0

    for root, dirs, files in os.walk(project_dir):
        # Look for session-logs directories inside paper-extension directories
        if os.path.basename(root) == "session-logs" and "paper-extension" in root:
            for f in files:
                if f.endswith(".md"):
                    fpath = os.path.join(root, f)
                    mtime = os.path.getmtime(fpath)
                    if mtime > latest_mtime:
                        latest_mtime = mtime
                        latest_path = fpath

    return latest_path, latest_mtime


def main():
    try:
        state_path = get_state_path()
        project_dir = os.getcwd()

        # Load state
        state = {"counter": 0, "last_mtime": 0.0, "reminded": False}
        if state_path.exists():
            with open(state_path) as f:
                state = json.load(f)

        # Check for session log updates
        log_path, current_mtime = find_latest_log(project_dir)

        if current_mtime > state["last_mtime"]:
            # Log was updated — reset counter
            state["counter"] = 0
            state["last_mtime"] = current_mtime
            state["reminded"] = False
        else:
            state["counter"] += 1

        # Save state
        with open(state_path, "w") as f:
            json.dump(state, f)

        # Check thresholds
        if state["counter"] >= BLOCK_THRESHOLD:
            if log_path:
                reason = (
                    f"Session log has not been updated in {state['counter']} responses. "
                    f"Update the session log before continuing: {log_path}"
                )
            else:
                reason = (
                    f"No session log found after {state['counter']} responses. "
                    "If running a pipeline stage, create one in paper-extension/session-logs/ "
                    "using the session log template."
                )
            print(json.dumps({"decision": "block", "reason": reason}))
            sys.exit(2)

        elif state["counter"] >= REMIND_THRESHOLD and not state["reminded"]:
            state["reminded"] = True
            with open(state_path, "w") as f:
                json.dump(state, f)

            if log_path:
                msg = f"Reminder: session log has not been updated in {state['counter']} responses. Consider updating: {log_path}"
            else:
                msg = "Reminder: no session log found. If running a pipeline stage, consider creating one."
            print(msg, file=sys.stderr)

        # Allow
        sys.exit(0)

    except Exception:
        # Fail-safe: never block on errors
        sys.exit(0)


if __name__ == "__main__":
    main()

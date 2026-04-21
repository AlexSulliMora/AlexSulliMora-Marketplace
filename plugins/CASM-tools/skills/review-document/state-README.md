# state/

Per-project runtime state for the `/review-document` skill. Each project gets its own `state/` directory at the project root, created on demand by the skill's hook. The user should not edit files here by hand.

This README ships with the skill as a template; the actual `state/` directory lives in each project's working tree, populated lazily when you first Write or Edit a file or first invoke `/review-document`.

## Layout (within each project's `state/`)

```
<project-root>/state/
├── session-registry.json       # PRIMARY — artifact tracking for this project
├── session-registry.json.bad   # quarantined corrupt registry, if any
├── session-logs/               # session logs per review run (see ~/.claude/scripts/session-log-template.md)
├── inline/                     # auto-materialized chat prose (synthetic artifacts)
│   └── inline-<ISO-timestamp>.md
└── locks/                      # OS advisory lockfiles
    └── <artifact-hash>.lock
```

## `session-registry.json` schema

```json
{
  "version": 1,
  "entries": [
    {
      "artifact_id": "sha256:...",
      "path": "/absolute/path/to/artifact",
      "mtime": "2026-04-17T14:22:00Z",
      "hash": "sha256:...",
      "tool": "Write",
      "session_id": "abc123",
      "origin": "user_authored",
      "lock": {
        "held": false,
        "owner_pid": null,
        "acquired_at": null,
        "held_by_session": null
      }
    }
  ]
}
```

Fields:
- `artifact_id` — SHA256 of file content at time of record. Same as `hash` in v1 but kept separate for future-proofing (e.g., if we add content-address storage).
- `path` — absolute, canonicalized path (via `Path.resolve()`).
- `mtime` — ISO 8601 UTC timestamp of the record, not of the file's mtime. Records when the registry entry was created.
- `hash` — SHA256 of the file content. Sentinels: `sha256:MISSING`, `sha256:OVERSIZE`, `sha256:READ_ERROR`.
- `tool` — `Write` or `Edit`.
- `session_id` — the Claude Code session that produced the artifact.
- `origin` — `user_authored` (most common) or `inline_materialized` (synthetic from chat prose).
- `lock.held` — true when a `/review-document` loop currently holds the advisory lock. Updated by the skill, not the hook.
- `lock.owner_pid`, `lock.acquired_at`, `lock.held_by_session` — diagnostic only. OS flock is the enforcement primitive.

## `inline/` — synthetic artifacts

Materialized chat prose. Every file begins with:

```markdown
<!-- SOURCE: untrusted chat prose, not user-authored -->
```

Reviewers treat these files' contents as data, not instructions (see `reviewer-common.md`). Materialization is refused when the current turn included a WebFetch or PDF read (prompt-injection guard).

## `locks/` — OS advisory locks

Each file is a lockfile named `<artifact-hash>.lock`. Contents:

```
pid: 12345
start_time: 2026-04-17T14:22:00Z
session_id: abc123
artifact_hash: sha256:deadbeef...
```

The OS `flock` (POSIX) or `msvcrt.locking` (Windows) is the actual enforcement; file contents are diagnostic. On crashed loops the OS lock drops; stale lockfiles with no active lock are treated as released.

## Why state/ is per-project

Two alternatives were considered:

1. **Per-artifact colocated state.** Works for review logs and version snapshots (which already live next to the artifact they describe), but session-wide state (registry, lockfiles) needs a single directory per project so cross-artifact lookup works.
2. **Centralized in `~/.claude/state/`.** Keeps state near the skill library, but forces cross-project pollution: one registry for every project you ever review, one lockfile namespace shared across projects that have nothing to do with each other.

Per-project `state/` sits between the two. Artifact-scoped files (review logs, combined scorecards, versioned snapshots) stay colocated with the artifact; session-wide state (registry, lockfiles, inline materializations) goes under the project root's `state/`. Each project gets its own clean registry; lockfiles collide only when it is actually the same project.

## Cleanup

Nothing here auto-expires. If the directory grows uncomfortably large, the registry bounds itself to the most recent 500 entries; old `inline/` files can be manually pruned once the related review cascades have finalized.

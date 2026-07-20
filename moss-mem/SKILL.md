---
name: moss-mem
description: Use when project work must persist across agent sessions, including starting or updating tasks, recovering context, searching prior work, capturing summaries, compacting history, validating handoffs, or completing a task.
version: "5.0.0"
---

# moss-mem — Project memory across sessions

## Overview

`MEMORY.md` and `.moss-mem/` are the source of truth. Generated files under
`.moss-mem/index-cache/` accelerate local retrieval and can always be rebuilt.
The skill uses Python's standard library only.

## Quick Dispatch

| Intent | Command |
|---|---|
| Show current task | `python3 {base}/scripts/memory_manager.py state show` |
| Set state | `python3 {base}/scripts/memory_manager.py state set current_task="repair login" next_step="inspect auth.py" status="🔧"` |
| Commit snapshot | `python3 {base}/scripts/memory_manager.py state commit -m "auth handoff"` |
| Add note | `python3 {base}/scripts/memory_manager.py state note "found refresh race"` |
| Build index | `python3 {base}/scripts/memory_manager.py knowledge-index` |
| Search memory | `python3 {base}/scripts/memory_manager.py memory-search "refresh race" --limit 10` |
| Validate | `python3 {base}/scripts/memory_manager.py knowledge-check --strict` |
| Compact | `python3 {base}/scripts/memory_manager.py state compact --dry-run` |

`{base}` is this skill's installation directory. All commands are local and
require no third-party package.

## Storage And Ownership

`MEMORY.md` is the project pointer and contract. `state` owns writes to it and
`.moss-mem/tasks/`; summary capture owns `.moss-mem/summaries/`; `knowledge-index`
owns generated `.moss-mem/index-cache/`. The index cache is disposable: never
hand-edit it or treat it as source data. `.harness/` is harness-owned and is
never read or written by moss-mem. Project documents and `AGENTS.md` remain
external, read-only context.

## Local Index And Search

Build or rebuild the deterministic Markdown index with:

```bash
python3 {base}/scripts/memory_manager.py knowledge-index
```

Search always uses the local command:

```bash
python3 {base}/scripts/memory_manager.py memory-search "query" --limit 10
```

The command ranks exact and token matches from `MEMORY.md`, active and archived
task files, and summaries. If the index is missing, corrupt, or stale it first
attempts one `knowledge-index` rebuild. Only when rebuilding fails or the
rebuilt index still cannot load does it emit `[INDEX-FALLBACK]` and search
source Markdown directly. Do not edit generated files.
`knowledge-check [--strict]` validates paths and index layout.

## State Operations

`state set k=v ...` is the only field-assignment verb; aliases `start`, `update`,
`complete`, `show`, `add-note`, and `init` remain supported. Examples:

```bash
python3 {base}/scripts/memory_manager.py state init
python3 {base}/scripts/memory_manager.py state show
python3 {base}/scripts/memory_manager.py state set current_task="fix auth" next_step="inspect auth.py" status="🔧"
python3 {base}/scripts/memory_manager.py state commit -m "auth handoff"
python3 {base}/scripts/memory_manager.py state note "found refresh race"
python3 {base}/scripts/memory_manager.py state validate --fix
```

The task record fields are `current_task` (string), `next_step` (string),
`status` (`🔧`, `✅`, or `❌`), `last_action`, `key_decisions` (list),
`landmines` (list), and auto-filled `created` ISO timestamp.

> **P9 trap:** `key_decisions`, `last_action`, or `landmines` set before the
> first `state commit` for a task land in the scratchpad, not its task file.
> Commit first, then set those handoff fields, and verify with `state show`.

## Summary Capture

Capture harness or session summaries as Markdown:

```bash
python3 {base}/scripts/memory_manager.py summary-capture \
  -t "topic" -s "summary" --source codex-harness \
  --decisions "decision" -n "next step" --related "file.py"
```

Summaries are stored under `.moss-mem/summaries/` and become searchable after
`knowledge-index`.

## Compaction

Preview, then explicitly confirm archival of older task files:

```bash
python3 {base}/scripts/memory_manager.py state compact --dry-run
python3 {base}/scripts/memory_manager.py state compact --strategy archive-summary --keep-recent 10 --yes
```

`archive-summary` keeps Description, Next Step, Key Decisions, and Landmines;
`archive-full` preserves the complete body. The command normally shows a STOP
confirmation; `--yes` is required for non-interactive runs. After moving more
than five tasks, run `knowledge-check --strict`, search three historical terms
with `memory-search`, rebuild the index, and run `state show` to confirm the
active pointer. If a key term disappears, stop and rerun with `archive-full`.

## Handoff Protocol

Use these four gated steps at session end:

1. Run `state validate`. Exit 0 proceeds to Step 4; exit 1 proceeds to Step 2.
2. Run `state validate --fix`, then validate again. Exit 0 proceeds to Step 4.
3. Set `last_action`, `key_decisions`, and `landmines`; run `state show` and
   verify all three are filled, repeating as needed.
4. Set `status="✅"`, run `state commit -m "<handoff summary>"`, then run
   `state show` and verify the pointer and status.

Step 3 is a checkpoint: show drafted decisions and landmines before writing.

## If-Then Fallbacks

| Trigger | Response |
|---|---|
| Missing `MEMORY.md` | Run `state init`, then commit a task. |
| Stale `.edit_lock` | Run `recover`; if still stale, remove the lock with the platform command and validate. |
| Search index missing/corrupt/stale | Attempt one `knowledge-index` rebuild; only if it fails or the rebuilt index still cannot load, continue with `[INDEX-FALLBACK]` source search. |
| Empty search | Widen the query and search source Markdown directly. |
| Incomplete handoff fields | Run `state validate --fix`, then set remaining fields and validate. |
| Strict layout check fails | Fix paths or rebuild with `knowledge-index`; record unresolved issues as landmines. |
| Compact write fails | Source file remains in place; fix disk/permissions and rerun. |

## Anti-Patterns / Blacklist

- Treat generated index files as authoritative or hand-edit them.
- Store state outside `MEMORY.md` and `.moss-mem/`.
- Modify project-owned `AGENTS.md`, docs, or harness session files.
- Skip validation gates or silently compact without confirmation.
- Block state writes because search/index validation failed; use fallback mode.
- Set handoff fields before the first task commit (the P9 trap).

## File Formats

`MEMORY.md` contains the strict sections Meta, 状态机, 下一步指令, 雷区与技术契约,
and 已归档任务, plus a free-form scratchpad. Task files under
`.moss-mem/tasks/` contain Description, Next Step, Status, Last Action,
Key Decisions, Landmines, and Created. Summaries are Markdown records under
`.moss-mem/summaries/`.

## First-Time Setup

```bash
python3 {base}/scripts/memory_manager.py state init
python3 {base}/scripts/memory_manager.py knowledge-check --strict
python3 {base}/scripts/memory_manager.py knowledge-index
```

## Platform Notes

| Operation | Unix (macOS / Linux / Git Bash) | Windows cmd | Windows PowerShell |
|---|---|---|---|
| Python | `python3 {base}/scripts/memory_manager.py …` | `python {base}\scripts\memory_manager.py …` | `python {base}\scripts\memory_manager.py …` |
| Search text | `python3 {base}/scripts/memory_manager.py memory-search "query"` | `python {base}\scripts\memory_manager.py memory-search "query"` | `python {base}\scripts\memory_manager.py memory-search "query"` |
| Remove lock | `rm .moss-mem/tasks/.edit_lock` | `del .moss-mem\tasks\.edit_lock` | `Remove-Item .moss-mem\tasks\.edit_lock` |
| Force-kill | `kill -9 <pid>` | `taskkill /F /PID <pid>` | `Stop-Process -Id <pid> -Force` |
| List directory | `ls` | `dir` | `Get-ChildItem` |

Python 3.9+ standard library is the only runtime requirement. The manager
handles UTF-8 console output and ASCII fallbacks on legacy terminals.

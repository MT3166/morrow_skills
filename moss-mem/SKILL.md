---
name: moss-mem
description: >-
  Project memory across coding-agent sessions using only MEMORY.md + .moss-mem/
  and a Python-stdlib local index (no external memory services). Use when the
  user starts/updates/completes a task, asks "where am I", needs handoff,
  searches prior work, captures a session summary, rebuilds the memory index,
  runs memory-search, compacts task/archive/summary history, cleans long-term
  MD growth, or validates handoff fields. Triggers: start task, update task,
  complete task, handoff, where am I, show memory, search memory, memory-search,
  knowledge-index, knowledge-check, compact memory, compact archive, compact
  summaries, multi-scope compact, MD cleanup, lifecycle compact, add note,
  summary capture, threshold nudge.
version: "6.0.0"
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
| Compact tasks | `python3 {base}/scripts/memory_manager.py state compact --scope tasks --dry-run` |
| Compact archive / summaries / all | `python3 {base}/scripts/memory_manager.py state compact --scope archive|summaries|all --dry-run` |

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

Task record schema:

| Field | Type | Required | Default | Purpose |
|---|---|---|---|---|
| `current_task` | string | optional | `(待补)` | Current task description. |
| `next_step` | string | optional | `等待下一步指令` | Next actionable handoff step. |
| `status` | enum | required | `🔧` | Task state: `🔧 In Progress`, `✅ Completed`, or `❌ Blocked`. |
| `last_action` | string | optional | `<!-- pending -->` | Most recent completed action. |
| `key_decisions` | list[string] | optional | `<!-- pending -->` | Decisions that constrain follow-up work. |
| `landmines` | list[string] | optional | `<!-- none -->` | Risks, hazards, or unresolved constraints. |
| `created` | ISO timestamp | auto | auto | Task creation time. |

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

## Compaction And Long-Term MD Lifecycle

Long-running projects grow Markdown in three hot layers. Compact is **passive
nudge + active confirm** — never silent auto-delete.

| Layer | Path | Passive nudge default | Active compact |
|---|---|---|---|
| Active tasks | `.moss-mem/tasks/*.md` | >30 files after commit/complete | `--scope tasks` (default) |
| Archive | `.moss-mem/tasks/archive/**/*.md` | >50 files after commit/complete/summary-capture | `--scope archive` secondary summary |
| Summaries | `.moss-mem/summaries/*.md` (non-digest) | >30 files after summary-capture | `--scope summaries` → monthly `digest-YYYY-MM.md` |

```bash
# Preview (always first)
python3 {base}/scripts/memory_manager.py state compact --scope tasks --dry-run
python3 {base}/scripts/memory_manager.py state compact --scope archive --dry-run
python3 {base}/scripts/memory_manager.py state compact --scope summaries --dry-run
python3 {base}/scripts/memory_manager.py state compact --scope all --dry-run

# Execute after 🛑 STOP confirm (or --yes for non-interactive)
python3 {base}/scripts/memory_manager.py state compact --scope all --strategy archive-summary --keep-recent 10 --yes
```

### Scope behavior

| `--scope` | Action |
|---|---|
| `tasks` | Move older active tasks into `tasks/archive/YYYY/`; `archive-summary` keeps Description / Next Step / Key Decisions / Landmines; `archive-full` keeps full body |
| `archive` | Re-summarize older archive bodies in place (does not delete files). Newest `--keep-recent` left untouched |
| `summaries` | Merge older non-digest summaries into `summaries/digest-YYYY-MM.md` (Decisions + Next Step + topic blocks). Originals removed only after digest write succeeds |
| `all` | Run tasks → archive → summaries in order under one confirmation |

### Passive nudge

`check_compact_threshold` runs after `state commit`, `complete` / `status="✅"`,
and `summary-capture`. It prints 🛑 STOP with the exact `state compact --scope … --dry-run`
command for each exceeded layer. **Nudge ≠ permission to delete or auto-compact.**

### Verify after compact

1. `knowledge-index`
2. `knowledge-check --strict`
3. `memory-search` on ≥3 historical key terms (e.g. past Key Decisions)
4. `state show` (active pointer intact)

🔴 CHECKPOINT: if a key term disappears, stop. For tasks/archive re-run with
`--strategy archive-full`; for summaries restore the pre-merge file from VCS
and do not re-merge that batch.

## Handoff Protocol

Use these four gated steps at session end:

1. Run `state validate`. Exit 0 proceeds to Step 4; exit 1 proceeds to Step 2.
2. Run `state validate --fix`, then validate again. Exit 0 proceeds to Step 4.
3. 🔴 CHECKPOINT — draft `last_action`, `key_decisions`, and `landmines`, show
   the user, then `state set` them; run `state show` and verify all three are
   filled, repeating as needed.
4. 🛑 STOP — confirm with the user, then run
   `state set status="✅" current_task="<handoff summary>"` once (or legacy
   `complete -d "<handoff summary>"`). This completes and archives the current
   task; **do not** chain `state commit` after it (`status="✅"` maps to
   complete/archive; `state commit` starts a **new** task file). Verify
   `MEMORY.md` reports `✅ Completed` and that an archive file appears in
   `.moss-mem/tasks/archive/` (with a completion record in
   `.moss-mem/tasks/MEMORY_ARCHIVE.md`). Start a new task with a separate
   `state commit` only after this handoff is complete.

## If-Then Fallbacks

Use this table after a failed gate. Apply the first response once; if the same
trigger remains, take the fallback and continue in file-only / index-fallback
mode rather than blocking state writes.

| Trigger | First response | Fallback if still failing |
|---|---|---|
| Missing `MEMORY.md` | `state init` (or first `state set` / `state commit` — both auto-init) | Create `MEMORY.md` pointer manually after `state commit -m "…"`, then `state show` |
| Stale `.edit_lock` after crash | `python3 {base}/scripts/memory_manager.py recover` | Remove `.moss-mem/tasks/.edit_lock` with the platform command, then `state validate --fix` |
| Search index missing / corrupt / stale | One `knowledge-index` rebuild, then retry `memory-search` | Continue with `[INDEX-FALLBACK]` source Markdown scan; mark active task `[INDEX-STALE]`; do not block handoff writes |
| Empty search results | Widen query tokens / raise `--limit`, rerun `memory-search` | `knowledge-index` then search again; if still empty, note "no hit" and proceed with `state show` context only |
| Incomplete handoff fields | `state validate --fix` | Set remaining `last_action` / `key_decisions` / `landmines` via `state set`, then `state validate` |
| Strict layout check fails | Fix missing paths or run `knowledge-index` | Non-strict `knowledge-check`; record layout issues as a task landmine; continue |
| Compact write fails (disk / permission) | Abort further moves — source files stay in place | 🛑 STOP, free disk / fix permissions, re-run the same `state compact --scope …` args |
| Key term missing after tasks/archive compact | 🔴 CHECKPOINT — stop using archive-summary for that set | Re-run with `--strategy archive-full`, then `knowledge-index` + `memory-search` spot-check |
| Key term missing after summaries digest merge | 🔴 CHECKPOINT — stop further merges for that month | Restore originals from VCS/backup; re-index; optional smaller `--keep-recent` batch |
| `--scope all` fails mid-sequence | Stop remaining scopes; report which scope failed | Fix the failing scope alone (`--scope tasks|archive|summaries`), then resume others |
| Passive nudge after summary-capture / commit | Show dry-run command only — do not compact yet | Ask user; on yes run `state compact --scope <layer> --dry-run` then confirmed execute |

## Anti-Patterns / Blacklist

| Anti-pattern | Required alternative |
|---|---|
| Hand-edit or treat `.moss-mem/index-cache/*` as source of truth | Rebuild with `knowledge-index`; only `MEMORY.md` / tasks / summaries are authoritative |
| Call external memory services (e.g. mempalace, vector DBs, MCP memory servers) for moss-mem search | Use `memory-search` / local Markdown only — this skill is stdlib + files |
| Store moss-mem state outside `MEMORY.md` and `.moss-mem/` | Keep all task / summary / archive / lock / index under those paths |
| Create or rewrite project `AGENTS.md`, `docs/`, or `.harness/sessions/*` as part of moss-mem | Read external docs only if present; harness owns `.harness/` |
| Skip `state validate` gates or silently compact without 🛑 / `--yes` | Always validate before complete; compact only after explicit confirm |
| Block `state set` / handoff writes because index/search failed | Finish state change in file-only mode; rebuild index later |
| Set `key_decisions` / `last_action` / `landmines` before the first `state commit` for a task (P9) | `state commit -m "…"` first, then set handoff fields, verify with `state show` |
| Chain `state set status="✅"` with `state commit -m "…"` for handoff | Complete archives; commit starts a **new** task. Verify via `MEMORY.md` + `.moss-mem/tasks/archive/` (no `state show --archived`) |
| Treat threshold nudge after commit/complete/summary-capture as auto-compact or delete permission | Nudge is 🛑 only; user must run `state compact --scope …` explicitly after dry-run |
| Hand-delete old `summaries/*.md` or archive files to "clean up" | Use `state compact --scope summaries|archive --dry-run` then confirm; digests preserve Decisions |
| Hand-write files under `.moss-mem/tasks/archive/` | Archive tree is owned by `state compact` / complete; restore by copying back to `tasks/` if needed |
| Compact without post-check `memory-search` on key decisions | Always re-index + spot-search ≥3 historical terms before declaring cleanup done |
| Use `--scope all --yes` on first try in a large repo | Prefer per-scope dry-run first; `--scope all` only after previews look right |

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

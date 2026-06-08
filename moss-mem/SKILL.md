---
name: moss-mem
description: >-
  Project memory that survives across coding-agent sessions. **`.moss-mem/`**
  holds the cross-session project state (task handoff, key decisions,
  landmines, generated index cache). Writes always go to `.moss-mem/`; reads
  route through the `mempalace search` CLI, falling back to file/grep. Single
  declarative `state set/show/commit` API; legacy `start`/`update`/`complete`
  remain as aliases. Triggers: start task, update task, complete task, handoff,
  where am I, show memory, search memory, add note, knowledge init/index/check.
version: "4.0.0"
---

# moss-mem — Project memory across sessions

## TL;DR

moss-mem owns **`.moss-mem/`** (project state, persistent, cross-session). It
does not own session-local state — that lives in `.harness/sessions/<id>/` and
is the harness's responsibility, not moss-mem's.

- **Write**: always to `.moss-mem/`. The file is the system of record.
- **Read**: semantic search via the `mempalace search` CLI; fall back to file/grep.
- **API**: declarative `state set current_task="…" next_step="…"` — one verb
  covers start/update/complete. Aliases (`start`/`update`/`complete`) keep
  existing scripts working.

```
.moss-mem/                                    .harness/sessions/<id>/
──────────────────                            ─────────────────────────
project state  ◀── moss-mem owns              session state ◀── harness owns
cross-session                                 per-session
persistent                                    ephemeral
```

**Rule of thumb**: if the next session needs it, write to `.moss-mem/`. If only
this session needs it, leave it in `.harness/`.

## Quick Dispatch

> **Placeholders** — `{base}` = the moss-mem installation directory
> (`~/.claude/skills/moss-mem` in Claude Code, or wherever the skill was
> installed). `<project>` = the `mempalace init` wing name (typically your
> repo's directory name; e.g. `mempalace init . --wing morrow_skills`). All
> commands below assume `{base}` is expanded.

| Intent | Command | Notes |
|---|---|---|
| Where am I? | `python3 {base}/scripts/memory_manager.py state show` | 1 step; reads MEMORY.md + active task file |
| Set state | `python3 {base}/scripts/memory_manager.py state set current_task="…" next_step="…"` | Declarative, idempotent, 0 round-trips; missing keys use placeholders |
| Commit snapshot | `python3 {base}/scripts/memory_manager.py state commit -m "auth: 60% done"` | Writes task file + updates MEMORY.md pointer |
| Search memory | `mempalace search "…" --wing <project>` (CLI) → `grep -r "…" .moss-mem/` (file) | Degrade through 2 tiers |
| Add note | `python3 {base}/scripts/memory_manager.py state note "found race in token refresh"` | Timestamped scratchpad |
| Validate handoff | `python3 {base}/scripts/memory_manager.py state validate [--fix]` | Check handoff fields; `--fix` auto-fills from git |
| Init | `python3 {base}/scripts/memory_manager.py state init` | Create `.moss-mem/` + MEMORY.md |
| Regenerate index | `python3 {base}/scripts/memory_manager.py knowledge-index` | Rebuild `.moss-mem/index-cache/memory-index.md` |
| Check layout | `python3 {base}/scripts/memory_manager.py knowledge-check [--strict]` | Validate memory paths exist |
| **Legacy aliases** | `start` / `update` / `complete` / `show` / `add-note` / `init` | All remain functional; internally map to `state *` |

> ⚠️ **P9 trap — `state set key_decisions=…` on a non-existent task**:
> If you call `state set` with `key_decisions` / `last_action` / `landmines`
> **before any `state commit` for this task**, the call prints `✅ MEMORY.md
> updated` but does **not** create the task file. Your decisions land in the
> scratchpad, not in the task's handoff fields. Symptom: `state show` reads
> an older (or missing) task file and your decision is invisible.
> **Fix**: when a task needs handoff fields written, call `state commit -m
> "…"` first (creates the task file), then `state set key_decisions=…
> last_action=… landmines=…`. For routine progress updates with no handoff
> fields, plain `state set` is fine.

## Architecture

### State schema

The current task is a flat key-value record with this contract:

| Field | Type | Required | Default | Purpose |
|---|---|---|---|---|
| `current_task` | string | optional | `(待补)` | What the task aims to achieve |
| `next_step` | string | optional | `等待下一步指令` | Precise next action (file:line or function) |
| `status` | enum | yes | `🔧` | `🔧 In Progress` / `✅ Completed` / `❌ Blocked` |
| `last_action` | string | optional | `<!-- pending -->` | What was just done (file:line, concrete) |
| `key_decisions` | list[string] | optional | `<!-- pending -->` | Architectural choices + rationale (do not revert) |
| `landmines` | list[string] | optional | `<!-- none -->` | Fragile areas, known issues, avoid unless instructed |
| `created` | ISO timestamp | auto | — | Set on commit |

`state set k=v k2=v2` is the only mutating verb. The same call works for
"start a new task", "update progress", and "complete": you just set the fields
to their new values. There is no lifecycle event distinct from "the agent
called `state set`".

### Ownership boundary

| Path | Owned by | moss-mem behavior |
|---|---|---|
| `MEMORY.md` | moss-mem | Read/write only via `state *` commands |
| `.moss-mem/tasks/` | moss-mem | Read/write only via `state *` |
| `.moss-mem/summaries/` | moss-mem | Imported harness summaries; read/write via `summary-capture` |
| `.moss-mem/index-cache/` | moss-mem | Generated cache; never hand-edit |
| `.harness/sessions/<id>/` | harness | moss-mem never reads or writes here |
| `AGENTS.md` | project (external) | moss-mem treats as optional read-only context if present |
| Project docs / `docs/`, `ARCHITECTURE.md`, etc. | project (external) | moss-mem does not create, move, edit, or require them |

### Search & retrieval

Two tiers, in priority order. The first that works wins; the agent does not
need to try the other tier unless the first returns nothing.

1. **CLI** — `mempalace search "…" --wing <project> [--room=…] [--results=10]`
   - Hybrid cosine + BM25 (ChromaDB-backed)
2. **File** — `grep -r "…" MEMORY.md .moss-mem/`
   - Exact match only

For the full `mempalace` CLI surface (search/mine/sync/init/wake-up/...), see
[`references/mempalace-tools.md`](references/mempalace-tools.md). Live source
of truth: `mempalace instructions help`.

> **MCP status**: `mempalace-mcp` exists as a stdio launcher inside the
> `mempalace` package, but moss-mem does **not** depend on it. Reach for the
> CLI directly. The reference file lists MCP tool names for users who wire
> `mempalace-mcp` into their runtime; moss-mem does not require that wiring.

**Small-palace guard**: when `mempalace` is indexed against < ~50 source files
(typical for a fresh project), cosine scores cluster below 0.5 and BM25
dominates — but result-card templates / test fixtures can still rank above
real memory. If `mempalace search` returns:
- **0 results** → fall back to `grep -r "…" MEMORY.md .moss-mem/` (always)
- **top cosine < 0.5** AND **< 3 results** → fall back to `grep` and label
  the mempalace output as `low-confidence`
- **top cosine ≥ 0.5** OR **≥ 3 results** → mempalace output is trustworthy

When you `mine`, restrict scope so the palace never indexes HTML templates
or test fixtures:

```
mempalace mine .moss-mem/tasks/ .moss-mem/summaries/ --wing <project>
mempalace mine MEMORY.md --wing <project>
```

Avoid `mempalace mine .` (whole-repo mine) — it pulls in result cards,
READMEs, and test-prompts that drown real memory.

## Operations

### `state show` — read current state

```
python3 {base}/scripts/memory_manager.py state show
```

Prints the current task pointer (from `MEMORY.md`) and the active task file's
filled sections. **Stop here for "where am I?" / "what was I doing?"**
questions. Do not escalate to 6-step context recovery unless the user explicitly
asks for "full context" / "related past work" / "everything".

### `state set` — set fields (the only mutating verb)

```
python3 {base}/scripts/memory_manager.py state set current_task="<X>" next_step="<Y>" [status="🔧"|"✅"|"❌"] [last_action="…"] [key_decisions="…"] [landmines="…"]
```

**Auto-init**: if `MEMORY.md` doesn't exist, `state set` (and `state commit`) creates it automatically. A fresh project can call `state set current_task="first task"` as its very first command — no separate `state init` round-trip needed.

Field behavior:

| Flag | Omitted | `""` (empty) | Non-empty |
|---|---|---|---|
| `current_task` | leave unchanged | → `(待补)` | replace |
| `next_step` | leave unchanged | → `等待下一步指令` | replace |
| `last_action` | leave unchanged | → `<!-- pending -->` | replace |
| `key_decisions` | leave unchanged | → `<!-- pending -->` | replace |
| `landmines` | leave unchanged | → `<!-- none -->` | replace |
| `status` | leave unchanged | error | replace |

**Why one verb covers start/update/complete**: there is no "this is a new task"
event distinct from "the agent changed the fields." A fresh project can call
`state set current_task="first task"` and it works. A long-running task can
call `state set last_action="refactored auth"` and it works. The contract is
the same.

### `state commit` — snapshot to disk

```
python3 {base}/scripts/memory_manager.py state commit -m "<one-line summary>"
```

Writes a timestamped file under `.moss-mem/tasks/`, updates the `MEMORY.md`
pointer, and (in enhanced mode) mirrors to MemPalace. Use this when you have
made changes you want to preserve across sessions.

### `state note` — append to scratchpad

```
python3 {base}/scripts/memory_manager.py state note "<text>"
```

Appends a timestamped entry to the active task's scratchpad. Use for
session-local notes that don't justify a `commit`.

### `state validate [--fix]` — check handoff fields

```
python3 {base}/scripts/memory_manager.py state validate            # exit 0 = all filled
python3 {base}/scripts/memory_manager.py state validate --fix      # auto-fill from git
```

Exits 0 when `last_action`, `key_decisions`, and `landmines` are not
placeholders. Use before `complete` (see Handoff Protocol).

### `state init` — first-time setup

```
python3 {base}/scripts/memory_manager.py state init
```

Creates `MEMORY.md` and `.moss-mem/{tasks,summaries,index-cache}`. Does not
create `AGENTS.md`, `ARCHITECTURE.md`, or `docs/`.

### `summary-capture` — import harness summaries

```
python3 {base}/scripts/memory_manager.py summary-capture \
  -t "<topic>" -s "<summary>" --source codex-harness \
  --decisions "<key decisions>" -n "<next step>" --related "<file1,file2>"
```

Writes `.moss-mem/summaries/YYYYMMDD-HHMMSS-<topic>.md`. After capture, mine
into MemPalace with `mempalace mine .moss-mem/summaries/ --wing <project>`.

### `knowledge-index` / `knowledge-check` — index cache maintenance

```
python3 {base}/scripts/memory_manager.py knowledge-index     # regenerate .moss-mem/index-cache/memory-index.md
python3 {base}/scripts/memory_manager.py knowledge-check     # validate memory paths exist
```

`knowledge-index` is the only writer of `.moss-mem/index-cache/`. Never
hand-edit the generated index.

## Handoff Protocol

> ⚠️ Before following this protocol, ensure a task file exists (see the
> P9 trap note in Quick Dispatch above). If you only ever called `state set`
> without ever calling `state commit` for this task, the handoff fields will
> silently land in scratchpad, not in the task file. Run `state commit -m
> "…"` first if needed.

For session-end or task-completion handoffs, follow this 4-step flow. Each step
has a gate; never skip a gate.

```
Step 1: state validate
        Gate: exit 0 = handoff fields filled → proceed to Step 4
              exit 1 = fields incomplete → continue to Step 2

Step 2: state validate --fix
        Gate: re-run state validate
              exit 0 → proceed to Step 4
              exit 1 → continue to Step 3

Step 3: state set last_action="…" key_decisions="…" landmines="…"
        Gate: state show — verify the three fields are not placeholders
              filled → proceed to Step 4
              still pending → repeat Step 3 with remaining fields

Step 4: state set status="✅" && state commit -m "<handoff summary>"
        Gate: state show --archived — verify the task moved to archive
              MEMORY.md status is ✅ → handoff complete
```

🔴 Step 3 (writing `key_decisions` / `landmines`) is a **CHECKPOINT** — draft
the values, show the user, then write. 🛑 `complete` is destructive (moves the
file to archive) — confirm before running.

## Anti-Patterns / Blacklist

| Anti-pattern | Required alternative |
|---|---|
| Create, move, or edit `AGENTS.md` as part of moss-mem | Read it only if present; treat as agent-owned external context |
| Create root `docs/`, `ARCHITECTURE.md`, product specs as part of moss-mem | Keep moss-mem scoped to `MEMORY.md` and `.moss-mem/**` |
| Store moss-mem state outside `.moss-mem/` | All task/summary/archive/lock/index under `.moss-mem/` |
| Treat MemPalace as the source of truth | Files own state; MemPalace mirrors/searches them |
| Store decisions only in diary/KG/palace drawers | Record handoff decisions via `state set key_decisions="…"` |
| Run `mempalace_sync apply=true` / `delete_drawer` from memory | Preview first, then wait at the 🛑 STOP gate |
| Hand-edit generated `.moss-mem/index-cache/memory-index.md` | Run `knowledge-index` to regenerate |
| Skip handoff gates because a task looks small | Run `state validate`/`state validate --fix` before commit |
| Let MCP/CLI failures block writes | Degrade to file-only, finish the state change, mine/sync later |
| Read or write `.harness/sessions/<id>/` | That is harness territory, not moss-mem's |
| Wire `mempalace-mcp` as moss-mem's primary read/write path | Use `mempalace <subcmd>` CLI directly; MCP wiring is optional and adds a runtime dependency for no functional gain |
| Call `mempalace_diary_write` / `mempalace_kg_add` / `mempalace_create_tunnel` as if they were CLI subcommands | These are MCP tool names only; the CLI surface is `mempalace mine` / `sync` / `search` / `init` / `wake-up` — no `diary` / `kg` / `tunnel` subcommands exist |
| Call `state set key_decisions=…` before any `state commit` for the current task | The call prints ✅ but the handoff fields land in scratchpad, not the task file. Run `state commit -m "…"` first, then `state set key_decisions=…`. See P9 trap in Quick Dispatch |
| `mempalace mine .` (whole-repo mine) | Use scoped mine: `mempalace mine .moss-mem/tasks/ .moss-mem/summaries/ MEMORY.md --wing <project>`. Whole-repo mine pulls in result cards, READMEs, test fixtures that drown real memory in small palaces |

## If-Then Fallbacks

Use this table after a failed gate. Apply the first response once; if the same
trigger remains, take the fallback path and continue the lifecycle in file-only
mode rather than blocking.

| Trigger | First response | Fallback if still failing |
|---|---|---|
| `MEMORY.md` missing | `python3 {base}/scripts/memory_manager.py state init` | Create the task with `state commit -m "…"`, then add the current pointer to `MEMORY.md` manually |
| Stale `.edit_lock` after crash | `python3 {base}/scripts/memory_manager.py recover` | Remove `.moss-mem/tasks/.edit_lock` (Unix `rm`, Windows `del`), then `state validate --fix` |
| MCP tool missing or timeout | Use the `mempalace` CLI directly; MCP is not the primary path | File-only: `grep -r "…" .moss-mem/`; record `[SYNC-PENDING]` in the task note; `mempalace mine` later |
| `mempalace` CLI unavailable | Continue file-only after the Python command succeeds | Add note `[SYNC-PENDING] install/run mempalace`; mine `.moss-mem/` at handoff |
| Search returns empty | Widen query or `max_distance`; try CLI `mempalace search` | File search over `MEMORY.md` and `.moss-mem/`; re-mine relevant memory files |
| `mempalace search` returns low confidence (top cosine < 0.5 AND < 3 hits) | Switch to `grep -r "…" MEMORY.md .moss-mem/` and label mempalace output as `low-confidence` | Re-mine with `mempalace mine .moss-mem/tasks/ .moss-mem/summaries/ MEMORY.md --wing <project>` (scoped, not whole-repo) |
| `memory-index.md` stale | `knowledge-index` then `knowledge-check` | Search `MEMORY.md` and `.moss-mem/` directly; mark `[INDEX-STALE]` in the active task |
| Handoff fields incomplete | `state validate --fix` | Fill `last_action`/`key_decisions`/`landmines` via `state set`, then `state validate` |
| `mempalace_sync` preview shows stale drawers | 🛑 STOP and show the preview | Skip `apply=true`; verify with `mempalace_get_drawer` or file search before pruning later |
| `knowledge-check --strict` fails | Fix missing/stale memory paths or rerun `knowledge-init`/`knowledge-index` | Run non-strict `knowledge-check`; record layout issues as a task landmine; continue |

## State file formats

### `MEMORY.md`

```
## Meta [Strict]            — project identity, tech stack, last update
## 状态机 [Strict]           — current task pointer + status + last action
## 下一步指令 [Strict]        — next actionable step (file:line or function)
## 暂存与备忘区 [Free]        — free-form notes
## 雷区与技术契约 [Strict]    — append-only constraints
## 已归档任务 [Strict]        — archive index
```

### Task file (`.moss-mem/tasks/YYYYMMDD-HHMMSS_task.md`)

```
## Description       ← current_task
## Next Step         ← next_step
## Status            ← 🔧 | ✅ | ❌
## Last Action       ← last_action
## Key Decisions     ← key_decisions (do not revert)
## Landmines         ← landmines
## Created           ← ISO timestamp
```

## Harness boundary

moss-mem does not create, manage, or require `.harness/`. The harness owns:

- `.harness/sessions/<id>/` — per-session working state
- `.harness/hooks/`, `.harness/config.yaml` — harness internals
- Session lifecycle events (start, stop, compact)

When the user says "save this for next session", ask: will next session need it?
If yes, write to `.moss-mem/`. If only this session, leave it in `.harness/`.

## First-Time Setup

```bash
# 1. Initialize memory
python3 {base}/scripts/memory_manager.py state init

# 2. Install MemPalace CLI (optional — for semantic search)
pip install mempalace
mempalace init <project_dir> --yes
mempalace mine .moss-mem/ --wing <project_name>

# 3. (Optional) Wire mempalace-mcp into your coding runtime
#    Claude Code:  claude mcp add mempalace -- mempalace-mcp
#    Codex:        codex mcp add mempalace
#    Cursor et al: add to MCP configuration
#    Note: moss-mem does not require this. The CLI is the primary path.

# 4. Initial validation
python3 {base}/scripts/memory_manager.py knowledge-check
python3 {base}/scripts/memory_manager.py knowledge-index
mempalace mine .moss-mem/tasks/ --mode convos --extract general --wing <project_name>
mempalace mine .moss-mem/summaries/ --mode convos --extract general --wing <project_name>
```

## Platform Notes

| Operation | Unix (macOS / Linux / Git Bash) | Windows cmd | Windows PowerShell |
|---|---|---|---|
| Python | `python3 {base}/scripts/memory_manager.py …` | `python {base}\scripts\memory_manager.py …` | `python {base}\scripts\memory_manager.py …` |
| Search text | `grep -r "query" .moss-mem/` | `findstr /s "query" .moss-mem\*` | `Select-String -Path ".moss-mem\*" -Pattern "query"` |
| Remove file | `rm .moss-mem/tasks/.edit_lock` | `del .moss-mem\tasks\.edit_lock` | `Remove-Item .moss-mem\tasks\.edit_lock` |
| Force-kill | `kill -9 <pid>` | `taskkill /F /PID <pid>` | `Stop-Process -Id <pid> -Force` |
| List directory | `ls` | `dir` | `Get-ChildItem` |

`memory_manager.py` uses Python stdlib only. Forward slashes work on all
platforms; use backslashes only in native shell commands.

## Skill Integration

- **init skill**: after creating project structure, run `moss-mem state init` then `moss-mem knowledge-init`.
- **Any long task**: `state set current_task=… next_step=…` → work → `state validate` → `state commit`.
- **Cross-session recovery**: `moss-mem state show` (1 step) is enough for "where am I?". For "show me everything", escalate to `mempalace wake-up --wing <project>` (CLI).
- **Setup**: `pip install mempalace && mempalace init <dir> --yes && mempalace mine .moss-mem/ --wing <project>`. The `mempalace-mcp` binary is a stdio launcher inside the same package; wire it only if your runtime requires MCP, not for moss-mem itself.

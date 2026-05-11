---
name: moss-mem
description: "Project memory management for Claude Code sessions. Two-layer: MEMORY.md (file index) + MemPalace MCP (semantic search, knowledge graph, agent diary) with CLI fallback (mine, wake-up, repair). Triggers: init/start/update/complete task, search memory, link tasks, handoff/context switch."
triggers:
  - initialize memory
  - init memory
  - 新项目初始化记忆
  - start task
  - new task
  - begin task
  - 开始任务
  - update memory
  - update task
  - 进度更新
  - 更新记忆
  - complete task
  - finish task
  - 完成任务
  - add note
  - scratchpad
  - 笔记
  - check memory
  - read memory
  - 查看记忆
  - 当前状态
  - show task
  - show memory
  - 查看任务
  - 查看交接状态
  - search memory
  - find task
  - 搜索记忆
  - 找任务
  - 查找
  - link task
  - relate task
  - 关联任务
  - agent diary
  - session note
  - 会话笔记
  - handoff
  - 交接
  - 接力
  - context switch
  - mine memory
  - 挖掘记忆
  - wake up
  - 唤醒
version: "3.1"
---

# moss-mem — Project Memory Management

## TL;DR

Two-layer memory: **MEMORY.md** as always-available startup index + **MemPalace MCP** (semantic search, temporal KG, agent diary) with **CLI fallback** (mine, wake-up, repair). When MCP is unavailable, degrades to CLI. When both unavailable, file-only. Never blocked.

```
File Layer (system of record)    MCP Layer (primary runtime)       CLI Layer (fallback + maintenance)
  MEMORY.md ← startup pointer      mempalace_search  → semantic     mempalace search  → vector search
  MEMORY_TASKS/*.md ← tasks        mempalace_kg_*    → temporal KG  mempalace wake-up → context snapshot
  Script: memory_manager.py        mempalace_diary_* → agent diary  mempalace mine    → bulk ingest
                                   mempalace_*_tunnel → cross-wing  mempalace repair  → index maintenance
                                   mempalace_sync     → prune stale  mempalace status  → health overview
```

Setup: `pip install mempalace && mempalace init <dir> --yes && mempalace mine <dir> --wing <project> && claude mcp add mempalace -- mempalace-mcp`.

## Decision Tree

```
User intent → primary path (MCP) → fallback (CLI) → last resort (file/grep)

"start task X"
  python3 {base}/scripts/memory_manager.py start -d "X" -n "next step"
  → MCP: mempalace_check_duplicate → mempalace_add_drawer room:tasks
  → CLI: skip mirroring (batched later via mempalace mine)

"update progress"
  python3 {base}/scripts/memory_manager.py update -d "X" -n "Y" -s "🔧"
  → MCP: if -k/-m non-empty, mempalace_add_drawer room:decisions/landmines + mempalace_kg_add
  → CLI: skip mirroring

"complete task"
  check → check --fix → update -l/-k/-m → complete
  → MCP: mempalace_update_drawer → mempalace_sync
  → CLI: skip

"search memory" / "find tasks about X"
  MCP:   mempalace_search query="X" wing=<project> limit=10 → semantic, ranked
  CLI:   mempalace search "X" --wing <project>              → vector, ranked
  File:  grep -r "X" MEMORY_TASKS/                           → exact match only

"link X to Y"
  MCP:   mempalace_kg_add + mempalace_create_tunnel
  File:  append to task file ## Key Decisions

"diary"
  MCP:   mempalace_diary_read / mempalace_diary_write (AAAK)
  File:  moss-mem add-note "[DIARY] ..."

"what were we working on?" (context recovery)
  MCP:   show → diary_read → search → kg_query → traverse → synthesize
  CLI:   show → mempalace wake-up --wing <project>
  File:  show → grep MEMORY_TASKS/

"handoff"
  MCP:   check → check --fix → update -l/-k/-m → diary_write → complete → sync → start
  CLI:   check → check --fix → update -l/-k/-m → complete → mine → start
  File:  check → check --fix → update -l/-k/-m → complete → start

"mine memory"
  CLI:   mempalace mine MEMORY_TASKS/ --mode convos --extract general --wing <project>
  MCP:   n/a (bulk operation — use CLI)
```

## Prerequisites

- Python 3.8+ (stdlib only). Run from **project root** (where MEMORY.md lives).
- Script: `{base}/scripts/memory_manager.py` — `{base}` is the `Base directory for this skill:` line in invocation header.
- After `kill -9`: `rm MEMORY_TASKS/.edit_lock`.
- **MemPalace MCP** (primary): installed via `pip install mempalace`, initialized via `mempalace init <dir> --yes && mempalace mine <dir> --wing <project>`, registered via `claude mcp add mempalace -- mempalace-mcp`.
- **MemPalace CLI** (fallback): same binary — `mempalace --version` confirms availability.

### Authoritative References

These external sources stay current independently — prefer them over hardcoded instructions when in doubt:

| Resource | What it provides | When to use |
|----------|-----------------|-------------|
| `mempalace instructions init` | Latest init workflow | Setup troubleshooting |
| `mempalace instructions search` | Latest search guidance | Search syntax questions |
| `mempalace instructions mine` | Latest mining modes + flags | Mine configuration |
| `mempalace instructions status` | Latest status interpretation | Palace health check |
| `mempalace instructions help` | Full CLI reference | Discovery / unknown features |
| `mempalace_get_aaak_spec` (MCP) | Authoritative AAAK format spec | Diary entry format questions |
| `mempalace --help` | Top-level subcommand list | Quick refresh |

## Availability Detection

Check once per session:

```
1. Try mempalace_status (MCP tool) → success = enhanced mode
2. If MCP tool not found / timeout:
   Try mempalace --version (CLI) → success = cli-fallback mode
3. If neither available → file-only mode
```

In enhanced and cli-fallback modes, `mempalace instructions help` provides a current capability overview — use it when unsure about available subcommands.

| Mode | Search | KG | Diary | Mirroring | Context Recovery |
|------|--------|----|-------|-----------|-----------------|
| **enhanced** (MCP) | semantic | temporal graph | AAAK entries | real-time | multi-tool orchestration |
| **cli-fallback** | vector (CLI) | via extract general | scratchpad notes | batched (mine) | wake-up snapshot |
| **file-only** | grep | manual annotation | add-note [DIARY] | none | grep |

## Operations

### Task Lifecycle (file-based, always available)

**start**
```
python3 {base}/scripts/memory_manager.py start -d "Description" -n "Next step instruction"
```
Creates `MEMORY_TASKS/YYYYMMDD-HHMMSS_task.md`, updates MEMORY.md pointer. Status → 🔧.

Enhanced (MCP): `mempalace_check_duplicate` → `mempalace_add_drawer wing=<project> room=tasks`. Skip on failure.

**update**
```
python3 {base}/scripts/memory_manager.py update -d "Progress" -n "Next step" -s "🔧"
```

Handoff fields:
```
-l "Last action: refactored auth.py:login() — extracted token validation"
-k "JWT in httpOnly cookie, not localStorage — do not revert"
-m "auth.py:45-60 untested — do not modify until tests added"
```

| Flag | Omitted | `""` (empty) | Non-empty |
|------|---------|--------------|-----------|
| `-l` | Leave unchanged | → `<!-- pending -->` | Replace |
| `-k` | Leave unchanged | → `<!-- none -->` | Replace |
| `-m` | Leave unchanged | → `<!-- none -->` | Replace |

Enhanced (MCP): when `-k`/`-m` non-empty → `mempalace_add_drawer room:decisions` / `room:landmines` + `mempalace_kg_add` with `valid_from` timestamp. Skip on failure.

**complete**
```
python3 {base}/scripts/memory_manager.py complete -d "Completion description"
```
Archives → `MEMORY_TASKS/archive/`, appends to `MEMORY_ARCHIVE.md`, status → ✅.

Enhanced (MCP): `mempalace_update_drawer` (mark complete) → `mempalace_sync project_dir=<project> apply=true` (prune stale). Skip on failure.

### Meta Operations (file-based)

| Command | Python invocation | Purpose |
|---------|------------------|---------|
| **init** | `python3 {base}/scripts/memory_manager.py init` | Create MEMORY.md + MEMORY_TASKS/ |
| **show** | `python3 {base}/scripts/memory_manager.py show [--file <path>]` | Print current or archived task file |
| **add-note** | `python3 {base}/scripts/memory_manager.py add-note -n "Note"` | Timestamped scratchpad note |
| **check** | `python3 {base}/scripts/memory_manager.py check [--fix]` | Verify handoff; `--fix` auto-fills from git |
| **recover** | `python3 {base}/scripts/memory_manager.py recover` | Interrupt recovery: lock → completeness → git diff → git log → stash |

### Skill Invocation Mapping (--action args)

| Invocation | Python command |
|-----------|---------------|
| `--action init` | `init` |
| `--action start --description "X" --status "🔧"` | `start -d "X" -s "🔧"` |
| `--action start --description "X" --next "Y"` | `start -d "X" -n "Y"` |
| `--action update --description "X" --next "Y" --status "🔧"` | `update -d "X" -n "Y" -s "🔧"` |
| `--action complete --description "X"` | `complete -d "X"` |
| `--action add-note --note "X"` | `add-note -n "X"` |

## MCP Operations (primary path)

### search — Semantic search

```
mempalace_search query="<keywords>" wing=<project> [room=<room>] [limit=10] [max_distance=1.5]
```

- `limit` — results count (1-100, default 5)
- `max_distance` — cosine distance threshold (lower = stricter)
- `wing`/`room` — optional scope filters

Output:
```
## 🔍 MemPalace Search: "<query>" (wing=<project>, MCP)
| Score  | Content                                | Drawer   | Room      |
|--------|----------------------------------------|----------|-----------|
| 0.92   | Implemented JWT auth middleware in ...  | #a1b2c3  | decisions |
| 0.87   | Fixed token refresh race condition...  | #d4e5f6  | tasks     |

3 results (semantic, max_distance=1.5). Full content: mempalace_get_drawer drawer_id="#a1b2c3"
```

CLI fallback: `mempalace search "<query>" --wing <project>` (vector, not semantic).
File fallback: `grep -r "<query>" MEMORY_TASKS/ MEMORY_ARCHIVE.md` (exact match only).

### link — Temporal knowledge graph

```
1. Confirm: "Link 'rate-limiting' → relates_to → 'api-security'. OK?"
2. mempalace_kg_add subject="rate-limiting" predicate="relates_to" object="api-security"
   [valid_from="2026-05-11"] [source_drawer_id="<id>"]
3. mempalace_create_tunnel source_wing=<p> source_room=tasks
   target_wing=<p> target_room=tasks label="rate-limiting → api-security"
```

Output: `🔗 Link Created: rate-limiting —[relates_to]→ api-security. KG edge (temporal) + tunnel.`

Query: `mempalace_kg_query entity="rate-limiting" [as_of="2026-06-01"] [direction="both"]`
Invalidate: `mempalace_kg_invalidate subject="..." predicate="..." object="..."`

CLI fallback: not available (KG is MCP-only). File fallback: append `Related: X → Y (relates_to)` to `## Key Decisions`.

### diary — Agent session journal

```
Read:  mempalace_diary_read agent_name="claude" last_n=10 [wing=<project>]
Write: mempalace_diary_write agent_name="claude" entry="<AAAK>" topic="<topic>" [wing=<project>]
       → Draft entry, show user, confirm before writing.
```

Output (read):
```
## 📓 Agent Diary (last 10)
| Date       | Topic        | Key Decisions / Actions         | ★   |
|------------|-------------|---------------------------------|-----|
| 2026-05-11 | auth-module | JWT in httpOnly cookies         | ★★★ |
```

AAAK format (built-in; full spec via `mempalace_get_aaak_spec`):
```
SESSION:YYYY-MM-DD|topic_code|KEY.dec:summary|LANDMINE:area|★★★
```

| Scenario | AAAK Example |
|----------|-------------|
| Feature built | `SESSION:2026-05-11\|auth.module\|built.JWT.middleware\|KEY.dec:cookies.over.localStorage\|★★★` |
| Bug fixed | `SESSION:2026-05-11\|token.refresh\|fixed.race.condition\|LANDMINE:auth.py.L45-L60.untested\|★★★` |
| Decision made | `SESSION:2026-05-11\|api.design\|KEY.dec:REST.over.GraphQL\|*confident*\|★★☆` |
| Handoff | `SESSION:2026-05-11\|handoff\|completed.auth.module\|NEXT:test.login.flow\|★★★` |

Proactive triggers: after milestone, architectural decision, blocker, session end, non-obvious bug fix.

CLI fallback: `moss-mem add-note "[DIARY] <AAAK entry>"` (write) or read scratchpad `[DIARY]` entries (read).

### context — Rich context recovery

```
Step 1: moss-mem show                         ← current task pointer (always)
Step 2: mempalace_diary_read last_n=10        ← recent session notes
Step 3: mempalace_search query=<topic>         ← related past work
Step 4: mempalace_kg_query entity=<project>    ← task relationship graph
Step 5: mempalace_traverse start_room=<room> max_hops=2  ← connected rooms
Step 6: Synthesize → template below
```

Output template:
```
## 📋 Context Recovery: <project>

### 🎯 Current Task
<Task description> | Next Step: <action> | Status: 🔧|✅|❌

### 📝 Recent Activity
| When      | What                           | Source     |
|-----------|--------------------------------|------------|
| <date>    | <latest diary or last action>  | diary/file |

### 🔑 Key Decisions (do not revert)
- <from task file + palace decisions>

### ⚠️ Landmines
- <from task file>

### 🔗 Related Past Work
<MCP: search results + kg edges + traversed rooms | grep matches>

### ▶️ Recommended Next Action
<Single concrete next step>
```

CLI fallback: `moss-mem show` + `mempalace wake-up --wing <project>` (L0+L1 snapshot, ~600-900 tokens). File fallback: `show` + `grep`.

Recovery quality: **Full** (MCP multi-tool) → **Snapshot** (CLI wake-up) → **Partial** (file + grep) → **Minimal** (file only, empty handoff).

## CLI Operations (fallback + maintenance)

These run when MCP is unavailable, or for maintenance operations that have no MCP equivalent.

### mine — Bulk ingest into palace

```
# Mine project source
mempalace mine <project_dir> --wing <project>

# Mine task files with auto-classification → decisions / milestones / problems
mempalace mine MEMORY_TASKS/ --mode convos --extract general --wing <project>

# Preview
mempalace mine MEMORY_TASKS/ --wing <project> --dry-run
```

Auto-classification (`--mode convos --extract general`) extracts into rooms: `decisions`, `milestones`, `problems`. Use this when MCP mirroring was skipped (e.g., long CLI-fallback session) to batch-sync file state into palace.

Run after every 3-5 completed tasks, or before handoff in CLI-fallback mode.

### wake-up — Context snapshot

```
mempalace wake-up [--wing <project>]
```

Returns L0 (project summary) + L1 (recent drawer activity). Primary context recovery when MCP is down. Also useful as a fast sanity check even in enhanced mode.

### status — Palace health

```
mempalace status
```

Shows wings, rooms, drawer counts. Use to verify palace state.

### repair — Index maintenance

```
mempalace repair [--yes] [--dry-run]
mempalace repair-status
```

- `repair` — rebuild ChromaDB vector index
- `repair-status` — compare sqlite vs HNSW counts (read-only)

### compress — Storage optimization

```
mempalace compress --wing <project> [--dry-run]
```

AAAK compression (~30x reduction). Preview with `--dry-run` first.

### hook run — Session lifecycle (harness integration)

```
echo '{"session_id":"<id>","stop_hook_active":false,"transcript_path":"<path>"}' \
  | mempalace hook run --hook session-stop --harness claude-code
```

Typically configured in `settings.json` as `Stop` / `PreCompact` hooks — not invoked manually. Listed here for completeness.

## MCP Quick Reference

### Read (19 tools)

| Tool | Key Parameters | Purpose |
|------|---------------|---------|
| `mempalace_status` | — | Palace overview, drawer/wing/room counts |
| `mempalace_get_taxonomy` | — | Full wing→room→drawer tree |
| `mempalace_list_wings` | — | All wings with drawer counts |
| `mempalace_list_rooms` | `wing` (opt) | Rooms within a wing |
| `mempalace_list_drawers` | `wing`, `room`, `limit`, `offset` | Paginated drawer list |
| `mempalace_get_drawer` | `drawer_id` | Full drawer content + metadata |
| `mempalace_search` | `query`, `limit`, `wing`, `room`, `max_distance` | Semantic search (ChromaDB) |
| `mempalace_check_duplicate` | `content`, `threshold` | Dedup check before write |
| `mempalace_get_aaak_spec` | — | AAAK dialect specification |
| `mempalace_traverse` | `start_room`, `max_hops` | Walk palace graph |
| `mempalace_find_tunnels` | `wing_a`, `wing_b` (both opt) | Cross-wing connections |
| `mempalace_follow_tunnels` | `wing`, `room` | Room's tunnel connections |
| `mempalace_list_tunnels` | `wing` (opt) | All explicit tunnels |
| `mempalace_graph_stats` | — | Palace graph overview |
| `mempalace_kg_query` | `entity`, `as_of`, `direction` | Temporal KG query |
| `mempalace_kg_timeline` | `entity` (opt) | Chronological fact timeline |
| `mempalace_kg_stats` | — | KG overview: entities, triples |
| `mempalace_diary_read` | `agent_name`, `last_n`, `wing` | Agent diary entries |
| `mempalace_memories_filed_away` | — | Recent palace checkpoint |

### Write (11 tools)

| Tool | Key Parameters | Purpose |
|------|---------------|---------|
| `mempalace_add_drawer` | `wing`, `room`, `content`, `source_file`, `added_by` | Store content (idempotent) |
| `mempalace_update_drawer` | `drawer_id`, `content`, `wing`, `room` | Update drawer |
| `mempalace_delete_drawer` | `drawer_id` | Delete drawer (irreversible) |
| `mempalace_kg_add` | `subject`, `predicate`, `object`, `valid_from`, `valid_to` | Add temporal KG fact |
| `mempalace_kg_invalidate` | `subject`, `predicate`, `object`, `ended` | Mark fact no longer true |
| `mempalace_create_tunnel` | `source_wing`, `source_room`, `target_wing`, `target_room`, `label` | Cross-wing link |
| `mempalace_delete_tunnel` | `tunnel_id` | Remove tunnel |
| `mempalace_diary_write` | `agent_name`, `entry` (AAAK), `topic`, `wing` | Write diary entry |
| `mempalace_sync` | `project_dir`, `wing`, `apply` | Prune stale drawers |
| `mempalace_reconnect` | — | Force reconnect palace DB |
| `mempalace_hook_settings` | `silent_save`, `desktop_toast` | Hook behavior |

### Confirmation Checkpoints

| Operation | Confirm? | Rationale |
|-----------|----------|-----------|
| Read tools (search, get_drawer, list_*, kg_query, diary_read, traverse) | No | Read-only |
| add_drawer / update_drawer (mirroring) | No | Best-effort cache; file is system of record |
| delete_drawer / delete_tunnel | **Yes** | Irreversible |
| kg_add / kg_invalidate / create_tunnel | **Yes** | Persistent graph changes |
| diary_write | **Yes** | Permanent diary entry |
| sync (apply=true) | **Yes** | Destructive pruning |

## Agent Handoff Protocol

Each step has a verification gate — confirm the output before proceeding. If any gate fails, fix the issue and re-run that step. Never skip gates.

```
Step 1: moss-mem check
        Gate: exit 0 = all handoff fields filled → proceed to step 5
              exit 1 = fields incomplete → continue to step 2

Step 2: moss-mem check --fix
        Gate: re-run moss-mem check
              exit 0 → proceed to step 5
              exit 1 → continue to step 3

Step 3: moss-mem update -l "..." -k "..." -m "..."
        Gate: moss-mem show — verify ## Last Action, ## Key Decisions, ## Landmines are not <!-- pending -->
              filled → proceed to step 4
              still pending → repeat step 3 with remaining fields

Step 4: moss-mem diary -n "..."
        Gate (MCP): draft diary entry → show user → confirm before mempalace_diary_write
        Gate (CLI): draft [DIARY] entry → show user → confirm before add-note
        confirmed → proceed to step 5

Step 5: moss-mem complete -d "..."
        Gate: moss-mem show --file MEMORY_TASKS/archive/<completed> — verify it was archived
              MEMORY.md status shows ✅ → proceed to step 6

Step 6a [MCP]: mempalace_sync project_dir=<project>     ← preview (no apply)
               Show: "N stale drawers would be pruned. OK?"
               User confirms → mempalace_sync project_dir=<project> apply=true
               Gate: mempalace_status — verify drawer count decreased

Step 6b [CLI]: mempalace mine MEMORY_TASKS/ --mode convos --extract general --wing <project>
               Gate: mempalace search "<recent task keyword>" --wing <project>
                     results found → proceed to step 7
                     empty → check mine output for errors

Step 7: moss-mem start -d "..." -n "..."
        Gate: moss-mem show — verify new task file created with correct Description + Next Step
```

**Never skip gates.** A failed gate means the previous step didn't complete — fix and retry. Step 4 (diary) and step 6a (sync apply=true) require explicit user confirmation.

## First-Time Setup

```
# 1. Initialize memory system (always)
python3 {base}/scripts/memory_manager.py init

# 2. Install MemPalace
pip install mempalace

# 3. Initialize and populate palace
mempalace init <project_dir> --yes
mempalace mine <project_dir> --wing <project_name>

# 4. Register MCP server
claude mcp add mempalace -- mempalace-mcp

# 5. Initial mine of task files
mempalace mine MEMORY_TASKS/ --mode convos --extract general --wing <project_name>
```

## Task File Format

```
## Description       ← What this task aims to achieve
## Next Step         ← Precise next action (file:line or function)
## Status            ← 🔧 In Progress | ✅ Completed | ❌ Blocked
## Last Action       ← What was just done (file:line, concrete change)
## Key Decisions     ← Architectural choices + rationale (do not revert)
## Landmines         ← Fragile areas, known issues, avoid unless instructed
## Created           ← ISO timestamp
```

## MEMORY.md Template

```
## Meta [Strict]           — project identity, tech stack, last update
## 状态机 [Strict]          — current task pointer + status + last action
## 下一步指令 [Strict]       — next actionable step (file:line or function)
## 暂存与备忘区 [Free]       — free-form notes
## 雷区与技术契约 [Strict]   — append-only constraints
## 已归档任务 [Strict]       — archive index
```

## File Tree

```
MEMORY.md                    ← source of truth (<80 lines)
MEMORY_TASKS/
  YYYYMMDD-HHMMSS_task.md   ← active tasks
  .edit_lock                ← concurrency control (O_EXCL)
  MEMORY_ARCHIVE.md         ← completed task log
  archive/                  ← archived task files
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| MEMORY.md missing | `moss-mem init` |
| Stale lock file | `rm MEMORY_TASKS/.edit_lock` |
| Task pointer stale | `moss-mem show --file <path>` |
| Empty handoff fields | `moss-mem check --fix` |
| Session killed mid-handoff | `moss-mem recover` then `moss-mem check --fix` |
| Stale task (>7 days) | `moss-mem recover` → complete or restart |
| MCP tools not found / timeout | Degrade to CLI-fallback; check `claude mcp list` |
| MCP `mempalace_status` hangs | File-only; check MCP server process |
| MCP `mempalace_search` returns `[]` | Increase `max_distance`; CLI: `mempalace mine` to re-index |
| MCP `mempalace_add_drawer` errors | Wing/room auto-created; retry or skip |
| CLI `mempalace: command not found` | `pip install mempalace` |
| CLI `mempalace search` returns nothing | `mempalace mine MEMORY_TASKS/ --mode convos --extract general --wing <project>` |
| CLI `mempalace mine` fails | Disk space? Try `--limit 100`; check `mempalace repair-status` |
| Vector index corrupted | `mempalace repair --yes` |
| ChromaDB version mismatch | `mempalace migrate [--dry-run]` |

## Design Decisions

1. **Why two layers?** MEMORY.md is the startup index (always readable, <80 lines). MCP adds semantic depth; CLI adds bulk maintenance; both degrade gracefully.
2. **Why MCP primary + CLI fallback?** MCP offers semantic search, temporal KG, and diary — capabilities that need a stateful server. CLI covers bulk operations (mine, repair) and provides a fast fallback path when MCP is down.
3. **Why best-effort MCP mirroring?** File is the system of record. MCP mirroring enhances searchability but must never block file operations.
4. **Why `mine --extract general` for CLI fallback?** Auto-classification into decisions/milestones/problems provides structured discovery even without MCP's explicit KG.
5. **Why single `_memory_update()`?** Guarantees MEMORY.md never partially written; section parse is idempotent.
6. **Why `<!-- none -->` placeholder?** Distinguishes "intentionally empty" from "forgot to fill."
7. **Why git integration for auto-fix?** Git diff/log provide free recovery context in every code project.

## Skill Integration

- **init skill**: After creating project structure, run `moss-mem init`.
- **Any long task**: `start` → `update` → `check` before `complete`.
- **Cross-session recovery**: `moss-mem context` (MCP multi-tool) or `moss-mem show` + `mempalace wake-up` (CLI snapshot).
- **Setup**: `pip install mempalace && mempalace init <dir> --yes && mempalace mine <dir> --wing <project> && claude mcp add mempalace -- mempalace-mcp`

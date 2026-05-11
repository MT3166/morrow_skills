---
name: moss-mem
description: "Project memory management for Claude Code sessions. Two-layer: MEMORY.md (file index) + MemPalace MCP (semantic search, knowledge graph, agent diary). Triggers: init/start/update/complete task, search memory, link tasks, handoff/context switch."
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
version: "2.2"
---

# moss-mem — Project Memory Management

## TL;DR

Two-layer memory: **MEMORY.md** as always-available startup index + **MemPalace MCP** (30 tools: semantic search, temporal knowledge graph, palace graph navigation, agent diary). MCP failure never blocks operations — every feature degrades gracefully to file-only fallback.

```
File Layer (system of record)     MCP Layer (amplifies search + discovery)
  MEMORY.md ← startup pointer       mempalace_search  → semantic search (ChromaDB)
  MEMORY_TASKS/*.md ← task files    mempalace_kg_*    → temporal entity-relation graph
  Script: memory_manager.py         mempalace_diary_* → agent session continuity
                                    mempalace_*_tunnel → cross-wing navigation
```

MemPalace CLI commands (`mempalace init`, `mempalace mine`) are separate from MCP tools. MCP tools are available once the palace is initialized. Setup: `pip install mempalace && mempalace init <dir> && mempalace mine <dir>`.

## Decision Tree

```
User intent → what to do (file op first, palace mirror is best-effort):

"start task X" / "new task X"
  python3 {base}/scripts/memory_manager.py start -d "X" -n "next step"
  → mirror: mempalace_check_duplicate → mempalace_add_drawer room:tasks (skip on failure)

"update progress" / status change
  python3 {base}/scripts/memory_manager.py update -d "X" -n "Y" -s "🔧"
  → mirror: if -k/-m non-empty, mempalace_add_drawer room:decisions/landmines

"complete task" / "finish task"
  check → check --fix → update -l/-k/-m → diary → mempalace_sync → complete → start

"search memory" / "find tasks about X"
  mempalace_search query=X limit=10 → table with similarity scores & drawer IDs
  → for full content: mempalace_get_drawer drawer_id=<id>
  fallback: grep -r "X" MEMORY_TASKS/ MEMORY_ARCHIVE.md

"link X to Y" / "relate tasks"
  Confirm → mempalace_kg_add (with valid_from/valid_to if known)
  → mempalace_create_tunnel if cross-room
  fallback: append relationship to task file ## Key Decisions

"what were we working on?" (context recovery)
  show → diary_read → search → kg_query → traverse → synthesize (template below)

"handoff" / "context switch" / "交接"
  Full 6-step Agent Handoff Protocol (see below)
```

## Prerequisites

- Python 3.8+ (stdlib only). Run from **project root** (where MEMORY.md lives).
- Script: `{base}/scripts/memory_manager.py` — `{base}` is the `Base directory for this skill:` line in invocation header.
- After `kill -9`: `rm MEMORY_TASKS/.edit_lock`.
- **MemPalace** (optional): install via `pip install mempalace`, then `mempalace init <dir> && mempalace mine <dir>`. When absent, all operations degrade to file-only. MemPalace exposes 30 MCP tools — the CLI is separate from the MCP server.

## Operations

Each operation shows: file command (always runs first), MCP enhancement (best-effort), and fallback (when MCP unavailable).

### Task Lifecycle

**start** — Create new task
```
python3 {base}/scripts/memory_manager.py start -d "Description" -n "Next step instruction"
```
Creates `MEMORY_TASKS/YYYYMMDD-HHMMSS_task.md`, updates MEMORY.md pointer. Status → 🔧.

Enhanced (best-effort):
1. `mempalace_check_duplicate content="<description>"` — skip if duplicate exists
2. `mempalace_add_drawer wing=<project> room=tasks content="<description + next step>"`

**update** — Report progress
```
python3 {base}/scripts/memory_manager.py update -d "Progress" -n "Next step" -s "🔧"
```
Updates MEMORY.md status/next_step/scratchpad. For agent handoff, add:
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

Enhanced: when `-k`/`-m` non-empty, mirror to `room: decisions`/`room: landmines` + `mempalace_kg_add` for related work with `valid_from` timestamp. Skip on failure.

**complete** — Archive and reset
```
python3 {base}/scripts/memory_manager.py complete -d "Completion description"
```
Archives task → `MEMORY_TASKS/archive/`, appends to `MEMORY_ARCHIVE.md`, resets status → ✅.

Enhanced: `mempalace_update_drawer` to mark status complete, then `mempalace_sync project_dir=<project> apply=true` to prune stale drawers pointing to deleted/renamed task files. Skip on failure.

### Knowledge Operations (MCP-powered, file fallback)

**search** — Semantic task search
```
mempalace_search query="<keywords>" wing=<project> limit=10 max_distance=1.5
```
- `limit` — results count (1-100, default 5)
- `max_distance` — cosine distance threshold (default 1.5, lower = stricter)
- `wing`/`room` — optional scope filters

Output (enhanced):
```
## 🔍 MemPalace Search: "<query>" (limit=10)
| Score | Content (truncated)              | Drawer   |
|-------|----------------------------------|----------|
| 0.92  | Implemented JWT auth middleware   | #a1b2c3  |
| 0.87  | Fixed token refresh race cond.    | #d4e5f6  |

  3 results from MemPalace (semantic, max_distance=1.5).
  Full content: mempalace_get_drawer drawer_id="#a1b2c3"
```

Fallback: `grep -r "<keywords>" MEMORY_TASKS/ MEMORY_ARCHIVE.md` — keyword match, not semantic. Note: "keyword match only — conceptually related tasks may be missed."

**link** — Connect related tasks/decisions (temporal KG)
```
1. Confirm: "Link: 'rate-limiting' → relates_to → 'api-security'. OK?"
2. mempalace_kg_add subject="rate-limiting" predicate="relates_to" object="api-security"
   valid_from="2026-05-11"  ← when this relationship became true (optional)
   source_drawer_id="<drawer>"  ← link back to source drawer (optional)
3. mempalace_create_tunnel source_wing=<p> source_room=tasks
   target_wing=<p> target_room=tasks label="rate-limiting → api-security"
```
Output (enhanced): `🔗 Link Created: rate-limiting —[relates_to]→ api-security. KG edge (temporal) + tunnel. Query: mempalace_kg_query entity="api-security"`

To query with time context: `mempalace_kg_query entity="rate-limiting" as_of="2026-06-01" direction="both"`

To mark a fact no longer true: `mempalace_kg_invalidate subject="..." predicate="..." object="..."`

Fallback: append `Related: rate-limiting → api-security (relates_to)` to task file `## Key Decisions`. Output: `🔗 Link Noted (file-only) — not graph-traversable.`

**diary** — Agent session journal
```
Read:  mempalace_diary_read agent_name="claude" last_n=10 wing=<project>
Write: mempalace_diary_write agent_name="claude" entry="<AAAK>" topic="<topic>" wing=<project>
       → Draft entry, show user, confirm before writing.
```

Output (read):
```
## 📓 Agent Diary (last 10)
| Date       | Topic        | Key Decisions / Actions         | ★   |
|------------|-------------|---------------------------------|-----|
| 2026-05-11 | auth-module | JWT in httpOnly cookies         | ★★★ |
```

List all agents with diaries: `mempalace_list_wings` (each agent is a wing).

AAAK format (built-in fallback when MCP spec unavailable — get full spec via `mempalace_get_aaak_spec`):
```
SESSION:YYYY-MM-DD|topic_code|KEY.dec:summary|LANDMINE:area|★★★
```

| Scenario | AAAK Example |
|----------|-------------|
| Feature built | `SESSION:2026-05-11|auth.module|built.JWT.middleware|KEY.dec:cookies.over.localStorage|★★★` |
| Bug fixed | `SESSION:2026-05-11|token.refresh|fixed.race.condition|LANDMINE:auth.py.L45-L60.untested|★★★` |
| Decision made | `SESSION:2026-05-11|api.design|KEY.dec:REST.over.GraphQL|*confident*|★★☆` |
| Blocker hit | `SESSION:2026-05-11|db.migration|blocked.by.schema.lock|*frustrated*|NEED:DBA.approval|★★★` |
| Handoff | `SESSION:2026-05-11|handoff|completed.auth.module|NEXT:test.login.flow|★★★` |

Proactive diary triggers: after completing a milestone, making an architectural decision, hitting a blocker, before session end, after fixing a non-obvious bug.

Fallback (write): `moss-mem add-note -n "[DIARY] <AAAK entry>"`.
Fallback (read): read scratchpad section from MEMORY.md, filter `[DIARY]` prefix.

**context** — Rich context recovery
```
User: "what were we working on?" (after long absence)

Step 1: moss-mem show                     ← always works (file pointer)
Step 2: mempalace_diary_read last_n=10    ← fallback: scratchpad [DIARY] notes
Step 3: mempalace_search query=<topic>    ← fallback: grep MEMORY_TASKS/
Step 4: mempalace_kg_query entity=<proj>  ← fallback: grep for manual relationships
Step 5: mempalace_traverse start_room=<room> max_hops=2 ← discover connected rooms
Step 6: Synthesize → output template below
```

Output template:
```
## 📋 Context Recovery: <project>

### 🎯 Current Task
<Task description> | **Next Step**: <action> | **Status**: 🔧|✅|❌

### 📝 Recent Activity
| When      | What                           | Source     |
|-----------|--------------------------------|------------|
| <date>    | <latest diary or last action>  | diary/file |

### 🔑 Key Decisions (do not revert)
- <from task file + palace decisions if available>

### ⚠️ Landmines
- <from task file>

### 🔗 Related Past Work
<MCP: search results + kg edges + traversed rooms | file-only: grep matches>

### 📊 Sources
[file] MEMORY.md + MEMORY_TASKS/<current>  ← always
[MCP] diary/search/kg/traverse: <counts>   ← if available

### ▶️ Recommended Next Action
<Single concrete next step>
```

Recovery quality: **Full** (file+MCP all) → **Partial** (file+some MCP) → **Minimal** (file only) → **Bare** (file only, empty handoff fields).

### Meta Operations

**init** — `python3 {base}/scripts/memory_manager.py init`
Creates MEMORY.md + MEMORY_TASKS/ + MEMORY_ARCHIVE.md.

**show** — `python3 {base}/scripts/memory_manager.py show [--file <path>]`
Prints current task file (or specific archived file). Always available.

**add-note** — `python3 {base}/scripts/memory_manager.py add-note -n "Note"`
Appends timestamped note to MEMORY.md scratchpad.

**check** — `python3 {base}/scripts/memory_manager.py check [--fix]`
- `check`: exit 0 if handoff fields filled, exit 1 if `<!-- pending -->` or `<!-- none -->`.
- `check --fix`: auto-fill from git (`## Last Action` ← diff stat, `## Key Decisions` ← new dirs, `## Landmines` ← new dirs + recent log).
- Run before `complete` to guarantee clean handoff.

**recover** — `python3 {base}/scripts/memory_manager.py recover`
Checks lock file → task completeness → `git diff HEAD` → `git log -5` → `git stash list`. Enhanced: also `mempalace_diary_read last_n=10` for recovery context. Skip on failure.

**Skill invocation mapping** (when called via `--action` args from CLAUDE.md):
| Invocation | Python command |
|-----------|---------------|
| `--action init` | `init` |
| `--action start --description "X" --status "🔧"` | `start -d "X" -s "🔧"` |
| `--action start --description "X" --next "Y"` | `start -d "X" -n "Y"` |
| `--action update --description "X" --next "Y" --status "🔧"` | `update -d "X" -n "Y" -s "🔧"` |
| `--action complete --description "X"` | `complete -d "X"` |
| `--action add-note --note "X"` | `add-note -n "X"` |

## MCP Fault Tolerance

### Availability Check (once per session)
Call `mempalace_status` or `mempalace_get_taxonomy`. Cache result:

| Response | Mode | Behavior |
|----------|------|----------|
| Palace info returned | `enhanced` | Use MCP, mirror to palace |
| "No palace found" / timeout / error / tool not found | `file-only` | Mention once, skip all MCP |

### Progressive Degradation
```
Level 0 — Full MCP:      all tools respond → mirror + search + graph + diary
Level 1 — Partial MCP:   some tools fail → use working ones, fallback rest
Level 2 — MCP degraded:  all timeout but status OK → file-only, suggest reconnect
Level 3 — MCP unavailable: status fails → file-only, no further MCP attempts
```

### Call Wrapper Pattern
```
1. Check cached availability mode
2. If file-only → use fallback immediately
3. If enhanced → call MCP tool
4. On failure: note once in scratchpad, use fallback, degrade level
5. Never retry failed MCP call in same session
6. File writes ALWAYS happen before palace mirroring (file is system of record)
```

### Per-Operation Fallback

| MCP Tool | Fallback | Degraded Behavior |
|----------|----------|-------------------|
| `mempalace_search` | `grep -r` MEMORY_TASKS/ | Keyword match, not semantic |
| `mempalace_get_drawer` | Read task file directly | Full content via file path |
| `mempalace_list_drawers` | `ls MEMORY_TASKS/` | File listing, not paginated |
| `mempalace_check_duplicate` | grep for content snippet | Manual dedup, less reliable |
| `mempalace_add_drawer` | None (skip) | Task only in MEMORY_TASKS/ |
| `mempalace_update_drawer` | None (skip) | Palace state may be stale |
| `mempalace_kg_add` | Append to `## Key Decisions` | Captured but not traversable |
| `mempalace_kg_query` | `grep -r` for entity | Manual discovery |
| `mempalace_kg_timeline` | Read MEMORY_ARCHIVE.md | Chronological archive, no graph |
| `mempalace_kg_invalidate` | Note in task file | Fact marked stale in prose only |
| `mempalace_create_tunnel` | None (skip) | Cross-ref lost until MCP restored |
| `mempalace_traverse` / `follow_tunnels` | None (skip) | Manual room exploration |
| `mempalace_diary_read` | Read scratchpad `[DIARY]` notes | Less structured |
| `mempalace_diary_write` | `add-note "[DIARY] ..."` | Preserved but not MCP-searchable |
| `mempalace_sync` | Manual file check | Stale drawers remain until next MCP session |
| `mempalace_get_aaak_spec` | Use built-in AAAK format | Basic format without full spec |

### MCP Tool Quick Reference (30 tools)

**Read (19 tools):**

| Tool | Key Parameters | Purpose |
|------|---------------|---------|
| `mempalace_status` | _none_ | Palace overview: drawers, wings, rooms, protocol, AAAK spec |
| `mempalace_get_taxonomy` | _none_ | Full tree: wing → room → drawer count (best overview) |
| `mempalace_list_wings` | _none_ | All wings with drawer counts (agents + projects) |
| `mempalace_list_rooms` | `wing` (opt) | Rooms within a wing |
| `mempalace_list_drawers` | `wing`, `room`, `limit`, `offset` | Paginated drawer list with previews |
| `mempalace_get_drawer` | `drawer_id` | Full content + metadata for single drawer |
| `mempalace_search` | `query`, `limit`, `wing`, `room`, `max_distance`, `context` | Semantic search (ChromaDB) |
| `mempalace_check_duplicate` | `content`, `threshold` | Dedup check before writing |
| `mempalace_get_aaak_spec` | _none_ | AAAK dialect specification |
| `mempalace_traverse` | `start_room`, `max_hops` | Walk palace graph from a room |
| `mempalace_find_tunnels` | `wing_a`, `wing_b` (both opt) | Rooms bridging two wings |
| `mempalace_follow_tunnels` | `wing`, `room` | See what a room connects to |
| `mempalace_list_tunnels` | `wing` (opt) | All explicit cross-wing tunnels |
| `mempalace_graph_stats` | _none_ | Palace graph overview |
| `mempalace_kg_query` | `entity`, `as_of`, `direction` | Temporal KG query |
| `mempalace_kg_timeline` | `entity` (opt) | Chronological fact timeline |
| `mempalace_kg_stats` | _none_ | KG overview: entities, triples, expired facts |
| `mempalace_diary_read` | `agent_name`, `last_n`, `wing` | Agent diary entries |
| `mempalace_memories_filed_away` | _none_ | Check for recent palace checkpoint |

**Write (11 tools):**

| Tool | Key Parameters | Purpose |
|------|---------------|---------|
| `mempalace_add_drawer` | `wing`, `room`, `content`, `source_file`, `added_by` | Store verbatim content (idempotent) |
| `mempalace_update_drawer` | `drawer_id`, `content`, `wing`, `room` | Update drawer content/metadata |
| `mempalace_delete_drawer` | `drawer_id` | Delete drawer (irreversible) |
| `mempalace_kg_add` | `subject`, `predicate`, `object`, `valid_from`, `valid_to`, `source_*` | Add temporal KG fact |
| `mempalace_kg_invalidate` | `subject`, `predicate`, `object`, `ended` | Mark fact no longer true |
| `mempalace_create_tunnel` | `source_wing`, `source_room`, `target_wing`, `target_room`, `label` | Cross-wing link |
| `mempalace_delete_tunnel` | `tunnel_id` | Remove explicit tunnel |
| `mempalace_diary_write` | `agent_name`, `entry` (AAAK), `topic`, `wing` | Write diary entry |
| `mempalace_sync` | `project_dir`, `wing`, `apply` | Prune stale drawers (dry-run default) |
| `mempalace_reconnect` | _none_ | Force reconnect to palace DB |
| `mempalace_hook_settings` | `silent_save`, `desktop_toast` | Get/set hook behavior |

### Confirmation Checkpoints

| Operation | Confirm? | Rationale |
|-----------|----------|-----------|
| Read tools (search, get_drawer, list_*, get_taxonomy, kg_query, kg_timeline, diary_read, traverse, graph_stats) | No | Read-only |
| add_drawer / update_drawer (mirroring) | No | Best-effort cache; file is system of record |
| delete_drawer / delete_tunnel | **Yes** | Irreversible |
| kg_add / kg_invalidate / create_tunnel (link) | **Yes** | Persistent graph changes |
| diary_write | **Yes** | Permanent diary entry |
| sync (with apply=true) | **Yes** | Destructive pruning |

### Timeout & Error Patterns

| Symptom | Likely Cause | Action |
|---------|-------------|--------|
| `mempalace_status` hangs >5s | Server not running | File-only; check MCP configuration |
| `mempalace_search` returns `[]` | Empty palace or query too strict | Increase `max_distance`; fallback grep; suggest `mempalace mine` (CLI) |
| `mempalace_add_drawer` errors | Wing/room not created | Skip mirroring; wing/room auto-created on first add_drawer |
| `mempalace_diary_write` errors | Permission / disk | Fallback `[DIARY]` scratchpad |
| `mempalace_sync` errors | Project dir mismatch | Skip; drawers will be pruned next sync |
| Multiple tools timeout | Server overloaded | Degrade to file-only for session |
| HNSW index errors (search) | ChromaDB transient issue | Auto-retried by MCP server; if persists, `mempalace_reconnect` |

## Palace Mirroring

Palace is a best-effort cache. File writes always happen first.

| File operation | Palace mirror (skip on failure) |
|---------------|----------------|
| `start` task | `check_duplicate` → `add_drawer` → `room: tasks` |
| `update -k` (decisions) | `add_drawer` → `room: decisions` + `kg_add` with `valid_from` |
| `update -m` (landmines) | `add_drawer` → `room: landmines` |
| `complete` task | `update_drawer` (mark complete) → `sync` (prune stale) |
| Session end | `diary_write` (AAAK session summary) |

Palace taxonomy: `wing: <project_name>` → `room: tasks | decisions | landmines | diary`.

## Agent Handoff Protocol

Always follow this sequence when handing off:

```
1. moss-mem check           ← verify handoff fields complete
2. moss-mem check --fix     ← auto-fill from git if possible
3. moss-mem update -l/-k/-m ← manually fill remaining fields
4. moss-mem diary -n "..."  ← write session diary (AAAK)
   Enhanced: mempalace_diary_write | File-only: add-note "[DIARY] ..."
5. moss-mem complete        ← archive current task
   Enhanced: mempalace_sync apply=true (prune stale) | Skip on failure
6. moss-mem start -d "..." -n "..." ← new task for next agent
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

MEMORY.md template:
```
## Meta [Strict]           — project identity, tech stack
## 状态机 [Strict]          — current pointer + status + last action
## 下一步指令 [Strict]       — next actionable step (file:line)
## 暂存与备忘区 [Free]       — free-form notes
## 雷区与技术契约 [Strict]   — append-only constraints
## 已归档任务 [Strict]       — archive index
```

File tree:
```
MEMORY.md                    ← source of truth (<80 lines, single-write via _memory_update())
MEMORY_TASKS/
  YYYYMMDD-HHMMSS_task.md   ← active/completed tasks
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
| MemPalace MCP not installed | File-only mode (all operations work) |
| MemPalace not initialized | File-only mode; run `mempalace init <dir> && mempalace mine <dir>` (CLI) |
| MemPalace search empty | Increase `max_distance`; fallback grep; run `mempalace mine` (CLI) |
| MemPalace index stale | `mempalace_reconnect` |
| MCP tools hang/timeout | Degrade to file-only for session |

## Design Decisions

1. **Why two layers?** MEMORY.md is the startup index (always readable without MCP). Palace adds semantic depth but degrades gracefully.
2. **Why timestamps in task filenames?** Avoids name collisions; chronological order aids forensics.
3. **Why single `_memory_update()`?** Guarantees MEMORY.md never partially written; section parse is idempotent.
4. **Why `<!-- none -->` placeholder?** Distinguishes "intentionally empty" from "forgot to fill."
5. **Why git integration for auto-fix?** Git is always present in code projects; diff/log provide free recovery context.
6. **Why best-effort palace mirroring?** File is the system of record; MCP is a cache that amplifies search and discovery. Every MCP operation has a file-based fallback — the system degrades gracefully, never fails.
7. **Why progressive degradation?** MCP availability is not binary — network, server load, or partial installation can cause selective failures. Handling each tool independently maximizes what still works.
8. **Why `check_duplicate` before `add_drawer`?** MemPalace `add_drawer` is idempotent by design, but `check_duplicate` avoids unnecessary write operations and keeps the palace clean.

## Skill Integration

- **init skill**: After creating project structure, run `moss-mem init`.
- **project-surgeon**: After surgical changes, use `moss-mem update -l/-k/-m`.
- **Any long task**: Always `start` → `update` → `check` before `complete`.
- **Cross-session recovery**: Use `moss-mem context` for rich recovery combining file pointer + palace search + diary + graph traversal.

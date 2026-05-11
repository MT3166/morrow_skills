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
version: "2.1"
---

# moss-mem — Project Memory Management

## TL;DR

Two-layer memory: **MEMORY.md** as always-available startup index + **MemPalace MCP** for semantic search, knowledge graph, and agent diary. MCP failure never blocks operations — every feature degrades gracefully to file-only fallback.

```
File Layer (system of record)     MCP Layer (amplifies search + discovery)
  MEMORY.md ← startup pointer       mempalace_search  → semantic task search
  MEMORY_TASKS/*.md ← task files    mempalace_kg_*    → relationship graph
  Script: memory_manager.py         mempalace_diary_* → session continuity
```

## Decision Tree

```
User intent → what to do (file op first, palace mirror is best-effort):

"start task X" / "new task X"
  python3 {base}/scripts/memory_manager.py start -d "X" -n "next step"
  → mirror: mempalace_add_drawer room:tasks (skip on failure)

"update progress" / status change
  python3 {base}/scripts/memory_manager.py update -d "X" -n "Y" -s "🔧"
  → mirror: if -k/-m non-empty, mempalace_add_drawer room:decisions/landmines

"complete task" / "finish task"
  check → check --fix → update -l/-k/-m → diary → complete → start (handoff protocol)

"search memory" / "find tasks about X"
  mempalace_search query=X → table with scores & drawer IDs
  fallback: grep -r "X" MEMORY_TASKS/ MEMORY_ARCHIVE.md

"link X to Y" / "relate tasks"
  Confirm relationship → mempalace_kg_add + mempalace_create_tunnel
  fallback: append to task file ## Key Decisions

"what were we working on?" (context recovery)
  show → diary_read → search → kg_query → synthesize (see Context Recovery template)

"handoff" / "context switch" / "交接"
  Full 6-step Agent Handoff Protocol (see below)
```

## Prerequisites

- Python 3.8+ (stdlib only). Run from **project root** (where MEMORY.md lives).
- Script: `{base}/scripts/memory_manager.py` — `{base}` is the `Base directory for this skill:` line in invocation header.
- After `kill -9`: `rm MEMORY_TASKS/.edit_lock`.
- **MemPalace** (optional): initialize via `mempalace init <dir> && mempalace mine <dir>`. When absent, all operations degrade to file-only.

## Operations

Each operation shows: file command (always runs first), MCP enhancement (best-effort), and fallback (when MCP unavailable).

### Task Lifecycle

**start** — Create new task
```
python3 {base}/scripts/memory_manager.py start -d "Description" -n "Next step instruction"
```
Creates `MEMORY_TASKS/YYYYMMDD-HHMMSS_task.md`, updates MEMORY.md pointer. Status → 🔧.

Enhanced: `mempalace_add_drawer` → `room: tasks` with description + next step. Skip on failure.

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

Enhanced: when `-k`/`-m` non-empty, mirror to `room: decisions`/`room: landmines` + `mempalace_kg_add` for related work. Skip on failure.

**complete** — Archive and reset
```
python3 {base}/scripts/memory_manager.py complete -d "Completion description"
```
Archives task → `MEMORY_TASKS/archive/`, appends to `MEMORY_ARCHIVE.md`, resets status → ✅.

Enhanced: `mempalace_update_drawer` to mark complete. Skip on failure.

### Knowledge Operations (MCP-powered, file fallback)

**search** — Semantic task search
```
mempalace_search query="<keywords>" wing=<project> k=<top-N>
```
Output (enhanced):
```
## 🔍 MemPalace Search: "<query>"
| Score | Content (truncated)              | Drawer   |
|-------|----------------------------------|----------|
| 0.92  | Implemented JWT auth middleware   | #a1b2c3  |
| 0.87  | Fixed token refresh race cond.    | #d4e5f6  |
  Top match: moss-mem show --file MEMORY_TASKS/archive/<task>.md
  3 results (semantic). Use drawer IDs for full content.
```
Fallback: `grep -r "<keywords>" MEMORY_TASKS/ MEMORY_ARCHIVE.md` — keyword match, not semantic. Note: "keyword match only — conceptually related tasks may be missed."

**link** — Connect related tasks/decisions
```
1. Confirm: "Link: 'rate-limiting' → relates_to → 'api-security'. OK?"
2. mempalace_kg_add subject="rate-limiting" predicate="relates_to" object="api-security"
3. mempalace_create_tunnel source_wing=<p> source_room=tasks target_wing=<p> target_room=tasks label="rate-limiting → api-security"
```
Output (enhanced): `🔗 Link Created: rate-limiting —[relates_to]→ api-security. KG edge + tunnel. Query: mempalace_kg_query entity="api-security"`

Fallback: append `Related: rate-limiting → api-security (relates_to)` to task file `## Key Decisions`. Output: `🔗 Link Noted (file-only) — not graph-traversable.`

**diary** — Agent session journal
```
Read:  mempalace_diary_read agent_name="claude" last_n=5
Write: mempalace_diary_write agent_name="claude" entry="<AAAK>" topic="<topic>"
       → Draft entry, show user, confirm before writing.
```

Output (read):
```
## 📓 Agent Diary (last 5)
| Date       | Topic        | Key Decisions / Actions         | ★   |
|------------|-------------|---------------------------------|-----|
| 2026-05-11 | auth-module | JWT in httpOnly cookies         | ★★★ |
```

AAAK format (built-in fallback when MCP spec unavailable):
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

Step 1: moss-mem show            ← always works (file pointer)
Step 2: mempalace_diary_read     ← fallback: scratchpad [DIARY] notes
Step 3: mempalace_search         ← fallback: grep MEMORY_TASKS/
Step 4: mempalace_kg_query       ← fallback: grep for manual relationships
Step 5: Synthesize → output template below
```

Output template (always use this structure):
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
<MCP: search results + kg edges | file-only: grep matches>

### 📊 Sources
[file] MEMORY.md + MEMORY_TASKS/<current>  ← always
[MCP] diary/search/kg: <count> entries     ← if available

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
Checks lock file → task completeness → `git diff HEAD` → `git log -5` → `git stash list`. Enhanced: also `mempalace_diary_read last_n=5` for recovery context. Skip on failure.

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
Call `mempalace_status`. Cache result:

| Response | Mode | Behavior |
|----------|------|----------|
| Palace info returned | `enhanced` | Use MCP, mirror to palace |
| "No palace found" / timeout / error / tool not found | `file-only` | Mention once, skip all MCP |

### Progressive Degradation
```
Level 0 — Full MCP:      all tools respond → mirror everything
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
| `mempalace_add_drawer` | None (skip) | Task only in MEMORY_TASKS/ |
| `mempalace_update_drawer` | None (skip) | Palace state may be stale |
| `mempalace_kg_query` | `grep -r` for entity | Manual discovery, not graph traversal |
| `mempalace_kg_add` | Append to `## Key Decisions` | Captured but not traversable |
| `mempalace_create_tunnel` | None (skip) | Cross-ref lost until MCP restored |
| `mempalace_diary_read` | Read scratchpad `[DIARY]` notes | Less structured |
| `mempalace_diary_write` | `add-note "[DIARY] ..."` | Preserved but not searchable via MCP |

### MCP Tool Quick Reference

| Tool | Purpose | Used In |
|------|---------|---------|
| `mempalace_status` | Health check | Availability check, recovery |
| `mempalace_search` | Semantic search (query, wing, room, k) | search, context |
| `mempalace_add_drawer` | Add content to room (wing, room, content) | start, update mirroring |
| `mempalace_update_drawer` | Update drawer (drawer_id, content) | complete mirroring |
| `mempalace_kg_add` | Add KG edge (subject, predicate, object) | link |
| `mempalace_kg_query` | Query KG (entity) | context |
| `mempalace_create_tunnel` | Cross-project ref (source/target wing/room, label) | link |
| `mempalace_diary_read` | Read diary (agent_name, last_n) | diary, recover, context |
| `mempalace_diary_write` | Write diary AAAK (agent_name, entry, topic) | diary, handoff |
| `mempalace_get_aaak_spec` | Get AAAK format spec | diary (enhanced) |
| `mempalace_reconnect` | Refresh HNSW index | troubleshooting |
| `mempalace_mine` | Index project dir into palace | setup (user action) |
| `mempalace_init` | Initialize new palace | setup (user action) |

### Confirmation Checkpoints

| Operation | Confirm? | Rationale |
|-----------|----------|-----------|
| search / diary read / kg_query | No | Read-only |
| add_drawer / update_drawer (mirroring) | No | Best-effort cache; file is system of record |
| kg_add / create_tunnel (link) | **Yes** | Persistent graph connections |
| diary_write | **Yes** | Permanent diary entry |
| init / mine | **Yes** | One-time project setup |

### Timeout & Error Patterns

| Symptom | Likely Cause | Action |
|---------|-------------|--------|
| `mempalace_status` hangs >5s | Server not running | File-only; check `mcp.json` |
| `mempalace_search` returns `[]` | Empty palace / query mismatch | Fallback grep; suggest `mempalace mine` |
| `mempalace_add_drawer` errors | Not initialized | Skip; suggest `mempalace init` |
| `mempalace_diary_write` errors | Permission / disk | Fallback `[DIARY]` scratchpad |
| Multiple tools timeout | Server overloaded | Degrade to file-only for session |

## Palace Mirroring

Palace is a best-effort cache. File writes always happen first.

| File operation | Palace mirror (skip on failure) |
|---------------|----------------|
| `start` task | `mempalace_add_drawer` → `room: tasks` |
| `update -k` (decisions) | `mempalace_add_drawer` → `room: decisions` |
| `update -m` (landmines) | `mempalace_add_drawer` → `room: landmines` |
| `complete` task | `mempalace_update_drawer` (mark complete) |
| Session end | `mempalace_diary_write` (session summary) |

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
6. moss-mem start -d "..." -n "..." ← new task for next agent
```

Complete task files enable context recovery. Palace diary entries add searchable session notes but file-based `[DIARY]` scratchpad notes serve as fallback.

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
| MemPalace not installed | File-only mode (all operations work) |
| MemPalace not initialized | File-only mode; optionally `mempalace init <dir> && mempalace mine <dir>` |
| MemPalace search empty | Fallback grep; suggest `mempalace mine` |
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

## Skill Integration

- **init skill**: After creating project structure, run `moss-mem init`.
- **project-surgeon**: After surgical changes, use `moss-mem update -l/-k/-m`.
- **Any long task**: Always `start` → `update` → `check` before `complete`.
- **Cross-session recovery**: Use `moss-mem context` for rich recovery (file pointer + palace search + diary).

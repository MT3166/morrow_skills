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
version: "2.0"
---

# moss-mem - Project Memory Management

## TL;DR

Two-layer memory: `MEMORY.md` as lightweight startup index + **MemPalace MCP** for semantic search, task relationships, and cross-session agent diary. Falls back to file-only mode when MCP unavailable.

## Two-Layer Architecture

```
Layer 1: MEMORY.md (file-based, always available)
  └── Startup index: project identity, current task pointer, status, next step
  └── Updated via Python script (single-write principle)

Layer 2: MemPalace MCP (rich memory, when available)
  └── Semantic search across past tasks (mempalace_search)
  └── Knowledge graph for task relationships (mempalace_kg_add/query)
  └── Agent diary for session continuity (mempalace_diary_read/write)
  └── Cross-project tunnels (mempalace_create_tunnel)

Palace taxonomy for moss-mem:
  wing: <project_name>
    room: tasks          ← task descriptions + status
    room: decisions      ← key architectural decisions
    room: landmines      ← known fragile areas
    room: diary          ← agent session notes
```

## Quick Reference

**File-based commands** (always available):

| Command | Purpose | Key Flags |
|---------|---------|-----------|
| `init` | Initialize memory system | - |
| `start -d "..." -n "..."` | Start new task | `-d` description, `-n` next step |
| `update -d "..." -n "..." -s "🔧"` | Update progress | `-s` status emoji |
| `update -l/-k/-m` | Agent handoff fields | `-l` last action, `-k` key decisions, `-m` landmines |
| `complete -d "..."` | Archive and reset | `-d` completion summary |
| `add-note -n "..."` | Scratchpad note | `-n` note content |
| `show [--file X]` | Inspect task file | `--file` for specific/stale task |
| `recover` | Interrupt recovery | git state inspection |
| `check [--fix]` | Handoff validation | `--fix` auto-fill empty fields |

**Mempalace-powered commands** (when MCP available):

| Command | Purpose | MCP Tool Used |
|---------|---------|---------------|
| `search "..."` | Semantic search across all tasks | `mempalace_search` |
| `link --from X --to Y --rel Z` | Connect related tasks/decisions | `mempalace_kg_add` + `mempalace_create_tunnel` |
| `diary` | Read recent agent diary entries | `mempalace_diary_read` |
| `diary -n "..."` | Write agent diary entry in AAAK | `mempalace_diary_write` |
| `context "..."` | Rich context recovery (task + search + diary + graph) | multi-tool orchestration |

## Invocation Workflow

When moss-mem is invoked, follow this decision flow:

```
1. Parse user intent → which operation? (init/start/update/complete/search/link/diary/show/context)

2. Check mempalace availability (once per session):
   Call mempalace_status with 5s timeout expectation.
   Map result to mode per "Availability Check" table in Fault Tolerance section.
   If file-only → mention once, then skip all MCP steps silently.

3. Execute the operation:
   - File-based commands (init/start/update/complete/add-note/show/recover/check):
     Run Python script first (system of record), then mirror to palace if enhanced.
   - MCP-powered commands (search/link/diary/context):
     Use MCP Call Wrapper Pattern: check mode → call MCP → fallback on failure.
     See "Per-Operation Fallback Table" for exact fallback per tool.

4. If any MCP call fails during enhanced mode:
   Log once to scratchpad, use fallback, degrade level for subsequent calls.
   Never let an MCP failure block the user's intent.
```

## Prerequisites

- Python 3.8+ (stdlib only — no external dependencies)
- Run from **project root** (where MEMORY.md lives)
- After `kill -9`: `rm MEMORY_TASKS/.edit_lock` before next operation
- **Script path**: `{base_dir}/scripts/memory_manager.py` — `{base_dir}` is the value on the `Base directory for this skill:` line in the skill invocation header
- **MemPalace** (optional): initialized via `mempalace init <dir> && mempalace mine <dir>` in the project. When absent, moss-mem degrades gracefully to file-only mode.

## Skill Invocation → Python Command Mapping

When invoked via the Skill tool with `--action`-style args (e.g. from CLAUDE.md startup protocol):

| Skill invocation | Python command |
|-----------------|----------------|
| `--action init` | `python3 {base_dir}/scripts/memory_manager.py init` |
| `--action start --description "X" --status "🔧"` | `python3 {base_dir}/scripts/memory_manager.py start -d "X" -s "🔧"` |
| `--action start --description "X" --next "Y"` | `python3 {base_dir}/scripts/memory_manager.py start -d "X" -n "Y"` |
| `--action update --description "X" --next "Y" --status "🔧"` | `python3 {base_dir}/scripts/memory_manager.py update -d "X" -n "Y" -s "🔧"` |
| `--action complete --description "X"` | `python3 {base_dir}/scripts/memory_manager.py complete -d "X"` |
| `--action add-note --note "X"` | `python3 {base_dir}/scripts/memory_manager.py add-note -n "X"` |

> `-n` (next step) is required for `start` but optional for `update`. Always run from project root.

## File-Based Commands

### init
```
python3 {base_dir}/scripts/memory_manager.py init
```
Creates `MEMORY.md` (if missing) and `MEMORY_TASKS/` directory with `MEMORY_ARCHIVE.md`.

### start
```
python3 {base_dir}/scripts/memory_manager.py start -d "Description" -n "Next step instruction"
```
Creates `MEMORY_TASKS/YYYYMMDD-HHMMSS_task.md` and updates pointer in MEMORY.md. Status → 🔧.

**Enhanced mode**: also call `mempalace_add_drawer` with `wing: <project>, room: tasks` containing description + next step.

### update
```
python3 {base_dir}/scripts/memory_manager.py update -d "Progress" -n "Next step" -s "🔧"
```
Updates MEMORY.md (status, next step, scratchpad entry with timestamp).

**Agent handoff fields** (all optional):
```
python3 {base_dir}/scripts/memory_manager.py update \
  -d "Completed auth refactor" \
  -n "Test the login flow" -s "🔧" \
  -l "Refactored auth.py:login() — moved token validation to separate function" \
  -k "JWT stored in httpOnly cookie, not localStorage — do not revert" \
  -m "auth.py:45-60 is untested, do not modify until tests added"
```

**Field semantics** (`-l` / `-k` / `-m`):

| Flag | Omitted | `""` (empty) | Non-empty |
|------|---------|--------------|-----------|
| `-l` | Leave unchanged | → `<!-- pending -->` | Replace |
| `-k` | Leave unchanged | → `<!-- none -->` | Replace |
| `-m` | Leave unchanged | → `<!-- none -->` | Replace |

**Enhanced mode**: when `-k` (key decisions) or `-m` (landmines) are non-empty, mirror them to palace:
- `mempalace_add_drawer` with `room: decisions` or `room: landmines`
- `mempalace_kg_add` if decisions relate to prior work

### complete
```
python3 {base_dir}/scripts/memory_manager.py complete -d "Completion description"
```
Archives task file → `MEMORY_TASKS/archive/`, appends to `MEMORY_ARCHIVE.md`, resets status → ✅.

### add-note
```
python3 {base_dir}/scripts/memory_manager.py add-note -n "Note content"
```
Appends timestamped note to scratchpad section.

### show
```
python3 {base_dir}/scripts/memory_manager.py show
python3 {base_dir}/scripts/memory_manager.py show --file MEMORY_TASKS/20260413-120000_task.md
```
Reads pointer from MEMORY.md → prints task file. Use `--file` for archived or stale tasks.

### recover
```
python3 {base_dir}/scripts/memory_manager.py recover
```
Automated interrupt recovery. Checks: (1) lock file → (2) task file completeness → (3) `git diff HEAD` → (4) `git log --oneline -5` → (5) `git stash list`. Guides next action.

**Enhanced mode**: also call `mempalace_diary_read` for recent agent entries that may contain recovery context.

### check
```
python3 {base_dir}/scripts/memory_manager.py check
python3 {base_dir}/scripts/memory_manager.py check --fix
```
- `check` alone: exit 0 if all handoff fields filled, exit 1 if any `<!-- pending -->` or `<!-- none -->`
- `check --fix`: auto-fill from git state:
  - `## Last Action` ← git diff stat summary
  - `## Key Decisions` ← newly created directories (architectural signals)
  - `## Landmines` ← new directories + recent git log
- Use before `moss-mem complete` to guarantee clean handoff.

## Mempalace Commands

These commands only execute when mempalace is available. Check with `mempalace_status` first. If "No palace found", report it and fall back to file-based equivalents.

### search — Semantic task search
```
User: "find tasks about authentication"

Enhanced path:
  mempalace_search query="authentication tasks decisions" wing=<project>
  → Present results with similarity scores and drawer IDs

Fallback (file-only or MCP call fails):
  grep -r "auth\|authentication\|login\|token\|session" MEMORY_TASKS/ MEMORY_ARCHIVE.md
  → Present matching files with line context
  → Note: keyword match, not semantic — results may miss conceptually related tasks
```

### link — Connect related tasks/decisions
```
User: "the rate-limiting work relates to our earlier API security task"

Enhanced path:
  mempalace_kg_add subject="rate-limiting-task" predicate="relates_to" object="api-security-task"
  mempalace_create_tunnel source_wing=<project> source_room=tasks target_wing=<project> target_room=tasks label="rate-limiting → api-security"

Fallback (file-only or MCP call fails):
  → Append to current task file ## Key Decisions:
    "Related: rate-limiting-task → api-security-task (relates_to)"
  → Relationship is preserved in file for human review but not traversable via graph
```

### diary — Agent session journal
```
Read:
  Enhanced: mempalace_diary_read agent_name="claude" last_n=5
  Fallback: read scratchpad section from MEMORY.md (recent notes, less structured)

Write:
  Enhanced: mempalace_diary_write agent_name="claude" entry="SESSION:2026-05-11|built.auth.module|KEY.dec:JWT.in.cookies|★★★" topic="auth-work"
  Fallback: moss-mem add-note -n "[DIARY] SESSION:2026-05-11|built.auth.module|KEY.dec:JWT.in.cookies|★★★"
```

Use AAAK format for diary entries: entity codes, `*emotion*` markers, pipe-separated fields, ISO dates, ★ importance ratings. Get the full spec via `mempalace_get_aaak_spec` when MCP is available; fall back to the built-in format: `SESSION:YYYY-MM-DD|topic|KEY.dec:item|★★★`.

### context — Rich context recovery
```
User: "what were we working on?" (after long absence)

Step 1: moss-mem show (file-based, always works)
  → Current task + next step + key decisions + landmines

Step 2: Try mempalace_diary_read agent_name="claude" last_n=10
  → Fallback: read scratchpad notes from MEMORY.md (look for [DIARY] prefix)

Step 3: Try mempalace_search query=<extracted topic from current task>
  → Fallback: grep -r "<topic keywords>" MEMORY_TASKS/ MEMORY_ARCHIVE.md

Step 4: Try mempalace_kg_query entity=<project>
  → Fallback: grep -r "<project>" MEMORY_TASKS/ for manual relationship discovery

Step 5: Synthesize a context summary from whatever sources succeeded:
   - Current task + next step (always available from file)
   - Key decisions (from task file; palace decisions if MCP worked)
   - Related past tasks (from search/grep results)
   - Recent agent diary entries (from MCP or scratchpad [DIARY] notes)
   - Note which sources were used: "[file only]" or "[file + MCP]"
```

## Palace Mirroring

Whenever file-based commands mutate state AND mempalace is available, mirror key facts:

| File operation | Palace mirror |
|---------------|---------------|
| `start` task | `mempalace_add_drawer` → `room: tasks` |
| `update -k` (decisions) | `mempalace_add_drawer` → `room: decisions` |
| `update -m` (landmines) | `mempalace_add_drawer` → `room: landmines` |
| `complete` task | `mempalace_update_drawer` to mark status complete |
| Session end | `mempalace_diary_write` with session summary |

Mirroring is best-effort: file operations must never fail because palace mirroring failed.

## MCP Fault Tolerance & Progressive Degradation

### Availability Check (run once per session)

```
mempalace_status
```

| Response | Meaning | Mode |
|----------|---------|------|
| Palace info returned | MCP fully available | `enhanced` |
| "No palace found" | Not initialized in this project | `file-only` |
| Timeout (>5s) or hang | MCP server unresponsive | `file-only` |
| Error / exception | MCP server error | `file-only` |
| Tool not found / unknown command | mempalace MCP not installed | `file-only` |

Cache the result for the session. If `file-only`, mention once ("MemPalace unavailable, using file-based memory") then skip all MCP steps silently.

### Per-Operation Fallback Table

When `file-only` mode, or when a specific MCP call fails even in `enhanced` mode:

| MCP Operation | MCP Tool | Fallback Command | Degraded Behavior |
|--------------|----------|-----------------|-------------------|
| Semantic search | `mempalace_search` | `grep -r "<keywords>" MEMORY_TASKS/ MEMORY_ARCHIVE.md` | Keyword match instead of semantic; results not relevance-ranked |
| Add task to palace | `mempalace_add_drawer` | None (skip silently) | Task only in MEMORY_TASKS/ file |
| Update palace drawer | `mempalace_update_drawer` | None (skip silently) | Palace state may be stale on next MCP availability |
| Knowledge graph query | `mempalace_kg_query` | `grep -r "<entity>" MEMORY_TASKS/` | Manual relationship discovery instead of graph traversal |
| Knowledge graph add | `mempalace_kg_add` | Append relationship to task file `## Key Decisions` | Relationship captured but not traversable |
| Create tunnel | `mempalace_create_tunnel` | None (skip silently) | Cross-reference lost until MCP restored |
| Read diary | `mempalace_diary_read` | Read scratchpad section from MEMORY.md | Recent notes instead of structured diary entries |
| Write diary | `mempalace_diary_write` | Append `[DIARY] <content>` to scratchpad via `add-note` | Less structured but preserved for next session |
| Get AAAK spec | `mempalace_get_aaak_spec` | Use built-in format (see below) | Basic AAAK without full spec guidance |

**Built-in AAAK fallback format**: `SESSION:YYYY-MM-DD|topic|KEY.dec:item|★★★`

### Progressive Degradation

Not binary — handle partial MCP failures:

```
Level 0 — Full MCP: all tools respond within timeout
  → Use MCP for everything, mirror to palace

Level 1 — Partial MCP: some tools work, others fail/timeout
  → Use MCP for working tools, fallback for failed ones
  → Report degraded tools to user once, continue

Level 2 — MCP degraded: all tools timeout but status responds
  → File-only mode; suggest user run `mempalace reconnect`

Level 3 — MCP unavailable: status check itself fails
  → File-only mode; no further MCP attempts this session
```

### MCP Call Wrapper Pattern

Every MCP interaction follows this pattern:

```
1. Check cached availability mode (from mempalace_status)
2. If file-only → use fallback immediately, skip MCP call
3. If enhanced → call MCP tool
4. If MCP call fails (timeout / error / empty result):
   a. Note failure once in scratchpad (don't spam)
   b. Use fallback from table above
   c. Degrade availability level for subsequent calls of same type
5. Never retry a failed MCP call in the same session
6. File operations (MEMORY.md writes) happen BEFORE palace mirroring,
   so file state is always consistent even if mirroring fails
```

### Timeout & Error Patterns

| Symptom | Likely Cause | Action |
|---------|-------------|--------|
| `mempalace_status` hangs >5s | MCP server not running | File-only mode; suggest user check `mcp.json` |
| `mempalace_search` returns `[]` | Empty palace or query mismatch | Fall back to grep; suggest `mempalace mine <dir>` if palace empty |
| `mempalace_add_drawer` errors | Palace not initialized | Skip mirroring; suggest `mempalace init <dir>` |
| `mempalace_kg_add` errors | Entity not found in graph | Skip; relationship captured in task file instead |
| `mempalace_diary_write` errors | Permission or disk full | Fall back to scratchpad note with `[DIARY]` prefix |
| Multiple tools timeout in sequence | MCP server overloaded | Degrade to file-only for rest of session |

## Agent Handoff Protocol

**Always follow this sequence** when handing off (session end, context switch, or before `complete`):

```
1. moss-mem check           ← verify completeness
2. moss-mem check --fix     ← auto-fill if possible
3. moss-mem update -l/-k/-m ← fill remaining fields manually
4. moss-mem diary -n "..."  ← write session diary entry
   → Enhanced: mempalace_diary_write (structured AAAK entry)
   → File-only: moss-mem add-note -n "[DIARY] SESSION:YYYY-MM-DD|topic|key_points|★★★"
5. moss-mem complete        ← archive task
6. moss-mem start -d "..." -n "..."  ← new task for next agent
```

A complete task file enables context recovery. Palace diary entries add searchable session notes but file-based `[DIARY]` scratchpad notes serve as fallback.

## Task File Format

```
## Description       ← What this task aims to achieve
## Next Step         ← Precise next action (file:line or function name)
## Status            ← 🔧 In Progress | ✅ Completed | ❌ Blocked
## Last Action       ← What was just done (file:line, concrete change)
## Key Decisions     ← Architectural choices + rationale (do not revert)
## Landmines         ← Fragile areas, known issues, avoid unless instructed
## Created           ← ISO timestamp
```

## MEMORY.md Template

```markdown
# MEMORY.md

## Meta [Strict]
- 最后更新：[YYYY-MM-DD HH:MM]
- 项目画像：[one sentence core responsibility]
- 技术栈：[key technologies]

## 状态机 [Strict]
- **当前指针**：`MEMORY_TASKS/YYYYMMDD-HHMMSS_task.md`
- **全局目标**：[current phase deliverable]
- **最后状态**：[🔧|✅|❌|⚠️]
- **最后动作**：[description of most recent action]

## 下一步指令 [Strict]
- [action] `path` -> [location] [detail]

## 暂存与备忘区 (Scratchpad) [Free]
<!-- notes go here -->

## 雷区与技术契约 [Strict/Append-only]
<!-- append-only constraints -->

## 已归档任务 [Strict/Append-only]
- [YYYY-MM-DD] [summary]
```

## Architecture Details

**Single-write principle**: All writes to MEMORY.md go through `_memory_update()` (one read → section parse → one write). Never partial writes.

```
MEMORY.md (source of truth, <80 lines)
    ├── ## Meta [Strict]         — project identity
    ├── ## 状态机 [Strict]        — current pointer + status
    ├── ## 下一步指令 [Strict]    — next actionable step
    ├── ## 暂存与备忘区 [Free]    — free-form notes
    ├── ## 雷区与技术契约 [Strict] — append-only constraints
    └── ## 已归档任务 [Strict]    — archive index

MEMORY_TASKS/YYYYMMDD-HHMMSS_task.md
    ├── ## Description
    ├── ## Next Step
    ├── ## Status
    ├── ## Last Action         ← filled by -l flag
    ├── ## Key Decisions       ← filled by -k flag
    ├── ## Landmines           ← filled by -m flag
    └── ## Created

MEMORY_TASKS/archive/              ← completed tasks
MEMORY_TASKS/.edit_lock           ← concurrency control (O_EXCL)
MEMORY_TASKS/MEMORY_ARCHIVE.md    ← completed task log
```

## Troubleshooting

| Problem | Diagnosis | Fix |
|---------|-----------|-----|
| `MEMORY.md missing` | First run in project | `moss-mem init` auto-creates it |
| `Concurrent edit detected` | Another process holding lock | Wait or `rm MEMORY_TASKS/.edit_lock` |
| Lock acquisition fails | Stale lock file | `rm MEMORY_TASKS/.edit_lock` |
| Task pointer stale | Task file moved/deleted | `moss-mem show --file X` with specific path |
| `## Last Action` empty | Handoff not completed | `moss-mem check --fix` or fill manually |
| Session killed mid-handoff | `kill -9` scenario | `moss-mem recover` then `moss-mem check --fix` |
| Task idle >7 days | Stale task | `moss-mem recover` to assess + `moss-mem complete` or restart |
| `check --fix` fails to fill Key Decisions | No new directories in git diff | Manual judgment required — mark as `<!-- none -->` |
| MemPalace not installed | `mempalace_status` returns "Tool not found" | File-only mode; all operations work, search is grep-based |
| MemPalace not initialized | `mempalace_status` returns "No palace found" | File-only mode; optionally run `mempalace init <dir> && mempalace mine <dir>` |
| MemPalace search returns no results | Palace empty or query too specific | Fall back to `grep -r` per fallback table; suggest `mempalace mine` |
| MemPalace index stale | External modification to palace | Call `mempalace_reconnect` to refresh HNSW index |
| MCP tools hang/timeout | MCP server unresponsive | Degrade to file-only for rest of session; see Fault Tolerance section |
| Partial MCP failures | Some tools work, others don't | Use Progressive Degradation: MCP for working tools, fallback for failed ones |

## Skill Integration

- **init**: After `init skill` creates project structure, run `moss-mem init` to set up memory
- **project-surgeon**: After surgical changes, use `moss-mem update -l/-k/-m` to document what changed
- **Any long task**: Always start with `moss-mem start`, update with `moss-mem update`, complete with `moss-mem check` before `moss-mem complete`
- **Cross-session recovery**: Use `moss-mem context` for rich recovery combining file pointer + palace search + diary

## Design Decisions

1. **Why two layers?** MEMORY.md is the startup index (always readable without MCP). Palace adds semantic depth but degrades gracefully.
2. **Why timestamps in task filenames?** Avoids concurrent-task name collisions; chronological order aids forensics.
3. **Why single `_memory_update()`?** Guarantees MEMORY.md never partially written; section parse is idempotent.
4. **Why `<!-- none -->` placeholder?** Distinguishes "intentionally empty" from "forgot to fill."
5. **Why git integration for auto-fix?** Git is always present in code projects; diff/log provide free context for recovery.
6. **Why best-effort palace mirroring?** File operations are the system of record; MCP is a cache that amplifies search and discovery. Every MCP operation has a file-based fallback — the system degrades gracefully, never fails.
7. **Why progressive degradation?** MCP availability is not binary — network, server load, or partial installation can cause selective failures. Handling each tool independently maximizes what still works rather than abandoning all MCP features.

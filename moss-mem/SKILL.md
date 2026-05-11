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

2. Check mempalace availability:
   Call mempalace_status once.
   If "No palace found" → file-only mode (skip MCP steps)
   If success → enhanced mode (file + MCP)

3. Execute the operation (see command sections below)

4. If enhanced mode AND operation mutates state:
   Mirror key facts to palace (see "Palace Mirroring" below)
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
→ mempalace_search query="authentication tasks decisions" wing=<project>
→ Present results with similarity scores and drawer IDs
→ If no results or MCP unavailable: grep MEMORY_TASKS/ and MEMORY_ARCHIVE.md
```

### link — Connect related tasks/decisions
```
User: "the rate-limiting work relates to our earlier API security task"
→ mempalace_kg_add subject="rate-limiting-task" predicate="relates_to" object="api-security-task"
→ mempalace_create_tunnel source_wing=<project> source_room=tasks target_wing=<project> target_room=tasks label="rate-limiting → api-security"
→ Also note the relationship in the current task file's ## Key Decisions
```

### diary — Agent session journal
```
Read:  mempalace_diary_read agent_name="claude" last_n=5
Write: mempalace_diary_write agent_name="claude" entry="SESSION:2026-05-11|built.auth.module|KEY.dec:JWT.in.cookies|★★★" topic="auth-work"
```

Use AAAK format for diary entries: entity codes, `*emotion*` markers, pipe-separated fields, ISO dates, ★ importance ratings. Get the full spec via `mempalace_get_aaak_spec` when needed.

### context — Rich context recovery
```
User: "what were we working on?" (after long absence)
→ Step 1: moss-mem show (file-based current task pointer)
→ Step 2: mempalace_diary_read agent_name="claude" last_n=10 (recent session notes)
→ Step 3: mempalace_search query=<extracted topic from current task> (related past work)
→ Step 4: mempalace_kg_query entity=<project> (task relationship graph)
→ Step 5: Synthesize a context summary:
   - Current task + next step
   - Key decisions (from task file + palace)
   - Related past tasks (from search + graph)
   - Recent agent diary entries
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

## Agent Handoff Protocol

**Always follow this sequence** when handing off (session end, context switch, or before `complete`):

```
1. moss-mem check           ← verify completeness
2. moss-mem check --fix     ← auto-fill if possible
3. moss-mem update -l/-k/-m ← fill remaining fields manually
4. moss-mem diary -n "..."  ← write session diary entry (MCP mode)
5. moss-mem complete        ← archive task
6. moss-mem start -d "..." -n "..."  ← new task for next agent
```

A complete task file + palace diary entry enables full context recovery in <30 seconds.

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
| MemPalace not available | `mempalace_status` returns "No palace found" | Run `mempalace init <dir> && mempalace mine <dir>`, or continue in file-only mode |
| MemPalace search returns no results | Palace empty or query too specific | Broaden query; fall back to `grep -r` across MEMORY_TASKS/ |
| MemPalace index stale | External modification to palace | Call `mempalace_reconnect` to refresh HNSW index |

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
6. **Why best-effort palace mirroring?** File operations are the system of record; palace is a cache that amplifies search and discovery.

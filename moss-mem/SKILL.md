---
name: moss-mem
description: "Project memory management for Claude Code sessions. Triggers: initialize memory, start/update/complete task, add note, show task, handoff/context switch."
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
  - handoff
  - 交接
  - 接力
  - context switch
version: "1.1"
---

# moss-mem - Project Memory Management

## TL;DR

Manages project memory via `MEMORY.md` (single source of truth) + `MEMORY_TASKS/` (detailed task files). Ensures zero-loss handoff between Claude sessions.

## Quick Reference

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

## Architecture

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

**Why timestamped task files?** Avoids filename collisions; chronological order aids debugging.

## Prerequisites

- Python 3.8+ (stdlib only — no external dependencies)
- Run from **project root** (where MEMORY.md lives)
- After `kill -9`: `rm MEMORY_TASKS/.edit_lock` before next operation

## Commands

### init
```
python3 /path/to/memory_manager.py init
```
Creates `MEMORY.md` (if missing) and `MEMORY_TASKS/` directory with `MEMORY_ARCHIVE.md`.

### start
```
python3 /path/to/memory_manager.py start -d "Description" -n "Next step instruction"
```
Creates `MEMORY_TASKS/YYYYMMDD-HHMMSS_task.md` and updates pointer in MEMORY.md. Status → 🔧.

### update
```
python3 /path/to/memory_manager.py update -d "Progress" -n "Next step" -s "🔧"
```
Updates MEMORY.md (status, next step, scratchpad entry with timestamp).

**Agent handoff fields** (all optional):
```
python3 /path/to/memory_manager.py update \
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

**Task expiration**: Tasks idle >7 days are stale. Run `moss-mem recover` to assess.

### complete
```
python3 /path/to/memory_manager.py complete -d "Completion description"
```
Archives task file → `MEMORY_TASKS/archive/`, appends to `MEMORY_ARCHIVE.md`, resets status → ✅.

### add-note
```
python3 /path/to/memory_manager.py add-note -n "Note content"
```
Appends timestamped note to scratchpad section.

### show
```
python3 /path/to/memory_manager.py show
python3 /path/to/memory_manager.py show --file MEMORY_TASKS/20260413-120000_task.md
```
Reads pointer from MEMORY.md → prints task file. Use `--file` for archived or stale tasks.

### recover
```
python3 /path/to/memory_manager.py recover
```
Automated interrupt recovery. Checks: (1) lock file → (2) task file completeness → (3) `git diff HEAD` → (4) `git log --oneline -5` → (5) `git stash list`. Guides next action.

### check
```
python3 /path/to/memory_manager.py check
python3 /path/to/memory_manager.py check --fix
```
- `check` alone: exit 0 if all handoff fields filled, exit 1 if any `<!-- pending -->` or `<!-- none -->`
- `check --fix`: auto-fill from git state:
  - `## Last Action` ← git diff stat summary
  - `## Key Decisions` ← newly created directories (architectural signals)
  - `## Landmines` ← new directories + recent git log
- Use before `moss-mem complete` to guarantee clean handoff.

## Agent Handoff Protocol

**Always follow this sequence** when handing off (session end, context switch, or before `complete`):

```
1. moss-mem check           ← verify completeness
2. moss-mem check --fix     ← auto-fill if possible
3. moss-mem update -l/-k/-m ← fill remaining fields manually
4. moss-mem complete        ← archive task
5. moss-mem start -d "..." -n "..."  ← new task for next agent
```

A complete task file enables full context recovery in <30 seconds.

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

## Skill Integration

- **init**: After `init skill` creates project structure, run `moss-mem init` to set up memory
- **project-surgeon**: After surgical changes, use `moss-mem update -l/-k/-m` to document what changed
- **Any long task**: Always start with `moss-mem start`, update with `moss-mem update`, complete with `moss-mem check` before `moss-mem complete`

## Design Decisions

1. **Why timestamps in task filenames?** Avoids concurrent-task name collisions; chronological order aids forensics.
2. **Why single `_memory_update()`?** Guarantees MEMORY.md never partially written; section parse is idempotent.
3. **Why `<!-- none -->` placeholder?** Distinguishes "intentionally empty" from "forgot to fill."
4. **Why git integration for auto-fix?** Git is always present in code projects; diff/log provide free context for recovery.

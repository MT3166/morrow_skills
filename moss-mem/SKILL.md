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
  - add note
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
version: "1.0"
---

# moss-mem - Project Memory Management

## Overview

Manages persistent context for projects via `MEMORY.md` and `MEMORY_TASKS/` directory. Ensures continuity across Claude sessions by tracking project state, active tasks, and technical conventions.

## Core Concepts

- **MEMORY.md**: Single source of truth for project state (strict format, <80 lines)
- **MEMORY_TASKS/**: Timestamped task files for detailed progress tracking
- **MEMORY_ARCHIVE.md**: Completed tasks archive
- **Concurrency control**: `.edit_lock` file prevents simultaneous modifications

## Commands

All commands run from **project root** (where MEMORY.md lives):
```
python3 /path/to/memory_manager.py <command> [args]
```

> **Path note**: When installed as a Claude Code skill, the script is at the skill install root. When developing locally, run from repo root. Adjust path as needed for your setup.

### init
Initialize memory system in current project:
```
python3 /path/to/memory_manager.py init
```
Creates `MEMORY.md` (if missing) and `MEMORY_TASKS/` directory.

### start
Start a new task:
```
python3 /path/to/memory_manager.py start -d "Description" -n "Next step instruction"
```
Creates `MEMORY_TASKS/YYYYMMDD-HHMMSS_task.md` and updates pointer in MEMORY.md.

### update
Update current task progress:
```
python3 /path/to/memory_manager.py update -d "Progress description" -n "Next step" -s "🔧"
```
Updates MEMORY.md meta, status, next step, and scratchpad.

For agent handoff, also pass handoff fields:
```
python3 /path/to/memory_manager.py update \
  -d "Completed auth refactor" \
  -n "Test the login flow" -s "🔧" \
  -l "Refactored auth.py:login() — moved token validation to separate function" \
  -k "JWT stored in httpOnly cookie, not localStorage — do not revert" \
  -m "auth.py:45-60 is untested, do not modify until tests added"
```

**Field semantics for handoff flags (`-l`, `-k`, `-m`)**:
| Flag | Omitted (not present) | Empty string `""` | Non-empty value |
|------|----------------------|-------------------|-----------------|
| `-l` | Leave unchanged | Clear to `<!-- pending -->` | Replace with value |
| `-k` | Leave unchanged | Clear to `<!-- none -->` | Replace with value |
| `-m` | Leave unchanged | Write `<!-- none -->` | Replace with value |

**Task expiration**: Tasks not updated for >7 days are considered stale. Run `moss-mem recover` to inspect and either complete or restart the task.

### complete
Complete current task:
```
python3 /path/to/memory_manager.py complete -d "Completion description"
```
Archives task file, updates MEMORY_ARCHIVE.md, resets status to ✅.

### add-note
Add free-form note to scratchpad:
```
python3 /path/to/memory_manager.py add-note -n "Note content"
```

### show
Show current task file content (for handoff review):
```
python3 /path/to/memory_manager.py show
python3 /path/to/memory_manager.py show --file MEMORY_TASKS/20260413-120000_task.md
```
Reads `MEMORY.md` → extracts `**当前指针**` → prints task file. Use `--file` to show a specific task file (e.g., an archived or stale task).

### recover
Automated interrupt recovery — inspects git state and guide task file reconstruction:
```
python3 /path/to/memory_manager.py recover
```
Steps: (1) check lock file, (2) inspect current task file, (3) `git diff HEAD` → uncommitted changes, (4) `git log --oneline -5` → recent commits, (5) `git stash list` → stashed changes. Run `moss-mem update` to fill in recovery information.

### check
Validate current task file completeness — ensure all required fields are filled before handoff:
```
python3 /path/to/memory_manager.py check
python3 /path/to/memory_manager.py check --fix
```
- Default: exits 0 if complete, exits 1 if any field is `<!-- pending -->` or `<!-- none -->`
- `--fix`: auto-fill empty fields using git-derived content:
  - `## Last Action` ← git diff summary (uncommitted changes)
  - `## Landmines` ← new directories + recent git log
  - `## Key Decisions` ← newly created directories (architectural signals)
Use before `moss-mem complete` to guarantee clean handoff.

## Status Emoji Convention

| Emoji | Meaning |
|-------|---------|
| 🔧 | In Progress |
| ✅ | Completed |
| ❌ | Error/Blocked |
| ⚠️ | Warning/Needs Attention |

## Usage in Conversation

When user requests memory operations, invoke the appropriate command. After each operation, report the result to user and append `📝 MEMORY 已更新` to your response.

## Task File Format (MEMORY_TASKS/YYYYMMDD-HHMMSS_task.md)

```
## Description       ← 任务目标
## Next Step         ← 下一步精确指令
## Status            ← 🔧 进行中 | ✅ 完成 | ❌ 阻塞
## Last Action       ← 本次完成的具体操作，精确到函数/行
## Key Decisions     ← 重大决策及原因，后续 Agent 遵守不推翻
## Landmines         ← 已知的坑或危险区域，勿动
## Created           ← ISO timestamp
```

## Agent Handoff Protocol

When handing off to another agent (session end or context switch):

1. **Update Last Action** — Fill in `## Last Action` with concrete changes made (file:line, function name, what changed)
2. **Record Key Decisions** — If any architectural choices were made, note the decision and rationale in `## Key Decisions`
3. **Flag Landmines** — If any code areas are fragile or known issues, document them in `## Landmines`
4. **Update Next Step** — Ensure `## Next Step` is precise and actionable for the next agent
5. **Call `moss-mem complete`** — Archive the task so the next agent can start fresh

A well-prepared task file lets the next agent achieve full context in under 30 seconds.

### Interrupt Recovery (Agent was killed mid-session)

If the previous agent was killed without completing the handoff:

1. **Inspect task file** → `python3 moss-mem/scripts/memory_manager.py show`
2. If `## Last Action` is empty or `## Next Step` is unclear:
   - Run `git diff HEAD` to see uncommitted changes (what was being done)
   - Run `git log --oneline -5` to see recent commits (context of recent work)
   - Run `git stash list` to check for any stashed changes
3. Fill in `## Last Action`, `## Landmines` based on code state and git diff
4. Continue from `## Next Step`; do not restart from scratch
5. After recovery: `moss-mem complete -d "recovered: <summary>"` → `moss-mem start -d "..." -n "..."`

```
# MEMORY.md

## Meta [Strict]
- 最后更新：[YYYY-MM-DD HH:MM]
- 项目画像：[one sentence]
- 技术栈：[stack]

## 状态机 [Strict]
- **当前指针**：`MEMORY_TASKS/YYYYMMDD-HHMMSS_task.md`
- **全局目标**：[current goal]
- **最后状态**：[status emoji]
- **最后动作**：[last action description]

## 下一步指令 [Strict]
- [动作] `path` -> [位置] 补充 [detail]

## 暂存与备忘区 (Scratchpad) [Free]
<!-- notes go here -->

## 雷区与技术契约 [Strict/Append-only]
<!-- constraints and pitfalls -->

## 已归档任务 [Strict/Append-only]
- [YYYY-MM-DD] [task summary]
```

## Prerequisites

- Python 3.8+
- No external dependencies (stdlib only)
- `MEMORY_TASKS/.edit_lock` must be removed manually after `kill -9` (see Error Handling)

## Error Handling

| Situation | Behavior |
|-----------|----------|
| Concurrent edit detected | Abort with error |
| MEMORY.md missing | Auto-create with default template |
| Task file missing | Warn but continue (pointer may be stale) |
| Lock acquisition fails | Exit with error code 1 |
| SIGTERM / SIGINT received | Release lock automatically before exit |
| Session crash (unhandled signal) | Lock released via `atexit` on next invocation (may need manual remove in rare cases) |

**Manual lock removal**: Only needed if a process was kill -9'd. Delete `MEMORY_TASKS/.edit_lock` before next operation.

## Script Location

```
/path/to/memory_manager.py
```

The script auto-detects its own location via `Path(__file__).resolve().parent`. To invoke from any directory, either use an absolute path or add the script's directory to `PATH`.

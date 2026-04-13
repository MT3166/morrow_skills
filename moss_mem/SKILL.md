---
name: moss_mem
description: "Project memory management skill for persistent context across sessions. Manages MEMORY.md and MEMORY_TASKS/ directory. Use when: (1) initializing a new project with memory system, (2) updating task progress with action=update, (3) starting a new task with action=start, (4) completing a task with action=complete, (5) adding notes to scratchpad with action=add_note, (6) reading MEMORY.md to understand current project state. Trigger phrases: update memory, start task, complete task, add note, initialize memory, check memory."
---

# MOSS_MEM - Project Memory Management

## Overview

Manages persistent context for projects via `MEMORY.md` and `MEMORY_TASKS/` directory. Ensures continuity across Claude sessions by tracking project state, active tasks, and technical conventions.

## Core Concepts

- **MEMORY.md**: Single source of truth for project state (strict format, <80 lines)
- **MEMORY_TASKS/**: Timestamped task files for detailed progress tracking
- **MEMORY_ARCHIVE.md**: Completed tasks archive
- **Concurrency control**: `.edit_lock` file prevents simultaneous modifications

## Commands

All commands use `python3 /Users/mt/.claude/skills/moss_mem/scripts/memory_manager.py <command> [args]`

### init
Initialize memory system in current project:
```
python3 .../memory_manager.py init
```
Creates `MEMORY.md` (if missing) and `MEMORY_TASKS/` directory.

### start
Start a new task:
```
python3 .../memory_manager.py start -d "Description" -n "Next step instruction"
```
Creates `MEMORY_TASKS/YYYYMMDD-HHMMSS_task.md` and updates pointer in MEMORY.md.

### update
Update current task progress:
```
python3 .../memory_manager.py update -d "Progress description" -n "Next step" -s "🔧"
```
Updates MEMORY.md meta, status, next step, and scratchpad.

### complete
Complete current task:
```
python3 .../memory_manager.py complete -d "Completion description"
```
Archives task file, updates MEMORY_ARCHIVE.md, resets status to ✅.

### add-note
Add free-form note to scratchpad:
```
python3 .../memory_manager.py add-note -n "Note content"
```

## Status Emoji Convention

| Emoji | Meaning |
|-------|---------|
| 🔧 | In Progress |
| ✅ | Completed |
| ❌ | Error/Blocked |
| ⚠️ | Warning/Needs Attention |

## Usage in Conversation

When user requests memory operations, invoke the appropriate command. After each operation, report the result to user and append `📝 MEMORY 已更新` to your response.

## MEMORY.md Format

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
/Users/mt/.claude/skills/MOSS_MEM/scripts/memory_manager.py
```

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

morrow_skills is a Claude Code extension skill repository. Skills are invoked via `/skill-name` syntax and provide specialized capabilities to Claude.

## Available Skills

### moss_mem
Project memory management skill. Manages `MEMORY.md` and `MEMORY_TASKS/` directory for cross-session context persistence.

**Trigger phrases:** "initialize memory", "update memory", "start task", "complete task", "add note"

**Script location:** `/Users/mt/.claude/skills/moss_mem/scripts/memory_manager.py`

**Commands:**
- `/moss_mem init` — Initialize memory system
- `/moss_mem start -d "描述" -n "下一步指令"` — Start new task
- `/moss_mem update -d "进度" -s "🔧"` — Update task progress
- `/moss_mem complete -d "完成描述"` — Complete current task
- `/moss_mem add-note -n "笔记内容"` — Add note to scratchpad

## Architecture

```
morrow_skills/
├── moss_mem/           # Skill definition
│   ├── SKILL.md         # Skill documentation
│   └── scripts/         # Python scripts for skill logic
├── MEMORY_TASKS/        # Task files directory
├── MEMORY.md            # Project state tracker
└── README.md            # User-facing documentation
```

## Project State Protocol

`MEMORY.md` is the source of truth for project state. All significant work should update it via moss_mem commands to maintain continuity across sessions.

## Development Notes

- No build system (markdown + Python scripts only)
- Skills are self-contained directories with `SKILL.md` defining triggers and behavior
- Concurrent edit protection via `.edit_lock` file in `MEMORY_TASKS/`
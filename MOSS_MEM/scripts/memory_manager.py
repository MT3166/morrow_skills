#!/usr/bin/env python3
"""
MOSS_MEM - Memory Management Script
Handles MEMORY.md and MEMORY_TASKS/ for project context persistence.
"""

import argparse
import os
import sys
import json
from datetime import datetime
from pathlib import Path

MEMORY_FILE = "MEMORY.md"
TASKS_DIR = "MEMORY_TASKS"
ARCHIVE_FILE = "MEMORY_ARCHIVE.md"


def get_timestamp():
    return datetime.now().strftime("%Y%m%d-%H%M")


def ensure_tasks_dir():
    Path(TASKS_DIR).mkdir(exist_ok=True)


def check_concurrent_edit():
    """Detect concurrent edit conflicts via .edit_lock file."""
    lock_file = Path(TASKS_DIR) / ".edit_lock"
    if lock_file.exists():
        try:
            with open(lock_file) as f:
                data = json.load(f)
                pid = data.get("pid", "unknown")
                time = data.get("time", "unknown")
                print(f"[WARNING] Concurrent edit detected! Lock held by PID {pid} at {time}")
                return True
        except:
            pass
    return False


def acquire_lock():
    """Acquire edit lock to prevent concurrent modifications."""
    ensure_tasks_dir()
    lock_file = Path(TASKS_DIR) / ".edit_lock"
    try:
        with open(lock_file, "w") as f:
            json.dump({"pid": os.getpid(), "time": datetime.now().isoformat()}, f)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to acquire lock: {e}")
        return False


def release_lock():
    """Release edit lock."""
    lock_file = Path(TASKS_DIR) / ".edit_lock"
    try:
        if lock_file.exists():
            lock_file.unlink()
    except Exception as e:
        print(f"[WARNING] Failed to release lock: {e}")


def cmd_start(description: str, next_step: str):
    """Start a new task: create timestamped task file and update MEMORY.md."""
    ensure_tasks_dir()
    if check_concurrent_edit():
        print("[ERROR] Cannot start new task while another edit is in progress.")
        sys.exit(1)

    acquire_lock()
    try:
        ts = get_timestamp()
        task_file = f"{TASKS_DIR}/{ts}_task.md"

        # Create task file
        with open(task_file, "w") as f:
            f.write(f"---\nname: {ts}_task\ndescription: {description}\ntype: task\n---\n\n")
            f.write(f"# Task - {ts}\n\n")
            f.write(f"## Description\n{description}\n\n")
            f.write(f"## Next Step\n{next_step}\n\n")
            f.write(f"## Status\n🔧 In Progress\n\n")
            f.write(f"## Created\n{datetime.now().isoformat()}\n\n")

        # Update MEMORY.md pointer
        update_memory_pointer(ts, task_file)
        update_memory_status("🔧 In Progress")

        print(f"✅ Task started: {task_file}")
        print(f"📝 Pointer updated in MEMORY.md")

    finally:
        release_lock()


def cmd_update(description: str, next_step: str, status: str):
    """Update current task progress in MEMORY.md."""
    if check_concurrent_edit():
        print("[WARNING] Concurrent edit detected, but proceeding with update.")

    acquire_lock()
    try:
        update_memory_meta()
        update_memory_status(status)
        update_memory_next_step(next_step)
        update_memory_scratchpad(description)

        print(f"✅ MEMORY.md updated")
        print(f"📊 Status: {status}")
        print(f"📋 Next: {next_step}")

    finally:
        release_lock()


def cmd_complete(description: str):
    """Complete current task: archive and update MEMORY.md."""
    if check_concurrent_edit():
        print("[ERROR] Cannot complete task while another edit is in progress.")
        sys.exit(1)

    acquire_lock()
    try:
        # Find current task file from MEMORY.md
        current_task = get_current_task_file()
        if current_task and Path(current_task).exists():
            archive_task(current_task)

        # Add to archive
        append_to_archive(description)

        # Update MEMORY.md status
        update_memory_status("✅ Completed")
        update_memory_last_action(f"Completed: {description}")

        print(f"✅ Task completed and archived")

    finally:
        release_lock()


def cmd_add_note(note: str):
    """Add a free-form note to MEMORY.md scratchpad."""
    acquire_lock()
    try:
        append_to_scratchpad(note)
        print(f"✅ Note added to scratchpad")
    finally:
        release_lock()


def get_current_task_file():
    """Extract current task file path from MEMORY.md."""
    if not Path(MEMORY_FILE).exists():
        return None

    with open(MEMORY_FILE) as f:
        content = f.read()
        for line in content.split("\n"):
            if "当前指针" in line or "current pointer" in line.lower():
                # Extract path between backticks if present
                if "`" in line:
                    start = line.find("`") + 1
                    end = line.rfind("`")
                    return line[start:end] if end > start else None
                # Otherwise look for path pattern
                parts = line.split(":")
                if len(parts) > 1:
                    return parts[-1].strip()
    return None


def update_memory_pointer(timestamp: str, task_file: str):
    """Update current task pointer in MEMORY.md."""
    if not Path(MEMORY_FILE).exists():
        create_default_memory()

    with open(MEMORY_FILE) as f:
        content = f.read()

    # Update pointer line
    new_lines = []
    for line in content.split("\n"):
        if "**当前指针**" in line or "**Current Pointer**" in line:
            new_lines.append(f"- **当前指针**：`{task_file}`")
        else:
            new_lines.append(line)
    content = "\n".join(new_lines)

    with open(MEMORY_FILE, "w") as f:
        f.write(content)


def update_memory_meta():
    """Update last modified timestamp in MEMORY.md."""
    if not Path(MEMORY_FILE).exists():
        create_default_memory()
        return

    with open(MEMORY_FILE) as f:
        content = f.read()

    new_lines = []
    for line in content.split("\n"):
        if "最后更新" in line:
            new_lines.append(f"- 最后更新：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
        else:
            new_lines.append(line)
    content = "\n".join(new_lines)

    with open(MEMORY_FILE, "w") as f:
        f.write(content)


def update_memory_status(status: str):
    """Update status in MEMORY.md."""
    if not Path(MEMORY_FILE).exists():
        create_default_memory()

    with open(MEMORY_FILE) as f:
        content = f.read()

    new_lines = []
    for line in content.split("\n"):
        if "**最后状态**" in line:
            new_lines.append(f"- **最后状态**：{status}")
        else:
            new_lines.append(line)
    content = "\n".join(new_lines)

    with open(MEMORY_FILE, "w") as f:
        f.write(content)


def update_memory_next_step(next_step: str):
    """Update next step instruction in MEMORY.md."""
    if not Path(MEMORY_FILE).exists():
        create_default_memory()

    with open(MEMORY_FILE) as f:
        content = f.read()

    new_lines = []
    for line in content.split("\n"):
        if "## 下一步指令" in line:
            in_next_step = True
            new_lines.append(line)
        elif in_next_step and line.startswith("- [") and "]" in line:
            new_lines.append(f"- [动作] {next_step}")
            in_next_step = False
        else:
            new_lines.append(line)
    content = "\n".join(new_lines)

    with open(MEMORY_FILE, "w") as f:
        f.write(content)


def update_memory_scratchpad(note: str):
    """Append note to scratchpad section in MEMORY.md."""
    if not Path(MEMORY_FILE).exists():
        create_default_memory()

    with open(MEMORY_FILE) as f:
        content = f.read()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_note = f"- [{timestamp}] {note}"

    # Find or create scratchpad section
    if "## 暂存与备忘区" in content:
        new_lines = []
        found_scratchpad = False
        for line in content.split("\n"):
            new_lines.append(line)
            if line.startswith("## 暂存与备忘区") and not found_scratchpad:
                found_scratchpad = True
                new_lines.append(new_note)
        content = "\n".join(new_lines)
    else:
        content += f"\n\n## 暂存与备忘区 (Scratchpad) [Free]\n{new_note}\n"

    with open(MEMORY_FILE, "w") as f:
        f.write(content)


def update_memory_last_action(action: str):
    """Update last action in MEMORY.md."""
    if not Path(MEMORY_FILE).exists():
        create_default_memory()

    with open(MEMORY_FILE) as f:
        content = f.read()

    # Add to archive instead
    append_to_archive(action)


def archive_task(task_file: str):
    """Move completed task to archive section."""
    ensure_tasks_dir()
    archive_dir = Path(TASKS_DIR) / "archive"
    archive_dir.mkdir(exist_ok=True)

    task_path = Path(task_file)
    if task_path.exists():
        # Read task content
        with open(task_path) as f:
            content = f.read()

        # Move to archive with timestamp
        ts = get_timestamp()
        archive_file = archive_dir / f"{ts}_{task_path.name}"
        with open(archive_file, "w") as f:
            f.write(content)

        # Remove original
        task_path.unlink()

        print(f"📦 Task archived: {archive_file}")


def append_to_archive(description: str):
    """Append completed task to archive."""
    ensure_tasks_dir()
    archive_path = Path(TASKS_DIR) / ARCHIVE_FILE

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n- [{timestamp}] {description}"

    if archive_path.exists():
        with open(archive_path) as f:
            content = f.read()
        # Find last entry and append
        content += entry
    else:
        content = f"# MEMORY Archive\n\n## Completed Tasks{entry}\n"

    with open(archive_path, "w") as f:
        f.write(content)


def append_to_scratchpad(note: str):
    """Append note to scratchpad."""
    update_memory_scratchpad(note)


def create_default_memory():
    """Create default MEMORY.md if it doesn't exist."""
    ensure_tasks_dir()

    content = """# MEMORY.md
<!-- 核心状态机与索引 -->

## Meta [Strict]
- 最后更新：[YYYY-MM-DD HH:MM]
- 项目画像：[一句话说明项目核心职责]
- 技术栈：[技术栈描述]

## 状态机 [Strict]
- **当前指针**：`MEMORY_TASKS/YYYYMMDD-HHMM_task.md`
- **全局目标**：[本阶段核心交付物]
- **最后状态**：[🔧 进行中 | ✅ 完成 | ❌ 错误 | ⚠️ 警告]

## 下一步指令 [Strict]
- [动作] `path/to/file` -> [函数/位置] 补充 [具体细节]

## 暂存与备忘区 (Scratchpad) [Free]
<!-- 留给 Agent 的自由发挥空间 -->

## 雷区与技术契约 [Strict/Append-only]
<!-- 只增不删 -->

## 已归档任务 [Strict/Append-only]
<!-- 保留最近 5-10 条记录 -->
"""

    with open(MEMORY_FILE, "w") as f:
        f.write(content)

    print(f"✅ Created default {MEMORY_FILE}")


def cmd_init():
    """Initialize MEMORY.md and MEMORY_TASKS/ directory."""
    ensure_tasks_dir()
    if Path(MEMORY_FILE).exists():
        print(f"⚠️  {MEMORY_FILE} already exists")
    else:
        create_default_memory()
    print(f"✅ {TASKS_DIR}/ directory ready")


def main():
    parser = argparse.ArgumentParser(description="MOSS_MEM - Memory Management")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # init command
    subparsers.add_parser("init", help="Initialize MEMORY.md and MEMORY_TASKS/")

    # start command
    start_parser = subparsers.add_parser("start", help="Start a new task")
    start_parser.add_argument("--description", "-d", required=True, help="Task description")
    start_parser.add_argument("--next-step", "-n", required=True, help="Next step instruction")

    # update command
    update_parser = subparsers.add_parser("update", help="Update task progress")
    update_parser.add_argument("--description", "-d", required=True, help="Progress description")
    update_parser.add_argument("--next-step", "-n", required=True, help="Next step instruction")
    update_parser.add_argument("--status", "-s", required=True, help="Status emoji")

    # complete command
    complete_parser = subparsers.add_parser("complete", help="Complete current task")
    complete_parser.add_argument("--description", "-d", required=True, help="Completion description")

    # add-note command
    note_parser = subparsers.add_parser("add-note", help="Add note to scratchpad")
    note_parser.add_argument("--note", "-n", required=True, help="Note content")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init()
    elif args.command == "start":
        cmd_start(args.description, args.next_step)
    elif args.command == "update":
        cmd_update(args.description, args.next_step, args.status)
    elif args.command == "complete":
        cmd_complete(args.description)
    elif args.command == "add-note":
        cmd_add_note(args.note)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

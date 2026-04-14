#!/usr/bin/env python3
"""
MOSS_MEM - Memory Management Script
Handles MEMORY.md and MEMORY_TASKS/ for project context persistence.
"""

import argparse
import atexit
import os
import signal
import sys
import json
from datetime import datetime
from pathlib import Path

MEMORY_FILE = "MEMORY.md"
TASKS_DIR = "MEMORY_TASKS"
ARCHIVE_FILE = "MEMORY_ARCHIVE.md"

# Auto-detect script location so callers don't need absolute paths
SCRIPT_DIR = Path(__file__).resolve().parent
# To invoke from anywhere, use: python3 "$(python3 -c "import os; print(os.path.dirname(os.path.abspath('~/.claude/skills/moss-mem/scripts/memory_manager.py'))))/memory_manager.py" <command>
# Or add to PATH: export PATH="$PATH:$HOME/.claude/skills/moss-mem/scripts"


def get_timestamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")


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
        except Exception:
            pass
    return False


def acquire_lock():
    """Acquire edit lock to prevent concurrent modifications. Uses O_EXCL for atomic creation."""
    ensure_tasks_dir()
    lock_file = Path(TASKS_DIR) / ".edit_lock"
    try:
        fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        with os.fdopen(fd, "w") as f:
            json.dump({"pid": os.getpid(), "time": datetime.now().isoformat()}, f)
        return True
    except FileExistsError:
        print(f"[ERROR] Lock already held by another process.")
        return False
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


def _signal_handler(signum, frame):
    """Release lock and exit on SIGTERM/SIGINT."""
    sig_name = signal.Signals(signum).name
    print(f"\n[INFO] Received {sig_name}, releasing lock and exiting.")
    release_lock()
    sys.exit(128 + signum)


signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)
atexit.register(release_lock)


# ---------------------------------------------------------------------------
# Core single-read-write update engine
# ---------------------------------------------------------------------------

def _memory_update(updates: dict):
    """
    Single read-modify-write for MEMORY.md — one read, one write.
    Uses section-based parsing: split content by ## headers, update each section.
    """
    if not Path(MEMORY_FILE).exists():
        _create_default_memory()

    with open(MEMORY_FILE) as f:
        original = f.read()

    scratchpad_notes = updates.get("scratchpad_notes", [])
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_scratch_lines = [f"- [{ts}] {n}" for n in scratchpad_notes]
    if new_scratch_lines:
        new_scratch_lines.append("")  # blank line before next section

    # ---- Parse content into sections ----
    sections = []
    lines = original.split("\n")
    n = len(lines)

    header_indices = []
    for idx, line in enumerate(lines):
        if line.startswith("## "):
            header_indices.append(idx)

    # Capture lines before the first section header
    pre_section = lines[:header_indices[0]] if header_indices else []

    for si, h_idx in enumerate(header_indices):
        header = lines[h_idx]
        body_start = h_idx + 1
        body_end = header_indices[si + 1] if si + 1 < len(header_indices) else n
        sections.append((header, lines[body_start:body_end], body_start, body_end))

    # ---- Apply updates to each section ----
    output_lines = []
    output_lines.extend(pre_section)  # include any lines before first ## header
    scratchpad_written = False

    for si, (header, body, _, _) in enumerate(sections):
        new_body = list(body)

        if header == "## Meta [Strict]":
            for i, line in enumerate(new_body):
                if "最后更新" in line and "touch" in updates:
                    new_body[i] = f"- 最后更新：{datetime.now().strftime('%Y-%m-%d %H:%M')}"

        elif header == "## 状态机 [Strict]":
            for i, line in enumerate(new_body):
                if "**当前指针**" in line and "pointer" in updates:
                    new_body[i] = f"- **当前指针**：`{updates['pointer']}`"
                elif "**最后动作**" in line and "last_action" in updates:
                    new_body[i] = f"- **最后动作**：{updates['last_action']}"
                elif "**最后状态**" in line and "status" in updates:
                    new_body[i] = f"- **最后状态**：{updates['status']}"

        elif header == "## 下一步指令 [Strict]":
            first_bullet_idx = -1
            for i, line in enumerate(new_body):
                if line.strip().startswith("-"):
                    first_bullet_idx = i
                    break
            if first_bullet_idx >= 0 and "next_step" in updates:
                new_body[first_bullet_idx] = f"- {updates['next_step']}"
            elif first_bullet_idx == -1 and "next_step" in updates:
                insert_at = 0
                while insert_at < len(new_body) and new_body[insert_at].strip() == "":
                    insert_at += 1
                new_body.insert(insert_at, f"- {updates['next_step']}")

        elif header.startswith("## 暂存与备忘区"):
            # Keep blank lines and HTML comments, discard old note entries
            new_body = [l for l in new_body if l.strip() == "" or l.strip().startswith("<!--")]
            new_body.extend(new_scratch_lines)
            scratchpad_written = True

        output_lines.append(header)
        output_lines.extend(new_body)

    # ---- Handle scratchpad notes if section didn't exist ----
    if new_scratch_lines and not scratchpad_written:
        output_lines.append("")
        output_lines.append("## 暂存与备忘区 (Scratchpad) [Free]")
        output_lines.extend(new_scratch_lines)

    with open(MEMORY_FILE, "w") as f:
        f.write("\n".join(output_lines))



def _create_default_memory():
    """Create default MEMORY.md if it doesn't exist."""
    ensure_tasks_dir()
    content = """# MEMORY.md
<!-- 核心状态机与索引 -->

## Meta [Strict]
- 最后更新：[YYYY-MM-DD HH:MM]
- 项目画像：[一句话说明项目核心职责]
- 技术栈：[技术栈描述]

## 状态机 [Strict]
- **当前指针**：`MEMORY_TASKS/YYYYMMDD-HHMMSS_task.md`
- **全局目标**：[本阶段核心交付物]
- **最后状态**：[🔧 进行中 | ✅ 完成 | ❌ 错误 | ⚠️ 警告]
- **最后动作**：[最近一次操作描述]

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


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_start(description: str, next_step: str):
    """Start a new task: create timestamped task file and update MEMORY.md."""
    ensure_tasks_dir()
    if check_concurrent_edit():
        print("[ERROR] Cannot start new task while another edit is in progress.")
        sys.exit(1)

    if not acquire_lock():
        print("[ERROR] Failed to acquire lock for start.")
        sys.exit(1)
    try:
        ts = get_timestamp()
        task_file = f"{TASKS_DIR}/{ts}_task.md"

        with open(task_file, "w") as f:
            f.write(f"---\nname: {ts}_task\ndescription: {description}\ntype: task\n---\n\n")
            f.write(f"# Task - {ts}\n\n")
            f.write(f"## Description\n{description}\n\n")
            f.write(f"## Next Step\n{next_step}\n\n")
            f.write(f"## Status\n🔧 In Progress\n\n")
            f.write(f"## Last Action\n<!-- 本次完成的具体操作，精确到函数/行 -->\n\n")
            f.write(f"## Key Decisions\n<!-- 重大决策及原因，后续 Agent 遵守不推翻 -->\n\n")
            f.write(f"## Landmines\n<!-- 已知的坑或危险区域，勿动 -->\n\n")
            f.write(f"## Created\n{datetime.now().isoformat()}\n\n")

        _memory_update({
            "pointer": task_file,
            "touch": True,
            "status": "🔧 In Progress",
            "last_action": f"Started: {description}",
        })

        print(f"✅ Task started: {task_file}")
        print(f"📝 Pointer updated in MEMORY.md")

    finally:
        release_lock()


def cmd_update(description: str, next_step: str, status: str,
               last_action: str = None, key_decisions: str = None, landmines: str = None):
    """Update current task progress in MEMORY.md."""
    if check_concurrent_edit():
        print("[ERROR] Cannot update while another edit is in progress.")
        sys.exit(1)

    if not acquire_lock():
        print("[ERROR] Failed to acquire lock for update.")
        sys.exit(1)
    try:
        _memory_update({
            "touch": True,
            "status": status,
            "next_step": next_step,
            "scratchpad_notes": [description],
        })

        # Write to task file if any handoff fields are provided
        if last_action or key_decisions or landmines:
            task_file = get_current_task_file()
            if task_file and Path(task_file).exists():
                _update_task_file(task_file, last_action, key_decisions, landmines)

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

    if not acquire_lock():
        print("[ERROR] Failed to acquire lock for complete.")
        sys.exit(1)
    try:
        current_task = get_current_task_file()
        if current_task:
            if Path(current_task).exists():
                _archive_task(current_task)
            else:
                print(f"[WARNING] Task file not found: {current_task} (pointer may be stale)")
        else:
            print(f"[WARNING] No current task pointer found in MEMORY.md")

        _append_to_archive(description)

        _memory_update({
            "touch": True,
            "status": "✅ Completed",
            "last_action": f"Completed: {description}",
        })

        print(f"✅ Task completed and archived")

    finally:
        release_lock()


def cmd_add_note(note: str):
    """Add a free-form note to MEMORY.md scratchpad."""
    if not acquire_lock():
        print("[ERROR] Failed to acquire lock for add-note.")
        sys.exit(1)
    try:
        _memory_update({"scratchpad_notes": [note]})
        print(f"✅ Note added to scratchpad")
    finally:
        release_lock()


def cmd_show(task_file: str = None):
    """Print task file to stdout for handoff review. Uses current task or --file."""
    if not task_file:
        task_file = get_current_task_file()
    if not task_file:
        print("[ERROR] No task file specified and no current pointer found in MEMORY.md")
        sys.exit(1)
    if not Path(task_file).exists():
        print(f"[ERROR] Task file not found: {task_file}")
        sys.exit(1)
    with open(task_file) as f:
        content = f.read()
    # Strip frontmatter for cleaner output
    lines = content.split("\n")
    if lines and lines[0] == "---":
        skip = 0
        for i, l in enumerate(lines[1:], 1):
            if l == "---":
                skip = i + 1
                break
        lines = lines[skip:]
    print("\n".join(lines))


# ---------------------------------------------------------------------------
# Task file utilities
# ---------------------------------------------------------------------------

def get_current_task_file():
    """Extract current task file path from MEMORY.md."""
    if not Path(MEMORY_FILE).exists():
        return None

    with open(MEMORY_FILE) as f:
        content = f.read()
        for line in content.split("\n"):
            if "**当前指针**" in line:
                # Try backtick extraction first (highest priority)
                if "`" in line:
                    start = line.find("`") + 1
                    end = line.rfind("`")
                    return line[start:end] if end > start else None
                # Fallback: split by either Chinese or English colon
                for sep in ("：", ":"):
                    if sep in line:
                        parts = line.split(sep)
                        if len(parts) > 1:
                            return parts[-1].strip()
    return None


def _update_task_file(task_file: str, last_action: str = None,
                      key_decisions: str = None, landmines: str = None):
    """Update handoff fields in the current task file.

    None = don't update, "" = clear placeholder, "content" = replace.
    """
    if not Path(task_file).exists():
        raise FileNotFoundError(f"Task file not found: {task_file}")

    with open(task_file) as f:
        content = f.read()

    lines = content.split("\n")
    output = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # last_action
        if line.strip().startswith("## Last Action"):
            output.append(line)
            i += 1
            while i < len(lines) and not lines[i].startswith("## ") and not lines[i].startswith("---"):
                i += 1
            if last_action is not None:
                output.append(last_action if last_action else "<!-- pending -->")
            continue
        # key_decisions
        if line.strip().startswith("## Key Decisions"):
            output.append(line)
            i += 1
            while i < len(lines) and not lines[i].startswith("## ") and not lines[i].startswith("---"):
                i += 1
            if key_decisions is not None:
                output.append(key_decisions if key_decisions else "<!-- pending -->")
            continue
        # landmines
        if line.strip().startswith("## Landmines"):
            output.append(line)
            i += 1
            while i < len(lines) and not lines[i].startswith("## ") and not lines[i].startswith("---"):
                i += 1
            if landmines is not None:
                output.append(landmines if landmines else "<!-- none -->")
            continue
        output.append(line)
        i += 1

    written = "\n".join(output)
    with open(task_file, "w") as f:
        f.write(written)

    # Verify write succeeded by reading back
    with open(task_file) as f:
        verified = f.read()
    if verified != written:
        raise RuntimeError(f"Write verification failed for {task_file}")


def _archive_task(task_file: str):
    """Move completed task to archive directory."""
    ensure_tasks_dir()
    archive_dir = Path(TASKS_DIR) / "archive"
    archive_dir.mkdir(exist_ok=True)

    task_path = Path(task_file)
    if task_path.exists():
        with open(task_path) as f:
            content = f.read()
        ts = get_timestamp()
        archive_file = archive_dir / f"{ts}_{task_path.name}"
        with open(archive_file, "w") as f:
            f.write(content)
        try:
            task_path.unlink()
        except FileNotFoundError:
            print(f"[WARNING] Task file already removed: {task_path}")
        print(f"📦 Task archived: {archive_file}")


def _append_to_archive(description: str):
    """Append completed task to archive. Atomic write via temp file + rename."""
    ensure_tasks_dir()
    archive_path = Path(TASKS_DIR) / ARCHIVE_FILE
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n- [{timestamp}] {description}"

    if archive_path.exists():
        with open(archive_path) as f:
            content = f.read()
        content += entry
    else:
        content = f"# MEMORY Archive\n\n## Completed Tasks{entry}\n"

    tmp_path = archive_path.with_suffix(".tmp")
    try:
        with open(tmp_path, "w") as f:
            f.write(content)
        os.replace(tmp_path, archive_path)
    except Exception as e:
        if tmp_path.exists():
            tmp_path.unlink()
        raise RuntimeError(f"Failed to write archive: {e}") from e


# ---------------------------------------------------------------------------
# Bootstrap / init
# ---------------------------------------------------------------------------

def cmd_init():
    """Initialize MEMORY.md and MEMORY_TASKS/ directory."""
    ensure_tasks_dir()
    archive_path = Path(TASKS_DIR) / ARCHIVE_FILE
    if not archive_path.exists():
        with open(archive_path, "w") as f:
            f.write(f"# MEMORY Archive\n\n## Completed Tasks\n")
        print(f"✅ {archive_path} created")
    if Path(MEMORY_FILE).exists():
        print(f"⚠️  {MEMORY_FILE} already exists")
    else:
        _create_default_memory()
    print(f"✅ {TASKS_DIR}/ directory ready")


# ---------------------------------------------------------------------------
# Aliases for backward compatibility (kept so other tools can call them)
# ---------------------------------------------------------------------------

def update_memory_pointer(timestamp: str, task_file: str):
    _memory_update({"pointer": task_file})


def update_memory_meta():
    _memory_update({"touch": True})


def update_memory_status(status: str):
    _memory_update({"status": status})


def update_memory_last_action(action: str):
    _memory_update({"last_action": action})


def update_memory_next_step(next_step: str):
    _memory_update({"next_step": next_step})


def update_memory_scratchpad(note: str):
    _memory_update({"scratchpad_notes": [note]})


def append_to_scratchpad(note: str):
    _memory_update({"scratchpad_notes": [note]})


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="MOSS_MEM - Memory Management")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    subparsers.add_parser("init", help="Initialize MEMORY.md and MEMORY_TASKS/")

    start_parser = subparsers.add_parser("start", help="Start a new task")
    start_parser.add_argument("--description", "-d", required=True, help="Task description")
    start_parser.add_argument("--next-step", "-n", required=True, help="Next step instruction")

    update_parser = subparsers.add_parser("update", help="Update task progress")
    update_parser.add_argument("--description", "-d", required=True, help="Progress description")
    update_parser.add_argument("--next-step", "-n", required=True, help="Next step instruction")
    update_parser.add_argument("--status", "-s", required=True, help="Status emoji")
    update_parser.add_argument("--last-action", "-l", default=None, help="Last action (writes to task file)")
    update_parser.add_argument("--key-decisions", "-k", default=None, help="Key decisions (writes to task file)")
    update_parser.add_argument("--landmines", "-m", default=None, help="Landmines (writes to task file)")

    complete_parser = subparsers.add_parser("complete", help="Complete current task")
    complete_parser.add_argument("--description", "-d", required=True, help="Completion description")

    note_parser = subparsers.add_parser("add-note", help="Add note to scratchpad")
    note_parser.add_argument("--note", "-n", required=True, help="Note content")

    show_parser = subparsers.add_parser("show", help="Show current task file (for handoff review)")
    show_parser.add_argument("--file", "-f", default=None, help="Specific task file to show (default: current pointer)")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init()
    elif args.command == "start":
        cmd_start(args.description, args.next_step)
    elif args.command == "update":
        cmd_update(args.description, args.next_step, args.status,
                getattr(args, 'last_action', None),
                getattr(args, 'key_decisions', None),
                getattr(args, 'landmines', None))
    elif args.command == "complete":
        cmd_complete(args.description)
    elif args.command == "add-note":
        cmd_add_note(args.note)
    elif args.command == "show":
        cmd_show(getattr(args, 'file', None))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
MOSS_MEM - Memory Management Script
Handles MEMORY.md and .moss-mem/ for project context persistence.
"""

import argparse
import atexit
import os
import shutil
import signal
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path

MEMORY_FILE = "MEMORY.md"
MOSS_DIR = ".moss-mem"
TASKS_DIR = ".moss-mem/tasks"
SUMMARIES_DIR = ".moss-mem/summaries"
INDEX_CACHE_DIR = ".moss-mem/index-cache"
ARCHIVE_FILE = "MEMORY_ARCHIVE.md"
OLD_TASKS_DIR = "MEMORY_TASKS"  # legacy — migrated on init

# Auto-detect script location so callers don't need absolute paths
SCRIPT_DIR = Path(__file__).resolve().parent
# To invoke from anywhere, call this script by absolute path from the installed skill directory.
# Or add the installed `moss-mem/scripts` directory to PATH.


def get_timestamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def ensure_tasks_dir():
    Path(TASKS_DIR).mkdir(parents=True, exist_ok=True)


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
- **当前指针**：`.moss-mem/tasks/YYYYMMDD-HHMMSS_task.md`
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
            f.write(f"## Last Action\n<!-- pending -->\n\n")
            f.write(f"## Key Decisions\n<!-- pending -->\n\n")
            f.write(f"## Landmines\n<!-- none -->\n\n")
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


def cmd_recover():
    """Automated interrupt recovery: inspect git state and guide task file reconstruction."""
    print("=== Interrupt Recovery ===")

    # Check lock file first
    lock_file = Path(TASKS_DIR) / ".edit_lock"
    if lock_file.exists():
        print(f"⚠️  Lock file exists: {lock_file}")
        print("   If the previous process was killed, delete it with:")
        print(f"   rm {lock_file}")
        print()

    # Check current task
    task_file = get_current_task_file()
    if task_file:
        print(f"Current task pointer: {task_file}")
        if Path(task_file).exists():
            print("Task file exists.")
            with open(task_file) as f:
                content = f.read()
            # Check if Last Action is empty
            if "## Last Action" in content:
                la_start = content.find("## Last Action")
                la_end = content.find("## ", la_start + 1)
                la_section = content[la_start:la_end] if la_end > 0 else content[la_start:]
                if "<!--" in la_section and "-->" in la_section:
                    print("⚠️  ## Last Action is empty (pending). Fill it before continuing.")
            else:
                print("⚠️  Task file has no ## Last Action section.")
        else:
            print(f"⚠️  Task file not found: {task_file} (stale pointer)")
    else:
        print("No current task pointer found.")

    print()
    print("=== Git State ===")

    # Run git commands to gather context
    import subprocess

    try:
        result = subprocess.run(["git", "diff", "HEAD", "--stat"],
                              capture_output=True, text=True, timeout=10)
        if result.stdout.strip():
            print("Uncommitted changes:")
            print(result.stdout)
        else:
            print("No uncommitted changes.")
    except Exception as e:
        print(f"(git diff unavailable: {e})")

    try:
        result = subprocess.run(["git", "log", "--oneline", "-5"],
                              capture_output=True, text=True, timeout=10)
        if result.stdout.strip():
            print("Recent commits:")
            print(result.stdout)
    except Exception as e:
        print(f"(git log unavailable: {e})")

    try:
        result = subprocess.run(["git", "stash", "list"],
                              capture_output=True, text=True, timeout=10)
        if result.stdout.strip():
            print("Stashed changes:")
            print(result.stdout)
    except Exception as e:
        print(f"(git stash unavailable: {e})")

    print()
    print("After reviewing git state, run:")
    print("  moss-mem update -d 'recovered context' -n '<next step>' -s '🔧'")
    print("to fill in the task file with recovery information.")


# ---------------------------------------------------------------------------
# Memory-only compatibility commands
# ---------------------------------------------------------------------------


def _touch_gitkeep(directory: Path, created: list | None = None, skipped: list | None = None):
    """Ensure a directory exists and is retained by git when empty."""
    directory.mkdir(parents=True, exist_ok=True)
    gitkeep = directory / ".gitkeep"
    if gitkeep.exists():
        if skipped is not None:
            skipped.append(str(gitkeep))
    else:
        gitkeep.write_text("")
        if created is not None:
            created.append(str(gitkeep))


REQUIRED_MEMORY_PATHS = [
    (MEMORY_FILE, "file"),
    (MOSS_DIR, "dir"),
    (TASKS_DIR, "dir"),
    (str(Path(TASKS_DIR) / ARCHIVE_FILE), "file"),
    (SUMMARIES_DIR, "dir"),
    (INDEX_CACHE_DIR, "dir"),
]


def cmd_knowledge_init(domain: str = None):
    """Compatibility alias: initialize moss-mem memory directories only."""
    if domain:
        print(f"[INFO] --domain {domain!r} is ignored; moss-mem no longer scaffolds project docs.")
    cmd_init()
    Path(SUMMARIES_DIR).mkdir(parents=True, exist_ok=True)
    Path(INDEX_CACHE_DIR).mkdir(parents=True, exist_ok=True)
    for directory in [Path(TASKS_DIR), Path(SUMMARIES_DIR), Path(INDEX_CACHE_DIR)]:
        gitkeep = directory / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.write_text("")
    print("✅ moss-mem memory layout ready: MEMORY.md + .moss-mem/{tasks,summaries,index-cache}/")
    print("ℹ️  AGENTS.md and project docs are external; moss-mem reads them only when present.")


def cmd_knowledge_index():
    """Regenerate a memory-only index under .moss-mem/index-cache/."""
    ensure_tasks_dir()
    Path(SUMMARIES_DIR).mkdir(parents=True, exist_ok=True)
    Path(INDEX_CACHE_DIR).mkdir(parents=True, exist_ok=True)
    index_path = Path(INDEX_CACHE_DIR) / "memory-index.md"
    task_files = sorted(Path(TASKS_DIR).glob("*_task.md"))
    summary_files = sorted(Path(SUMMARIES_DIR).glob("*.md"))
    lines = [
        "# moss-mem Memory Index",
        "",
        "Generated from `.moss-mem/tasks/` and `.moss-mem/summaries/`.",
        "Do not hand-edit; rerun `moss-mem knowledge-index`.",
        "",
        "## Tasks",
    ]
    if task_files:
        lines.extend(f"- `{p}`" for p in task_files)
    else:
        lines.append("- <!-- none -->")
    lines.extend(["", "## Summaries"])
    if summary_files:
        lines.extend(f"- `{p}`" for p in summary_files)
    else:
        lines.append("- <!-- none -->")
    index_path.write_text("\n".join(lines) + "\n")
    print(f"✅ Memory index written: {index_path}")


def cmd_knowledge_check(strict: bool = False):
    """Validate moss-mem memory layout only."""
    errors = []
    warnings = []
    for raw_path, kind in REQUIRED_MEMORY_PATHS:
        path = Path(raw_path)
        if kind == "file" and not path.is_file():
            errors.append(f"missing file: {raw_path}")
        elif kind == "dir" and not path.is_dir():
            errors.append(f"missing directory: {raw_path}")

    agents_path = Path("AGENTS.md")
    if agents_path.exists():
        print("ℹ️  AGENTS.md found; moss-mem treats it as read-only external context")

    index_path = Path(INDEX_CACHE_DIR) / "memory-index.md"
    sources = []
    for root in [Path(TASKS_DIR), Path(SUMMARIES_DIR)]:
        if root.exists():
            sources.extend(p for p in root.rglob("*.md") if p.is_file())
    if index_path.exists() and sources:
        index_mtime = index_path.stat().st_mtime_ns
        newer = [p for p in sources if p.stat().st_mtime_ns > index_mtime]
        if newer:
            warnings.append(f"memory index is stale; newer source: {max(newer, key=lambda p: p.stat().st_mtime_ns)}")
        else:
            print("✅ memory index is fresh")

    if warnings:
        print("\n⚠️  Warnings:")
        for warning in warnings:
            print(f"   • {warning}")
    if errors:
        print("\n❌ Memory layout check failed:")
        for error in errors:
            print(f"   • {error}")
        print("\nRun: moss-mem init")
        sys.exit(1)
    if strict and warnings:
        sys.exit(1)
    print("✅ moss-mem memory layout ok")


def _slugify_topic(topic: str) -> str:
    cleaned = []
    for ch in topic.lower():
        if ch.isascii() and ch.isalnum():
            cleaned.append(ch)
        elif ch in {" ", "-", "_", "."}:
            cleaned.append("-")
    slug = "".join(cleaned).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug[:80] or "summary"


def _yaml_scalar(value: str) -> str:
    """Return a conservative double-quoted YAML scalar."""
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def cmd_summary_capture(topic: str, summary: str, source: str = "harness", decisions: str = "", next_step: str = "", related: str = ""):
    """Capture a harness/session summary into .moss-mem/summaries/."""
    Path(SUMMARIES_DIR).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    filename_ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = _slugify_topic(topic)
    summary_path = Path(SUMMARIES_DIR) / f"{filename_ts}-{slug}.md"

    related_lines = []
    for item in related.split(","):
        item = item.strip()
        if item:
            related_lines.append(f"- `{item}`")
    if not related_lines:
        related_lines.append("- <!-- none -->")

    content = "\n".join([
        "---",
        f"topic: {_yaml_scalar(topic)}",
        f"source: {_yaml_scalar(source)}",
        f"created: {_yaml_scalar(timestamp)}",
        "type: harness-summary",
        "---",
        "",
        f"# Harness Summary - {topic}",
        "",
        "## Source",
        source,
        "",
        "## Summary",
        summary,
        "",
        "## Decisions",
        decisions if decisions else "<!-- none -->",
        "",
        "## Next Step",
        next_step if next_step else "<!-- pending -->",
        "",
        "## Related Files",
        *related_lines,
        "",
        "## MemPalace Sync",
        f"Run: `mempalace mine .moss-mem/summaries/ --mode convos --extract general --wing <project>`",
        "",
    ])
    summary_path.write_text(content)
    print(f"✅ Harness summary captured: {summary_path}")
    print("🔎 Next: mine `.moss-mem/summaries/` into MemPalace before handoff if MCP/CLI is available.")

def _git_diff_summary():
    """Get summary of uncommitted changes."""
    try:
        result = subprocess.run(["git", "diff", "--stat", "HEAD"],
                              capture_output=True, text=True, timeout=10)
        return result.stdout.strip() if result.stdout.strip() else None
    except Exception:
        return None


def _git_log_summary(n=5):
    """Get recent commit messages."""
    try:
        result = subprocess.run(["git", "log", f"--oneline", f"-{n}"],
                              capture_output=True, text=True, timeout=10)
        return result.stdout.strip() if result.stdout.strip() else None
    except Exception:
        return None


def _git_new_dirs():
    """Detect newly created directories from git diff (heuristic for architectural decisions)."""
    try:
        result = subprocess.run(["git", "diff", "--name-status", "HEAD"],
                              capture_output=True, text=True, timeout=10)
        lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
        new_dirs = [l.split("\t")[1].rsplit("/", 1)[0] for l in lines
                   if l.startswith("A") and "/" in l.split("\t")[1]]
        return list(set(new_dirs)) if new_dirs else None
    except Exception:
        return None


def cmd_check(task_file: str = None, fix: bool = False):
    """Validate task file completeness. Exit 0 if complete, 1 if incomplete.
    With --fix: auto-fill empty fields using git-derived content."""
    if not task_file:
        task_file = get_current_task_file()
    if not task_file:
        print("[ERROR] No task file specified and no current pointer found.")
        sys.exit(1)
    if not Path(task_file).exists():
        print(f"[ERROR] Task file not found: {task_file}")
        sys.exit(1)

    with open(task_file) as f:
        content = f.read()

    issues = []
    fix_applied = []

    # Check Last Action
    if "## Last Action" in content:
        la_start = content.find("## Last Action")
        la_end = content.find("## ", la_start + 1)
        la_section = content[la_start:la_end] if la_end > 0 else content[la_start:]
        if "<!--" in la_section and "-->" in la_section and "pending" in la_section.lower():
            if fix:
                diff = _git_diff_summary()
                if diff:
                    inferred = f"Uncommitted changes: {diff.split(chr(10))[0]}"
                    content = content.replace("## Last Action\n<!-- pending -->", f"## Last Action\n{inferred}")
                    fix_applied.append(f"## Last Action → '{inferred[:60]}...'")
                else:
                    issues.append("## Last Action is still <!-- pending --> (no git diff to infer from)")
            else:
                issues.append("## Last Action is still <!-- pending -->")

    # Check Key Decisions
    if "## Key Decisions" in content:
        kd_start = content.find("## Key Decisions")
        kd_end = content.find("## ", kd_start + 1)
        kd_section = content[kd_start:kd_end] if kd_end > 0 else content[kd_start:]
        if "<!--" in kd_section and "-->" in kd_section and "none" in kd_section.lower():
            if fix:
                new_dirs = _git_new_dirs()
                if new_dirs:
                    inferred = "Architectural decisions from uncommitted changes:\n" + "\n".join([f"- New directory created: {d}/ (review if it implies a module boundary)" for d in new_dirs[:5]])
                    content = content.replace("## Key Decisions\n<!-- none -->", f"## Key Decisions\n{inferred}")
                    fix_applied.append(f"## Key Decisions → inferred {len(new_dirs)} new dir(s)")
                else:
                    issues.append("## Key Decisions is still <!-- none --> (no architectural signals in git diff)")
            else:
                issues.append("## Key Decisions is still <!-- none -->")

    # Check Landmines
    if "## Landmines" in content:
        lm_start = content.find("## Landmines")
        lm_end = content.find("## ", lm_start + 1)
        lm_section = content[lm_start:lm_end] if lm_end > 0 else content[lm_start:]
        if "<!--" in lm_section and "-->" in lm_section and "none" in lm_section.lower():
            if fix:
                new_dirs = _git_new_dirs()
                log = _git_log_summary(3)
                if new_dirs or log:
                    parts = []
                    if new_dirs:
                        parts.append("New/changed directories (may need attention): " + ", ".join(new_dirs[:5]))
                    if log:
                        parts.append(f"Recent commits:\n{log}")
                    inferred = "\n".join(parts)
                    content = content.replace("## Landmines\n<!-- none -->", f"## Landmines\n{inferred}")
                    fix_applied.append("## Landmines → filled from git state")
                else:
                    issues.append("## Landmines is still <!-- none --> (no git state to infer from)")
            else:
                issues.append("## Landmines is still <!-- none -->")

    if fix_applied:
        with open(task_file, "w") as f:
            f.write(content)
        print("✅ Auto-fix applied:")
        for f_msg in fix_applied:
            print(f"   - {f_msg}")

    if issues:
        print("⚠️  Task file incomplete:")
        for issue in issues:
            print(f"   - {issue}")
        sys.exit(1)
    else:
        print("✅ Task file is complete.")
        sys.exit(0)


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

def _migrate_old_tasks_dir():
    """Migrate legacy MEMORY_TASKS/ → .moss-mem/tasks/ if needed."""
    old_path = Path(OLD_TASKS_DIR)
    new_path = Path(TASKS_DIR)

    if not old_path.exists() or not old_path.is_dir():
        return

    if new_path.exists():
        print(f"⚠️  Both {OLD_TASKS_DIR}/ and {TASKS_DIR}/ exist — manual merge required.")
        print(f"   Remove {OLD_TASKS_DIR}/ if {TASKS_DIR}/ is up to date.")
        return

    print(f"⚠️  Legacy {OLD_TASKS_DIR}/ exists outside moss-mem ownership.")
    print(f"   moss-mem will not move or delete it automatically.")
    print(f"   To migrate manually: mkdir -p {TASKS_DIR} && cp -R {OLD_TASKS_DIR}/. {TASKS_DIR}/")

    print(f"   MEMORY.md pointers to {OLD_TASKS_DIR}/ are left unchanged until you migrate files manually.")


def cmd_init():
    """Initialize MEMORY.md and .moss-mem/tasks/ directory."""
    # Ensure .moss-mem/ parent exists
    Path(MOSS_DIR).mkdir(exist_ok=True)

    # Migration: if old MEMORY_TASKS/ exists, move it BEFORE creating new dir
    _migrate_old_tasks_dir()

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

    subparsers.add_parser("init", help="Initialize MEMORY.md and .moss-mem/tasks/")

    start_parser = subparsers.add_parser("start", help="Start a new task")
    start_parser.add_argument("--description", "-d", required=False, default="(待补)", help="Task description; defaults to placeholder you can fill in via update")
    start_parser.add_argument("--next-step", "-n", required=False, default="等待下一步指令", help="Next step instruction; defaults to placeholder you can fill in via update")

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

    subparsers.add_parser("recover", help="Automated interrupt recovery")

    check_parser = subparsers.add_parser("check", help="Validate task file completeness")
    check_parser.add_argument("--file", "-f", default=None, help="Specific task file to check (default: current pointer)")
    check_parser.add_argument("--fix", action="store_true", help="Auto-fill empty fields with git-derived content")

    knowledge_init_parser = subparsers.add_parser("knowledge-init", help="Compatibility alias for memory init")
    knowledge_init_parser.add_argument("--domain", "-d", default=None, choices=["web", "mobile", "api", "cli"],
                                       help="Ignored compatibility option")

    subparsers.add_parser("knowledge-index", help="Regenerate .moss-mem/index-cache/memory-index.md")

    knowledge_check_parser = subparsers.add_parser("knowledge-check", help="Validate moss-mem memory layout")
    knowledge_check_parser.add_argument("--strict", action="store_true", help="Fail when memory index warnings are present")

    summary_parser = subparsers.add_parser("summary-capture", help="Capture a harness/session summary into .moss-mem/summaries/")
    summary_parser.add_argument("--topic", "-t", required=True, help="Short summary topic")
    summary_parser.add_argument("--summary", "-s", required=True, help="Compressed session or harness summary")
    summary_parser.add_argument("--source", default="harness", help="Summary source, e.g. codex-harness or session-stop")
    summary_parser.add_argument("--decisions", default="", help="Key decisions captured in the summary")
    summary_parser.add_argument("--next-step", "-n", default="", help="Next concrete step")
    summary_parser.add_argument("--related", default="", help="Comma-separated related file paths")

    # ── v4: declarative state subcommand ──
    state_parser = subparsers.add_parser("state", help="Declarative state API (v4)")
    state_subs = state_parser.add_subparsers(dest="state_action", help="State actions")

    state_subs.add_parser("init", help="Initialize MEMORY.md and .moss-mem/ (alias for 'init')")
    state_subs.add_parser("show", help="Show current task (alias for 'show')")

    state_set_parser = state_subs.add_parser("set", help="Set one or more state fields (key=value pairs)")
    state_set_parser.add_argument("pairs", nargs="*", help="Field assignments like current_task=\"...\" next_step=\"...\"")
    # Legacy friendly flags — still supported for compatibility
    state_set_parser.add_argument("--description", "-d", default=None, help="= current_task")
    state_set_parser.add_argument("--next-step", "-n", default=None, help="= next_step")
    state_set_parser.add_argument("--status", "-s", default=None, help="Status emoji")
    state_set_parser.add_argument("--last-action", "-l", default=None)
    state_set_parser.add_argument("--key-decisions", "-k", default=None)
    state_set_parser.add_argument("--landmines", "-m", default=None)

    state_commit_parser = state_subs.add_parser("commit", help="Snapshot current state to a new task file")
    state_commit_parser.add_argument("-m", "--message", required=True, help="One-line commit summary")

    state_note_parser = state_subs.add_parser("note", help="Append timestamped note (alias for 'add-note')")
    state_note_parser.add_argument("text", nargs="?", default=None, help="Note text (or pass via --note/-n)")
    state_note_parser.add_argument("--note", "-n", default=None, help="Note content (legacy flag)")

    state_validate_parser = state_subs.add_parser("validate", help="Validate handoff fields (alias for 'check')")
    state_validate_parser.add_argument("--fix", action="store_true", help="Auto-fill from git")
    state_validate_parser.add_argument("--file", "-f", default=None)

    state_subs.add_parser("recover", help="Interrupt recovery (alias for 'recover')")

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
    elif args.command == "recover":
        cmd_recover()
    elif args.command == "check":
        cmd_check(getattr(args, 'file', None), getattr(args, 'fix', False))
    elif args.command == "knowledge-init":
        cmd_knowledge_init(getattr(args, 'domain', None))
    elif args.command == "knowledge-index":
        cmd_knowledge_index()
    elif args.command == "knowledge-check":
        cmd_knowledge_check(getattr(args, 'strict', False))
    elif args.command == "summary-capture":
        cmd_summary_capture(args.topic, args.summary, args.source, args.decisions, args.next_step, args.related)
    elif args.command == "state":
        # ── v4 state dispatcher ──
        action = getattr(args, "state_action", None)
        if action is None:
            state_parser.print_help()
            sys.exit(1)

        if action == "init":
            cmd_init()
        elif action == "show":
            cmd_show(None)
        elif action == "set":
            # Auto-init: if MEMORY.md is missing, create it before setting fields.
            # Lets a fresh project call `state set current_task="…"` as the very first
            # command without a separate `state init` round-trip.
            if not os.path.exists(MEMORY_FILE):
                cmd_init()

            # Collect field values: from pairs (k=v) and from legacy flags
            # Map old field names to new schema
            field_map = {
                "current_task": args.description,
                "next_step": args.next_step,
                "status": args.status,
                "last_action": args.last_action,
                "key_decisions": args.key_decisions,
                "landmines": args.landmines,
            }
            for pair in (args.pairs or []):
                if "=" not in pair:
                    print(f"[ERROR] state set expects key=value, got: {pair}")
                    sys.exit(1)
                k, _, v = pair.partition("=")
                field_map[k.strip()] = v.strip().strip('"').strip("'")

            # If status is being set, complete the task. Otherwise update.
            if field_map.get("status") in ("✅", "✅ Completed"):
                desc = field_map.get("current_task") or field_map.get("last_action") or "Completed"
                cmd_complete(desc)
            else:
                # Treat as update — required: description + next_step + status
                desc = field_map.get("current_task") or "(待补)"
                nxt = field_map.get("next_step") or "等待下一步指令"
                st = field_map.get("status") or "🔧 In Progress"
                cmd_update(desc, nxt, st,
                          field_map.get("last_action"),
                          field_map.get("key_decisions"),
                          field_map.get("landmines"))
        elif action == "commit":
            # Auto-init: same logic as `state set` — first commit on a fresh project
            # should not require a separate `state init` round-trip.
            if not os.path.exists(MEMORY_FILE):
                cmd_init()
            # commit = start a new task file with the current state
            cmd_start(args.message, "继续推进")
            # then update with the message as last_action
            cmd_update(args.message, "继续推进", "🔧 In Progress", args.message, None, None)
        elif action == "note":
            text = args.text or args.note
            if not text:
                print("[ERROR] state note requires text argument or --note/-n")
                sys.exit(1)
            cmd_add_note(text)
        elif action == "validate":
            cmd_check(getattr(args, "file", None), getattr(args, "fix", False))
        elif action == "recover":
            cmd_recover()
        else:
            state_parser.print_help()
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

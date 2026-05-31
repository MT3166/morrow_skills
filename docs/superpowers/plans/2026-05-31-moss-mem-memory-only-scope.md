# moss-mem Memory-Only Scope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Narrow moss-mem so it creates and depends only on root `MEMORY.md` plus `.moss-mem/**`, with `AGENTS.md` treated as optional read-only external context.

**Architecture:** Remove broad project-documentation scaffold ownership from moss-mem core. Keep task lifecycle, handoff, summaries, search/mine fallback, and memory health checks under `.moss-mem/`. Deprecate `knowledge-init`, `knowledge-index`, and `knowledge-check` as project-doc commands by replacing them with memory-only behavior and clear messages.

**Tech Stack:** Python stdlib CLI (`moss-mem/scripts/memory_manager.py`), Markdown skill instructions (`moss-mem/SKILL.md`), JSON prompt tests (`moss-mem/test-prompts.json`), git.

---

## File Structure

- Modify: `moss-mem/scripts/memory_manager.py` — path constants, command behavior, required health checks, removal/deprecation of docs scaffold templates.
- Modify: `moss-mem/SKILL.md` — document memory-only ownership and remove docs-as-system-of-record workflow.
- Modify: `moss-mem/test-prompts.json` — replace docs scaffold prompts with memory-only prompts.
- Do not modify: `/Users/mt/.claude/skills/moss-mem` installed runtime copy unless explicitly requested later.
- Do not add: `AGENTS.md`, `ARCHITECTURE.md`, root `docs/`, or `.moss-mem/docs/` as moss-mem managed files.

## Task 1: Narrow CLI Behavior to Memory-Only Paths

**Files:**
- Modify: `moss-mem/scripts/memory_manager.py`

- [ ] **Step 1: Inspect current command surface**

Run:
```bash
rg -n "ROOT_KNOWLEDGE_TEMPLATES|DOCS_KNOWLEDGE_TEMPLATES|DOMAIN_REFERENCE_TEMPLATES|cmd_knowledge_init|cmd_knowledge_index|cmd_knowledge_check|REQUIRED_HARNESS_PATHS|knowledge-init|knowledge-index|knowledge-check|AGENTS.md|ARCHITECTURE.md|docs/" moss-mem/scripts/memory_manager.py
```
Expected: shows the broad docs scaffold code to remove or rewrite.

- [ ] **Step 2: Replace broad required paths with memory required paths**

In `moss-mem/scripts/memory_manager.py`, replace `REQUIRED_HARNESS_PATHS` with:
```python
REQUIRED_MEMORY_PATHS = [
    (MEMORY_FILE, "file"),
    (MOSS_DIR, "dir"),
    (TASKS_DIR, "dir"),
    (str(Path(TASKS_DIR) / ARCHIVE_FILE), "file"),
    (SUMMARIES_DIR, "dir"),
    (INDEX_CACHE_DIR, "dir"),
]
```
Expected: no `AGENTS.md`, `ARCHITECTURE.md`, or `docs/**` required by moss-mem health checks.

- [ ] **Step 3: Make `knowledge-init` memory-only or deprecated**

Replace `cmd_knowledge_init(domain: str = None)` body with memory-only behavior:
```python
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
```
Expected: the command remains backward-compatible but no longer creates `AGENTS.md`, `ARCHITECTURE.md`, or `docs/`.

- [ ] **Step 4: Replace `knowledge-index` with memory-index cache**

Replace `cmd_knowledge_index()` body with memory-only index generation:
```python
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
    lines.extend(f"- `{p}`" for p in task_files) or lines.append("- <!-- none -->")
    lines.extend(["", "## Summaries"])
    lines.extend(f"- `{p}`" for p in summary_files) or lines.append("- <!-- none -->")
    index_path.write_text("\n".join(lines) + "\n")
    print(f"✅ Memory index written: {index_path}")
```
Expected: no `docs/index.md` reads/writes.

- [ ] **Step 5: Replace `knowledge-check` with memory health check**

Rewrite `cmd_knowledge_check(strict: bool = False)` to check `REQUIRED_MEMORY_PATHS`, optional root `AGENTS.md` read-only presence, and generated memory index freshness:
```python
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
```
Expected: `knowledge-check` no longer validates broad project docs.

- [ ] **Step 6: Remove unused broad docs template code**

Delete or stop referencing these definitions if unused:
```text
ROOT_KNOWLEDGE_TEMPLATES
DOCS_KNOWLEDGE_TEMPLATES
DOMAIN_REFERENCE_TEMPLATES
_collect_index_file
_docs_index_link
_knowledge_source_files
_scan_placeholder_markers
PLACEHOLDER_MARKERS
```
Expected: `rg "AGENTS.md|ARCHITECTURE.md|docs/" moss-mem/scripts/memory_manager.py` returns only legacy/help text if intentionally kept, not creation/required paths.

- [ ] **Step 7: Run CLI validation**

Run:
```bash
python3 -m py_compile moss-mem/scripts/memory_manager.py
python3 - <<'PY'
import tempfile, subprocess, pathlib, os, sys
script = pathlib.Path('moss-mem/scripts/memory_manager.py').resolve()
with tempfile.TemporaryDirectory() as td:
    subprocess.run([sys.executable, str(script), 'knowledge-init', '--domain', 'web'], cwd=td, check=True)
    assert pathlib.Path(td, 'MEMORY.md').is_file()
    assert pathlib.Path(td, '.moss-mem/tasks').is_dir()
    assert pathlib.Path(td, '.moss-mem/tasks/MEMORY_ARCHIVE.md').is_file()
    assert pathlib.Path(td, '.moss-mem/summaries/.gitkeep').is_file()
    assert pathlib.Path(td, '.moss-mem/index-cache/.gitkeep').is_file()
    assert not pathlib.Path(td, 'AGENTS.md').exists()
    assert not pathlib.Path(td, 'ARCHITECTURE.md').exists()
    assert not pathlib.Path(td, 'docs').exists()
    subprocess.run([sys.executable, str(script), 'knowledge-check'], cwd=td, check=True)
    subprocess.run([sys.executable, str(script), 'knowledge-index'], cwd=td, check=True)
    assert pathlib.Path(td, '.moss-mem/index-cache/memory-index.md').is_file()
print('memory-only cli ok')
PY
```
Expected: prints `memory-only cli ok`.

- [ ] **Step 8: Commit CLI narrowing**

Run:
```bash
git add moss-mem/scripts/memory_manager.py
git commit -m "fix(moss-mem): limit managed files to memory state"
```
Expected: commit contains only `memory_manager.py`.

## Task 2: Update SKILL.md to Memory-Only Ownership

**Files:**
- Modify: `moss-mem/SKILL.md`

- [ ] **Step 1: Find docs-scaffold language**

Run:
```bash
rg -n "Four-layer|docs/|AGENTS.md|ARCHITECTURE.md|knowledge-init|knowledge-index|knowledge-check|system of record|product-specs|exec-plans|references/|DESIGN.md|SECURITY.md" moss-mem/SKILL.md
```
Expected: identifies sections to rewrite.

- [ ] **Step 2: Rewrite TL;DR and file tree**

Change the opening model to:
```markdown
Two-layer memory: **MEMORY.md** as the always-available startup state + **.moss-mem/** as the project-local memory store. MemPalace MCP/CLI can index, search, and mirror those files, but moss-mem never depends on MemPalace availability. `AGENTS.md` and project docs are external read-only context when present; moss-mem does not create or manage them.
```

Use this file tree:
```markdown
MEMORY.md
.moss-mem/
  tasks/
    MEMORY_ARCHIVE.md
    archive/
    .edit_lock
  summaries/
  index-cache/
```
Expected: no root docs scaffold shown as moss-mem-managed.

- [ ] **Step 3: Rewrite knowledge operation sections as memory operations**

Replace `knowledge-init/index/check` descriptions:
```markdown
**knowledge-init** — Compatibility alias for memory init
Creates `MEMORY.md`, `.moss-mem/tasks/`, `.moss-mem/summaries/`, and `.moss-mem/index-cache/`. It does not create `AGENTS.md`, `ARCHITECTURE.md`, or `docs/`.

**knowledge-index** — Regenerate `.moss-mem/index-cache/memory-index.md` from `.moss-mem/tasks/` and `.moss-mem/summaries/`.

**knowledge-check** — Validate memory layout only: `MEMORY.md`, `.moss-mem/tasks/`, `.moss-mem/tasks/MEMORY_ARCHIVE.md`, `.moss-mem/summaries/`, `.moss-mem/index-cache/`. `AGENTS.md` is optional read-only context.
```
Expected: docs scaffold responsibilities gone.

- [ ] **Step 4: Update anti-patterns and troubleshooting**

Ensure SKILL.md explicitly says:
```markdown
- Do not create, move, or edit `AGENTS.md`; read it only if present.
- Do not create root `docs/`, `ARCHITECTURE.md`, product specs, design docs, or plan docs as part of moss-mem.
- Do not store moss-mem state outside `.moss-mem/` except `MEMORY.md`.
```
Expected: user constraint encoded as a red-line.

- [ ] **Step 5: Runtime-neutral scan**

Run:
```bash
grep -nE "(在 Claude Code|Claude Code skill|Claude Code 用户|Cursor only|Codex 中|^\[!\[Claude Code|~/\.claude/skills/[a-z]|/plugin install\b)" moss-mem/SKILL.md moss-mem/README.md 2>/dev/null || true
```
Expected: no output.

- [ ] **Step 6: Commit SKILL.md update**

Run:
```bash
git add moss-mem/SKILL.md
git commit -m "docs(moss-mem): document memory-only ownership"
```
Expected: commit contains only `SKILL.md`.

## Task 3: Update Test Prompts to Memory-Only Expectations

**Files:**
- Modify: `moss-mem/test-prompts.json`

- [ ] **Step 1: Replace docs scaffold prompts**

Update prompt expectations:
- id 10: expect `knowledge-init --domain web` to create only `MEMORY.md`, `.moss-mem/tasks/`, `.moss-mem/summaries/`, `.moss-mem/index-cache/`; explicitly not `AGENTS.md`, `ARCHITECTURE.md`, or `docs/`.
- id 12: change prompt to “我新增了一条 session summary，帮我刷新 moss-mem memory index 并说明 MemPalace 该怎么同步”; expect `knowledge-index` writes `.moss-mem/index-cache/memory-index.md`, then `mempalace mine .moss-mem/ --wing <project>` or more specific tasks/summaries mines.
- id 13: expect `knowledge-check` validates memory layout and stale `.moss-mem/index-cache/memory-index.md`; no `docs/DESIGN.md`.

- [ ] **Step 2: Validate JSON**

Run:
```bash
python3 -m json.tool moss-mem/test-prompts.json >/dev/null
```
Expected: exits 0.

- [ ] **Step 3: Commit prompt update**

Run:
```bash
git add moss-mem/test-prompts.json
git commit -m "test(moss-mem): align prompts with memory-only scope"
```
Expected: commit contains only `test-prompts.json`.

## Task 4: Final Validation and Handoff

**Files:**
- Read-only validation across `moss-mem/*`

- [ ] **Step 1: Run final validations**

Run:
```bash
python3 -m py_compile moss-mem/scripts/memory_manager.py
python3 -m json.tool moss-mem/test-prompts.json >/dev/null
grep -nE "(在 Claude Code|Claude Code skill|Claude Code 用户|Cursor only|Codex 中|^\[!\[Claude Code|~/\.claude/skills/[a-z]|/plugin install\b)" moss-mem/SKILL.md moss-mem/README.md 2>/dev/null || true
python3 - <<'PY'
import tempfile, subprocess, pathlib, sys
script = pathlib.Path('moss-mem/scripts/memory_manager.py').resolve()
with tempfile.TemporaryDirectory() as td:
    subprocess.run([sys.executable, str(script), 'knowledge-init', '--domain', 'web'], cwd=td, check=True)
    forbidden = ['AGENTS.md', 'ARCHITECTURE.md', 'docs']
    for name in forbidden:
        assert not pathlib.Path(td, name).exists(), name
    subprocess.run([sys.executable, str(script), 'knowledge-index'], cwd=td, check=True)
    subprocess.run([sys.executable, str(script), 'knowledge-check'], cwd=td, check=True)
print('final memory-only validation ok')
PY
```
Expected: no grep output and final print.

- [ ] **Step 2: Confirm branch status**

Run:
```bash
git status --short -- moss-mem/SKILL.md moss-mem/scripts/memory_manager.py moss-mem/test-prompts.json
```
Expected: no output.

- [ ] **Step 3: Final report**

Report:
```text
- Commits created
- Paths moss-mem now owns
- Paths moss-mem no longer creates/requires
- Validation commands run
- Installed skill directory still not synced unless separately requested
```
Expected: user can decide whether to sync installed skill.

## Self-Review

- Spec coverage: Covers user constraints: root `MEMORY.md` only exception; `.moss-mem/**` for moss-mem managed files; `AGENTS.md` read-only optional; broad project docs removed from core.
- Placeholder scan: No TBD/TODO placeholders remain. All commands and code snippets are concrete.
- Type consistency: Uses existing constants `MEMORY_FILE`, `MOSS_DIR`, `TASKS_DIR`, `SUMMARIES_DIR`, `INDEX_CACHE_DIR`, and `ARCHIVE_FILE` consistently.

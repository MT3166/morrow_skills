# moss-mem Dependency-Free Local Index Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the MemPalace mechanism from `moss-mem` and replace its retrieval role with a dependency-free, ranked local index and search command.

**Architecture:** Markdown files remain the only source of truth. `knowledge-index` parses `MEMORY.md`, task files including archives, and session summaries into an atomic JSON search cache plus a human-readable Markdown catalog; `memory-search` ranks local records and falls back to direct source scanning when the cache cannot be rebuilt.

**Tech Stack:** Python 3 standard library (`argparse`, `collections`, `json`, `pathlib`, `re`, `shutil`, `tempfile`, `unittest`), Markdown, JSON, Git, Darwin SkillLens evaluation.

## Global Constraints

- No MemPalace, MCP, vector database, SQLite extension, external service, or third-party Python package.
- The source of truth remains `MEMORY.md`, `.moss-mem/tasks/**/*.md`, and `.moss-mem/summaries/**/*.md`.
- `.moss-mem/index-cache/` is generated and may be deleted and rebuilt.
- Use UTF-8 and atomic temporary-file replacement for generated indexes.
- Tokenization must support lowercase ASCII words plus CJK unigrams and adjacent bigrams.
- Ranking weights are fixed: title/topic 8; Description/Summary 5; Decisions/Key Decisions/Landmines 5; Related Files/Next Step 3; remaining sections 1; exact phrase bonus 10.
- Search order is score descending, source `mtime_ns` descending, path ascending.
- Use TDD: watch every new test fail for the expected reason before production edits.
- Do not install dependencies or modify unrelated dirty-worktree files.
- Do not exceed 150% of the original `SKILL.md` size.

---

## File Map

- Create: `moss-mem/tests/test_memory_manager.py` — command-level and unit-level standard-library regression tests.
- Modify: `moss-mem/scripts/memory_manager.py` — lock repair, structured index generation, ranked search, validation, and local-only prompts.
- Replace: `moss-mem/test-prompts.json` — the three user-approved Darwin evaluation prompts.
- Rewrite: `moss-mem/SKILL.md` — local-file architecture, index/search workflow, failure branches, checkpoints, and blacklist.
- Delete: `moss-mem/references/mempalace-tools.md` — retired integration reference.
- Replace: `moss-mem/result-card.html` and `moss-mem/result-card.png` — final Darwin evaluation card.
- Delete: `moss-mem/result-card-round2.png` — obsolete result artifact recoverable from Git history.
- Local evaluation log, not committed: `.claude/skills/darwin-skill/results.tsv`.

### Task 1: Freeze The Darwin Evaluation Set And Record Baseline

**Files:**
- Replace: `moss-mem/test-prompts.json`
- Local only: `.claude/skills/darwin-skill/results.tsv`

**Interfaces:**
- Consumes: approved design at `docs/superpowers/specs/2026-07-20-moss-mem-local-index-design.md`.
- Produces: exactly three prompts used unchanged for baseline and post-change evaluation.

- [ ] **Step 1: Replace the prompt fixture with the approved cases**

Use `apply_patch` so `moss-mem/test-prompts.json` is exactly:

```json
[
  {
    "id": 1,
    "prompt": "项目环境只有 Python 标准库。初始化记忆、创建任务和 session summary 后，生成本地索引。",
    "expected": "生成 .moss-mem/index-cache/memory-index.json 和 memory-index.md；两者包含任务与 summary，过程不安装或调用外部记忆服务。",
    "type": "local_index_generation"
  },
  {
    "id": 2,
    "prompt": "搜索 token refresh race；它只存在于归档任务的 Key Decisions 中。",
    "expected": "memory-search 返回该归档任务且排名第一，输出 score、kind、path、title 和命中摘要。",
    "type": "ranked_archive_search"
  },
  {
    "id": 3,
    "prompt": "JSON 索引损坏后搜索 httpOnly cookie。",
    "expected": "memory-search 自动重建一次；若重建失败则直接扫描 Markdown 并标记 [INDEX-FALLBACK]，交接功能不受阻。",
    "type": "corrupt_index_recovery"
  }
]
```

- [ ] **Step 2: Validate the fixture**

Run: `python3 -m json.tool moss-mem/test-prompts.json`

Expected: formatted JSON containing IDs `1`, `2`, and `3`; exit code `0`.

- [ ] **Step 3: Run the baseline effect evaluation**

Dispatch six fresh agents in parallel with `fork_turns="none"`: one `with_skill` and one `baseline` agent for each prompt. Give `with_skill` agents the current `moss-mem/SKILL.md`; do not give it to baseline agents. Require each to return the commands it would run, expected files/output, and any external dependency assumptions.

Expected current failures:

- Prompt 1 produces only a path-list Markdown index and recommends external synchronization.
- Prompt 2 selects an external search CLI rather than a local ranked command.
- Prompt 3 has no JSON cache recovery path or `memory-search` command.

- [ ] **Step 4: Record the baseline score**

Ensure `.claude/skills/darwin-skill/results.tsv` has this header:

```tsv
timestamp	commit	skill	old_score	new_score	status	dimension	note	eval_mode
```

Append one `baseline` row using the independent judge's computed 9-dimension score, current commit `53edb31`, skill `moss-mem`, note `three approved local-index prompts; runtime neutrality scan recorded separately`, and `eval_mode=full_test`.

- [ ] **Step 5: Commit the frozen prompt set**

```bash
git add moss-mem/test-prompts.json
git commit -m "test(moss-mem): focus evaluation on local index"
```

### Task 2: Restore Cross-Platform Lock Acquisition

**Files:**
- Create: `moss-mem/tests/test_memory_manager.py`
- Modify: `moss-mem/scripts/memory_manager.py:146-160`

**Interfaces:**
- Consumes: existing CLI `state set key=value`.
- Produces: `run_cli(*args: str) -> subprocess.CompletedProcess[str]` test helper and working `acquire_lock() -> bool`.

- [ ] **Step 1: Write the failing command-level test**

Create `moss-mem/tests/test_memory_manager.py` with:

```python
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "memory_manager.py"


class MemoryManagerCLITest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.project = Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=self.project,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_state_set_acquires_lock_and_updates_memory(self):
        result = self.run_cli(
            "state",
            "set",
            "current_task=repair login",
            "next_step=inspect auth.py",
            "status=🔧",
        )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        memory = (self.project / "MEMORY.md").read_text(encoding="utf-8")
        self.assertIn("repair login", memory)
        self.assertIn("inspect auth.py", memory)
        self.assertFalse((self.project / ".moss-mem/tasks/.edit_lock").exists())
```

- [ ] **Step 2: Run the test and verify RED**

Run: `python3 -m unittest moss-mem/tests/test_memory_manager.py -v`

Expected: FAIL because output contains `module 'os' has no attribute '_open'` and return code is non-zero.

- [ ] **Step 3: Apply the one-line production fix**

In `acquire_lock`, replace:

```python
fd = os._open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
```

with:

```python
fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
```

- [ ] **Step 4: Verify GREEN**

Run: `python3 -m unittest moss-mem/tests/test_memory_manager.py -v`

Expected: `test_state_set_acquires_lock_and_updates_memory ... ok`.

- [ ] **Step 5: Commit**

```bash
git add moss-mem/tests/test_memory_manager.py moss-mem/scripts/memory_manager.py
git commit -m "fix(moss-mem): restore atomic lock creation"
```

### Task 3: Build Structured JSON And Markdown Indexes

**Files:**
- Modify: `moss-mem/tests/test_memory_manager.py`
- Modify: `moss-mem/scripts/memory_manager.py:7-17,108-114,605-632`

**Interfaces:**
- Produces: `_discover_memory_sources() -> list[Path]`, `_parse_memory_record(path: Path, record_id: int) -> dict`, `_tokenize(text: str) -> list[str]`, `_current_source_metadata() -> dict[str, int]`, `_build_index_payload() -> tuple[dict, list[str]]`, `_write_index_files(payload: dict, warnings: list[str]) -> None`, `cmd_knowledge_index() -> bool`.
- Generated files: `.moss-mem/index-cache/memory-index.json` and `.moss-mem/index-cache/memory-index.md`.

- [ ] **Step 1: Add a failing index-generation test**

Add this method to `MemoryManagerCLITest`:

```python
    def test_knowledge_index_contains_memory_tasks_archives_and_summaries(self):
        (self.project / ".moss-mem/tasks/archive/2026").mkdir(parents=True)
        (self.project / ".moss-mem/summaries").mkdir(parents=True)
        (self.project / "MEMORY.md").write_text(
            "# MEMORY.md\n\n## 下一步指令 [Strict]\n- run tests\n",
            encoding="utf-8",
        )
        (self.project / ".moss-mem/tasks/20260720-100000_task.md").write_text(
            "# Task - Login\n\n## Description\nRepair login\n",
            encoding="utf-8",
        )
        (self.project / ".moss-mem/tasks/archive/2026/20260719_task.md").write_text(
            "# Compacted Login Task\n\n## Key Decisions\ntoken refresh race\n",
            encoding="utf-8",
        )
        (self.project / ".moss-mem/summaries/20260720-auth.md").write_text(
            "---\ntopic: auth summary\ncreated: 2026-07-20 10:00\n---\n\n# Harness Summary\n\n## Summary\nUse httpOnly cookie\n",
            encoding="utf-8",
        )

        result = self.run_cli("knowledge-index")

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        json_path = self.project / ".moss-mem/index-cache/memory-index.json"
        md_path = self.project / ".moss-mem/index-cache/memory-index.md"
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(len(payload["records"]), 4)
        self.assertEqual(
            {record["kind"] for record in payload["records"]},
            {"memory", "task", "archived-task", "summary"},
        )
        self.assertIn("token refresh race", json_path.read_text(encoding="utf-8"))
        self.assertIn("auth summary", md_path.read_text(encoding="utf-8"))
```

- [ ] **Step 2: Run the test and verify RED**

Run: `python3 -m unittest moss-mem/tests/test_memory_manager.py -v`

Expected: FAIL because `memory-index.json` does not exist.

- [ ] **Step 3: Add index constants and parsing helpers**

Add `import re` and `from collections import defaultdict` near the imports. Add these constants below `OLD_TASKS_DIR`:

```python
INDEX_SCHEMA_VERSION = 1
INDEX_JSON_FILE = "memory-index.json"
INDEX_MD_FILE = "memory-index.md"
```

Implement the interfaces with these exact rules:

```python
def _discover_memory_sources():
    paths = []
    memory = Path(MEMORY_FILE)
    if memory.is_file():
        paths.append(memory)
    for root in (Path(TASKS_DIR), Path(SUMMARIES_DIR)):
        if root.exists():
            paths.extend(path for path in root.rglob("*.md") if path.is_file())
    return sorted(set(paths), key=lambda path: str(path))


def _tokenize(text):
    normalized = text.lower()
    terms = re.findall(r"[a-z0-9_]+", normalized)
    for chunk in re.findall(r"[\u3400-\u9fff]+", normalized):
        terms.extend(chunk)
        terms.extend(chunk[index:index + 2] for index in range(len(chunk) - 1))
    return terms


def _classify_source(path):
    if path == Path(MEMORY_FILE):
        return "memory"
    if Path(SUMMARIES_DIR) in path.parents:
        return "summary"
    if "archive" in path.parts:
        return "archived-task"
    if path.name == ARCHIVE_FILE:
        return "archive-index"
    return "task"
```

Add the remaining helpers with these implementations:

```python
def _parse_memory_record(path, record_id):
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    frontmatter = {}
    body_start = 0
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                body_start = index + 1
                break
            if ":" in lines[index]:
                key, value = lines[index].split(":", 1)
                frontmatter[key.strip()] = value.strip().strip('"')

    title = path.stem
    sections = {}
    current = None
    buffer = []
    for line in lines[body_start:]:
        if line.startswith("# ") and title == path.stem:
            title = line[2:].strip()
        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(buffer).strip()
            current = line[3:].strip()
            buffer = []
        elif current is not None:
            buffer.append(line)
    if current is not None:
        sections[current] = "\n".join(buffer).strip()

    created = frontmatter.get("created", "")
    if not created and sections.get("Created"):
        created = sections["Created"].splitlines()[0].strip()
    preview_source = next(
        (
            sections[name]
            for name in ("Description", "Summary", "Key Decisions", "Decisions", "Next Step")
            if sections.get(name)
        ),
        title,
    )
    preview = " ".join(preview_source.split())[:240]
    return {
        "id": record_id,
        "path": str(path),
        "kind": _classify_source(path),
        "title": frontmatter.get("topic") or frontmatter.get("description") or title,
        "created": created,
        "mtime_ns": path.stat().st_mtime_ns,
        "sections": sections,
        "preview": preview,
    }


def _current_source_metadata():
    return {str(path): path.stat().st_mtime_ns for path in _discover_memory_sources()}


def _build_index_payload():
    records = []
    warnings = []
    inverted = defaultdict(set)
    for path in _discover_memory_sources():
        try:
            record = _parse_memory_record(path, len(records))
        except (OSError, UnicodeError) as exc:
            warnings.append(f"skipped unreadable source {path}: {exc}")
            continue
        records.append(record)
        searchable = " ".join([record["title"], *record["sections"].values()])
        for term in _tokenize(searchable):
            inverted[term].add(record["id"])
    if not records:
        raise ValueError("no readable memory sources")
    payload = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sources": {record["path"]: record["mtime_ns"] for record in records},
        "records": records,
        "inverted_terms": {term: sorted(ids) for term, ids in sorted(inverted.items())},
    }
    return payload, warnings


def _render_index_markdown(payload, warnings):
    labels = [
        ("memory", "Memory"),
        ("task", "Tasks"),
        ("archived-task", "Archived Tasks"),
        ("archive-index", "Archive Indexes"),
        ("summary", "Summaries"),
    ]
    lines = [
        "# moss-mem Memory Index",
        "",
        f"Generated: {payload['generated_at']}",
        f"Records: {len(payload['records'])}",
    ]
    for kind, label in labels:
        lines.extend(["", f"## {label}"])
        matches = [record for record in payload["records"] if record["kind"] == kind]
        if not matches:
            lines.append("- <!-- none -->")
        for record in matches:
            created = f" | {record['created']}" if record["created"] else ""
            lines.append(f"- `{record['path']}` | {record['title']}{created}")
            lines.append(f"  - {record['preview']}")
    if warnings:
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {warning}" for warning in warnings)
    return "\n".join(lines) + "\n"


def _write_index_files(payload, warnings):
    Path(INDEX_CACHE_DIR).mkdir(parents=True, exist_ok=True)
    outputs = {
        Path(INDEX_CACHE_DIR) / INDEX_JSON_FILE: json.dumps(
            payload, ensure_ascii=False, indent=2, sort_keys=True
        ) + "\n",
        Path(INDEX_CACHE_DIR) / INDEX_MD_FILE: _render_index_markdown(payload, warnings),
    }
    previous = {path: path.read_bytes() if path.exists() else None for path in outputs}
    temp_paths = {}
    try:
        for path, text in outputs.items():
            temp = path.with_suffix(path.suffix + ".tmp")
            temp.write_text(text, encoding="utf-8")
            temp_paths[path] = temp
        for path, temp in temp_paths.items():
            os.replace(temp, path)
    except OSError:
        for path, content in previous.items():
            if content is None:
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
            else:
                restore = path.with_suffix(path.suffix + ".restore")
                restore.write_bytes(content)
                os.replace(restore, path)
        raise
    finally:
        for temp in temp_paths.values():
            try:
                temp.unlink()
            except FileNotFoundError:
                pass
```

- [ ] **Step 4: Replace `cmd_knowledge_index`**

Implement:

```python
def cmd_knowledge_index():
    """Regenerate dependency-free JSON and Markdown memory indexes."""
    try:
        payload, warnings = _build_index_payload()
        _write_index_files(payload, warnings)
    except (OSError, ValueError) as exc:
        safe_print(f"❌ Memory index failed: {exc}")
        return False
    safe_print(f"✅ Memory index written: {len(payload['records'])} record(s)")
    for warning in warnings:
        safe_print(f"⚠️  {warning}")
    return True
```

Update the `knowledge-index` dispatch so a `False` return exits with code `1`.

- [ ] **Step 5: Verify GREEN**

Run: `python3 -m unittest moss-mem/tests/test_memory_manager.py -v`

Expected: both tests pass and the temporary project contains both index files.

- [ ] **Step 6: Commit**

```bash
git add moss-mem/tests/test_memory_manager.py moss-mem/scripts/memory_manager.py
git commit -m "feat(moss-mem): generate structured local indexes"
```

### Task 4: Add Ranked Search, Automatic Rebuild, And Direct Fallback

**Files:**
- Modify: `moss-mem/tests/test_memory_manager.py`
- Modify: `moss-mem/scripts/memory_manager.py:605-675,1270-1405`

**Interfaces:**
- Consumes: `_current_source_metadata()` and structured payloads from Task 3.
- Produces: `_load_index_payload() -> dict`, `_index_problem(payload: dict) -> str | None`, `_score_record(record: dict, query: str, terms: list[str]) -> int`, `_matching_excerpt(record: dict, query: str, terms: list[str]) -> str`, `_search_records(payload: dict, query: str, limit: int) -> list[dict]`, `cmd_memory_search(query: str, limit: int = 10) -> int`.
- CLI: `memory-search QUERY [--limit N]`.

- [ ] **Step 1: Add failing ranked-search and corrupt-index tests**

First add this exact fixture helper to `MemoryManagerCLITest`, then add the two test methods:

```python
    def _write_index_fixture(self):
        (self.project / ".moss-mem/tasks/archive/2026").mkdir(parents=True)
        (self.project / ".moss-mem/summaries").mkdir(parents=True)
        (self.project / "MEMORY.md").write_text(
            "# MEMORY.md\n\n## 下一步指令 [Strict]\n- run tests\n",
            encoding="utf-8",
        )
        (self.project / ".moss-mem/tasks/20260720-100000_task.md").write_text(
            "# Task - Login\n\n## Description\nRepair login\n",
            encoding="utf-8",
        )
        (self.project / ".moss-mem/tasks/archive/2026/20260719_task.md").write_text(
            "# Compacted Login Task\n\n## Key Decisions\ntoken refresh race\n",
            encoding="utf-8",
        )
        (self.project / ".moss-mem/summaries/20260720-auth.md").write_text(
            "---\ntopic: auth summary\ncreated: 2026-07-20 10:00\n---\n\n"
            "# Harness Summary\n\n## Summary\nUse httpOnly cookie\n",
            encoding="utf-8",
        )
```

```python
    def test_memory_search_ranks_archived_key_decision_first(self):
        self._write_index_fixture()
        self.assertEqual(self.run_cli("knowledge-index").returncode, 0)

        result = self.run_cli("memory-search", "token refresh race", "--limit", "3")

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("kind=archived-task", result.stdout)
        self.assertIn("20260719_task.md", result.stdout)
        self.assertIn("token refresh race", result.stdout)
        self.assertLess(result.stdout.index("20260719_task.md"), result.stdout.find("[2] ") if "[2] " in result.stdout else len(result.stdout))

    def test_memory_search_rebuilds_corrupt_json_index(self):
        self._write_index_fixture()
        self.assertEqual(self.run_cli("knowledge-index").returncode, 0)
        json_path = self.project / ".moss-mem/index-cache/memory-index.json"
        json_path.write_text("{broken", encoding="utf-8")

        result = self.run_cli("memory-search", "httpOnly cookie")

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("Rebuilding local memory index", result.stdout)
        self.assertIn("20260720-auth.md", result.stdout)
        self.assertTrue(list(json_path.parent.glob("memory-index.json.bak.*")))
        json.loads(json_path.read_text(encoding="utf-8"))
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python3 -m unittest moss-mem/tests/test_memory_manager.py -v`

Expected: both new tests fail because `memory-search` is not a recognized command.

- [ ] **Step 3: Implement index status and ranking**

Add these implementations:

```python
FIELD_WEIGHTS = {
    "title": 8,
    "Description": 5,
    "Summary": 5,
    "Decisions": 5,
    "Key Decisions": 5,
    "Landmines": 5,
    "Related Files": 3,
    "Next Step": 3,
}


def _load_index_payload():
    path = Path(INDEX_CACHE_DIR) / INDEX_JSON_FILE
    with _open(path) as handle:
        return json.load(handle)


def _index_problem(payload):
    if payload.get("schema_version") != INDEX_SCHEMA_VERSION:
        return "schema mismatch"
    current = _current_source_metadata()
    indexed = payload.get("sources", {})
    if set(current) != set(indexed):
        return "source set changed"
    if any(current[path] != indexed[path] for path in current):
        return "source modified"
    return None


def _record_weighted_fields(record):
    fields = [(record["title"], FIELD_WEIGHTS["title"])]
    for name, value in record["sections"].items():
        fields.append((value, FIELD_WEIGHTS.get(name, 1)))
    return fields


def _score_record(record, query, terms):
    normalized_query = " ".join(query.lower().split())
    score = 0
    for value, weight in _record_weighted_fields(record):
        normalized_value = " ".join(value.lower().split())
        value_terms = _tokenize(normalized_value)
        score += sum(value_terms.count(term) * weight for term in terms)
        if normalized_query and normalized_query in normalized_value:
            score += 10
    return score


def _matching_excerpt(record, query, terms):
    normalized_query = " ".join(query.lower().split())
    ranked_fields = sorted(_record_weighted_fields(record), key=lambda item: -item[1])
    for value, _weight in ranked_fields:
        flat = " ".join(value.split())
        lowered = flat.lower()
        if normalized_query in lowered or any(term in _tokenize(lowered) for term in terms):
            return flat[:240]
    return record["preview"][:240]


def _search_records(payload, query, limit):
    if limit < 1:
        raise ValueError("limit must be >= 1")
    terms = list(dict.fromkeys(_tokenize(query)))
    candidate_ids = set()
    for term in terms:
        candidate_ids.update(payload.get("inverted_terms", {}).get(term, []))
    records_by_id = {record["id"]: record for record in payload["records"]}
    candidates = [records_by_id[record_id] for record_id in candidate_ids if record_id in records_by_id]
    results = []
    for record in candidates:
        score = _score_record(record, query, terms)
        if score > 0:
            results.append({
                "score": score,
                "record": record,
                "excerpt": _matching_excerpt(record, query, terms),
            })
    results.sort(
        key=lambda item: (
            -item["score"],
            -item["record"]["mtime_ns"],
            item["record"]["path"],
        )
    )
    return results[:limit]
```

- [ ] **Step 4: Implement recovery and fallback**

Implement:

```python
def _backup_corrupt_index():
    path = Path(INDEX_CACHE_DIR) / INDEX_JSON_FILE
    if not path.exists():
        return None
    backup = path.with_name(f"{path.name}.bak.{get_timestamp()}")
    os.replace(path, backup)
    return backup


def cmd_memory_search(query, limit=10):
    query = query.strip()
    if not query:
        safe_print("❌ search query must not be empty")
        return 1
    if limit < 1:
        safe_print("❌ limit must be >= 1")
        return 1

    payload = None
    reason = None
    try:
        payload = _load_index_payload()
        reason = _index_problem(payload)
    except FileNotFoundError:
        reason = "missing index"
    except json.JSONDecodeError:
        _backup_corrupt_index()
        reason = "corrupt index"
    except OSError:
        reason = "unreadable index"

    if reason:
        safe_print(f"Rebuilding local memory index: {reason}")
        if cmd_knowledge_index():
            try:
                payload = _load_index_payload()
            except (OSError, json.JSONDecodeError):
                payload = None
        else:
            payload = None

    if payload is None:
        safe_print("[INDEX-FALLBACK] scanning Markdown sources directly")
        try:
            payload, warnings = _build_index_payload()
        except (OSError, ValueError) as exc:
            safe_print(f"❌ Memory search failed: {exc}")
            return 1
        for warning in warnings:
            safe_print(f"⚠️  {warning}")

    results = _search_records(payload, query, limit)
    if not results:
        safe_print(f"[NO_MATCH] query={query} sources={len(payload['records'])}")
        return 0
    for index, result in enumerate(results, start=1):
        record = result["record"]
        safe_print(
            f"[{index}] score={result['score']} kind={record['kind']} path={record['path']}"
        )
        safe_print(f"    title={record['title']}")
        safe_print(f"    excerpt={result['excerpt']}")
    return 0
```

- [ ] **Step 5: Register the CLI**

Add:

```python
memory_search_parser = subparsers.add_parser("memory-search", help="Search the local generated memory index")
memory_search_parser.add_argument("query", help="Words or phrase to search")
memory_search_parser.add_argument("--limit", type=int, default=10, help="Maximum results; default 10")
```

Dispatch with:

```python
elif args.command == "memory-search":
    sys.exit(cmd_memory_search(args.query, args.limit))
```

- [ ] **Step 6: Add the direct-fallback unit test**

Add `import io` to the test imports and add:

```python
    def test_memory_search_direct_scans_when_rebuild_fails(self):
        self._write_index_fixture()
        spec = importlib.util.spec_from_file_location("memory_manager_under_test", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        previous = Path.cwd()
        output = io.StringIO()
        try:
            os.chdir(self.project)
            with mock.patch.object(module, "cmd_knowledge_index", return_value=False):
                with mock.patch("sys.stdout", output):
                    exit_code = module.cmd_memory_search("httpOnly cookie")
        finally:
            os.chdir(previous)

        self.assertEqual(exit_code, 0)
        self.assertIn("[INDEX-FALLBACK]", output.getvalue())
        self.assertIn("20260720-auth.md", output.getvalue())
```

- [ ] **Step 7: Verify GREEN**

Run: `python3 -m unittest moss-mem/tests/test_memory_manager.py -v`

Expected: lock, generation, ranking, corrupt rebuild, and direct fallback tests all pass.

- [ ] **Step 8: Commit**

```bash
git add moss-mem/tests/test_memory_manager.py moss-mem/scripts/memory_manager.py
git commit -m "feat(moss-mem): add ranked local memory search"
```

### Task 5: Strengthen Validation And Remove Runtime Integration Hints

**Files:**
- Modify: `moss-mem/tests/test_memory_manager.py`
- Modify: `moss-mem/scripts/memory_manager.py:426-448,634-674,696-743,1125-1133`

**Interfaces:**
- Consumes: `_load_index_payload()` and `_index_problem()` from Task 4.
- Produces: strict validation of both generated index files; local re-index guidance after summary capture and compaction.

- [ ] **Step 1: Add failing integration tests**

Add tests that assert:

```python
    def test_knowledge_check_strict_fails_when_index_is_stale(self):
        self._write_index_fixture()
        self.assertEqual(self.run_cli("knowledge-index").returncode, 0)
        task = self.project / ".moss-mem/tasks/20260720-100000_task.md"
        task.write_text(task.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")
        result = self.run_cli("knowledge-check", "--strict")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("memory index is stale", result.stdout)

    def test_summary_capture_recommends_local_reindex_only(self):
        result = self.run_cli(
            "summary-capture", "-t", "auth", "-s", "cookie decision",
            "--decisions", "httpOnly cookie", "-n", "run tests",
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("knowledge-index", result.stdout)
        removed_name = "mem" + "palace"
        self.assertNotIn(removed_name, result.stdout.lower())
        summary = next((self.project / ".moss-mem/summaries").glob("*.md"))
        self.assertNotIn(removed_name, summary.read_text(encoding="utf-8").lower())
```

Also add:

```python
    def test_compaction_recommends_local_reindex_only(self):
        tasks = self.project / ".moss-mem/tasks"
        tasks.mkdir(parents=True)
        for index in range(3):
            (tasks / f"20260720-10000{index}_task.md").write_text(
                f"# Task {index}\n\n## Description\nTask {index}\n",
                encoding="utf-8",
            )

        result = self.run_cli(
            "state", "compact", "--keep-recent", "1", "--yes"
        )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("knowledge-index", result.stdout)
        removed_name = "mem" + "palace"
        self.assertNotIn(removed_name, result.stdout.lower())
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python3 -m unittest moss-mem/tests/test_memory_manager.py -v`

Expected: stale validation or local-only message tests fail against current behavior.

- [ ] **Step 3: Update validation**

After the existing layout loop, replace the current single-index freshness block with:

```python
    json_index = Path(INDEX_CACHE_DIR) / INDEX_JSON_FILE
    markdown_index = Path(INDEX_CACHE_DIR) / INDEX_MD_FILE
    if not json_index.is_file():
        warnings.append(f"missing index: {json_index}")
    if not markdown_index.is_file():
        warnings.append(f"missing index: {markdown_index}")
    if json_index.is_file():
        try:
            payload = _load_index_payload()
            problem = _index_problem(payload)
            if problem:
                warnings.append(f"memory index is stale: {problem}")
            else:
                safe_print("✅ memory index is fresh")
        except json.JSONDecodeError:
            warnings.append(f"memory index is corrupt: {json_index}")
        except OSError as exc:
            warnings.append(f"memory index is unreadable: {exc}")
```

Preserve the existing warning/error printing and `if strict and warnings: sys.exit(1)` behavior.

- [ ] **Step 4: Replace integration hints**

Apply these exact replacements:

```python
# check_compact_threshold docstring body
notices growth before it starts hurting local index/search latency.

# cmd_summary_capture content tail
        "## Related Files",
        *related_lines,
        "",
    ])
    summary_path.write_text(content, encoding="utf-8")
    safe_print(f"✅ Harness summary captured: {summary_path}")
    safe_print("🔎 Next: run knowledge-index before handoff.")

# cmd_compact success tail
    if not dry_run:
        safe_print(f"   Archive location: {archive_dir}")
        safe_print("   Next: run knowledge-index to refresh local search")
    return 0
```

- [ ] **Step 5: Verify GREEN**

Run: `python3 -m unittest moss-mem/tests/test_memory_manager.py -v`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add moss-mem/tests/test_memory_manager.py moss-mem/scripts/memory_manager.py
git commit -m "fix(moss-mem): validate and refresh local indexes"
```

### Task 6: Rewrite The Skill Contract And Remove Retired References

**Files:**
- Rewrite: `moss-mem/SKILL.md`
- Delete: `moss-mem/references/mempalace-tools.md`

**Interfaces:**
- Consumes: commands implemented in Tasks 2-5.
- Produces: runtime-neutral documentation for `state`, `knowledge-index`, `memory-search`, `knowledge-check`, summaries, compaction, and handoff.

- [ ] **Step 1: Run the runtime-content RED scan**

Run:

```bash
rg -n -i 'mempalace|mempalace-mcp|mempalace_|--wing|pip install mempalace' moss-mem/SKILL.md moss-mem/scripts/memory_manager.py moss-mem/test-prompts.json moss-mem/references
```

Expected: multiple matches in `SKILL.md` and `references/mempalace-tools.md`.

- [ ] **Step 2: Rewrite `SKILL.md` around the local-only contract**

Keep the file under 460 lines. Use this exact top-level structure and content requirements:

```markdown
---
name: moss-mem
description: Use when project work must persist across agent sessions, including starting or updating tasks, recovering context, searching prior work, capturing summaries, compacting history, validating handoffs, or completing a task.
version: "5.0.0"
---

# moss-mem — Project memory across sessions

## Overview

`MEMORY.md` and `.moss-mem/` are the source of truth. Generated files under
`.moss-mem/index-cache/` accelerate local retrieval and can always be rebuilt.
The skill uses Python's standard library only.

## Quick Dispatch

| Intent | Command |
|---|---|
| Show current task | `python3 {base}/scripts/memory_manager.py state show` |
| Set state | `python3 {base}/scripts/memory_manager.py state set current_task="repair login" next_step="inspect auth.py" status="🔧"` |
| Commit snapshot | `python3 {base}/scripts/memory_manager.py state commit -m "auth handoff"` |
| Add note | `python3 {base}/scripts/memory_manager.py state note "found refresh race"` |
| Build index | `python3 {base}/scripts/memory_manager.py knowledge-index` |
| Search memory | `python3 {base}/scripts/memory_manager.py memory-search "refresh race" --limit 10` |
| Validate | `python3 {base}/scripts/memory_manager.py knowledge-check --strict` |
| Compact | `python3 {base}/scripts/memory_manager.py state compact --dry-run` |

## Storage And Ownership
## Local Index And Search
## State Operations
## Summary Capture
## Compaction
## Handoff Protocol
## If-Then Fallbacks
## Anti-Patterns / Blacklist
## File Formats
## First-Time Setup
## Platform Notes
```

The completed sections must preserve the current state schema, P9 trap, four-step handoff gates, compaction confirmation checkpoint, ownership boundary, and platform commands. Replace all search guidance with `memory-search`; describe missing/corrupt/stale index rebuild and `[INDEX-FALLBACK]`; forbid hand-editing generated indexes and treating index caches as source data. Do not mention or imply the retired integration.

- [ ] **Step 3: Delete the retired reference**

Impact: `moss-mem/references/mempalace-tools.md` is removed from the working tree; it remains recoverable from Git history.

Run: `git rm moss-mem/references/mempalace-tools.md`

- [ ] **Step 4: Run content and runtime-neutrality scans**

Run:

```bash
rg -n -i 'mempalace|mempalace-mcp|mempalace_|--wing|pip install mempalace' moss-mem/SKILL.md moss-mem/scripts/memory_manager.py moss-mem/test-prompts.json moss-mem/references
```

Expected: no output.

Run:

```bash
grep -nE '(在 Claude Code|Claude Code skill|Claude Code 用户|Cursor only|Codex 中|^\[!\[Claude Code|~/\.claude/skills/[a-z]|/plugin install\b)' moss-mem/SKILL.md 2>/dev/null
```

Expected: no output.

- [ ] **Step 5: Run regression tests**

Run: `python3 -m unittest discover -s moss-mem/tests -v`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add moss-mem/SKILL.md moss-mem/scripts/memory_manager.py moss-mem/test-prompts.json moss-mem/tests/test_memory_manager.py
git add -u moss-mem/references/mempalace-tools.md
git commit -m "docs(moss-mem): make local index the retrieval contract"
```

### Task 7: Full Verification, Independent Re-Evaluation, And Result Card

**Files:**
- Replace: `moss-mem/result-card.html`
- Replace: `moss-mem/result-card.png`
- Delete: `moss-mem/result-card-round2.png`
- Local only: `.claude/skills/darwin-skill/results.tsv`

**Interfaces:**
- Consumes: all implementation commits and the unchanged three-prompt evaluation set.
- Produces: verified before/after Darwin score and one current result card.

- [ ] **Step 1: Run complete verification**

```bash
python3 -m unittest discover -s moss-mem/tests -v
python3 -m json.tool moss-mem/test-prompts.json
python3 moss-mem/scripts/memory_manager.py --help
git diff --check 53edb31..HEAD
```

Expected: tests pass, JSON validates, help lists `memory-search`, and `git diff --check` is silent.

- [ ] **Step 2: Run isolated smoke flow in a temporary directory**

Run these commands one at a time:

```bash
MOSS_SMOKE_DIR=$(mktemp -d)
cd "$MOSS_SMOKE_DIR"
python3 /Users/mt/00XMT/99_Codebase/personal/morrow_skills/moss-mem/scripts/memory_manager.py state init
python3 /Users/mt/00XMT/99_Codebase/personal/morrow_skills/moss-mem/scripts/memory_manager.py state set current_task="auth handoff" next_step="run integration tests" status="🔧"
python3 /Users/mt/00XMT/99_Codebase/personal/morrow_skills/moss-mem/scripts/memory_manager.py state commit -m "auth handoff snapshot"
python3 /Users/mt/00XMT/99_Codebase/personal/morrow_skills/moss-mem/scripts/memory_manager.py summary-capture -t "auth summary" -s "completed auth handoff" --decisions "use httpOnly cookie" -n "run integration tests"
python3 /Users/mt/00XMT/99_Codebase/personal/morrow_skills/moss-mem/scripts/memory_manager.py knowledge-index
python3 /Users/mt/00XMT/99_Codebase/personal/morrow_skills/moss-mem/scripts/memory_manager.py memory-search "auth handoff"
python3 /Users/mt/00XMT/99_Codebase/personal/morrow_skills/moss-mem/scripts/memory_manager.py knowledge-check --strict
```

Expected: every command exits `0`; search returns the task or summary; no external command is installed or invoked.

- [ ] **Step 3: Re-run the six effect agents and two independent judges**

Use the same prompt text and pairing as Task 1. Judges receive anonymous baseline/post-change outputs, the 9-dimension rubric, and no information about which output is newer. Require both judges to provide per-dimension scores and cite concrete behavior differences.

Keep the implementation only when the rounded one-decimal total is strictly greater than the baseline and both judges agree the post-change outputs are better. Otherwise run `git revert` on the most recent optimization commit; never use `git reset --hard`.

- [ ] **Step 4: Append the Darwin result row**

Append a `keep` row to `.claude/skills/darwin-skill/results.tsv` with the verified old/new totals, current commit, improved dimension, note `dependency-free structured index + ranked search`, and `eval_mode=full_test`.

- [ ] **Step 5: Replace obsolete result artifacts**

Impact: `moss-mem/result-card-round2.png` and the old card files are removed from the current tree; all remain recoverable from Git history. Announce this impact before running:

```bash
git rm moss-mem/result-card-round2.png moss-mem/result-card.html moss-mem/result-card.png
```

Copy `/Users/mt/.agents/skills/darwin-skill/templates/result-card.html` to `moss-mem/result-card.html`, then use `apply_patch` to fill the exact baseline/post-change totals, nine dimension bars, three improvement summaries, and date `2026-07-20` from the recorded judge results.

Generate the PNG:

```bash
node /Users/mt/.agents/skills/darwin-skill/scripts/screenshot.mjs /Users/mt/00XMT/99_Codebase/personal/morrow_skills/moss-mem/result-card.html /Users/mt/00XMT/99_Codebase/personal/morrow_skills/moss-mem/result-card.png
```

Expected: script exits `0` and `moss-mem/result-card.png` is non-empty.

- [ ] **Step 6: Commit evaluation artifacts**

```bash
git add moss-mem/result-card.html moss-mem/result-card.png
git add -u moss-mem/result-card-round2.png
git commit -m "chore(moss-mem): publish local-index evaluation card"
```

### Task 8: Final Review And MEMORY Handoff

**Files:**
- Write through moss-mem only: `MEMORY.md`, `.moss-mem/tasks/**`

**Interfaces:**
- Consumes: verified implementation and Darwin score.
- Produces: precise cross-session handoff without touching unrelated worktree changes.

- [ ] **Step 1: Invoke verification-before-completion**

Re-run its required evidence checks. Do not claim completion from earlier output.

- [ ] **Step 2: Review the scoped Git delta**

```bash
git status --short
git diff --stat 53edb31..HEAD -- moss-mem docs/superpowers
git log --oneline 53edb31..HEAD
```

Expected: only planned `moss-mem` and plan/spec artifacts are in the scoped delta; unrelated pre-existing files remain untouched.

- [ ] **Step 3: Write the handoff fields**

Run:

```bash
python3 moss-mem/scripts/memory_manager.py state commit -m "moss-mem local index implementation complete"
python3 moss-mem/scripts/memory_manager.py state set status="✅" last_action="Removed the external memory mechanism; added atomic JSON/Markdown indexes, ranked memory-search, recovery, tests, and docs" key_decisions="Markdown remains source of truth; generated local indexes use Python stdlib only; corrupt or stale caches rebuild once then direct-scan fallback" landmines="Generated index files must not be hand-edited; preserve explicit confirmation before compaction; unrelated dirty-worktree files were not modified" next_step="Review branch auto-optimize/20260720-1922 and choose merge or PR integration"
python3 moss-mem/scripts/memory_manager.py state show
```

Expected: status is `✅`; the three handoff fields are populated; next step names the branch.

- [ ] **Step 4: Report completion evidence**

Report test count, exact verification commands, before/after Darwin scores, result-card path, commits created, and any residual risk. End with `📝 MEMORY 已更新`.

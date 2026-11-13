# moss-mem P3 Relation and Time Views Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic read-only lineage and valid-time views over the P1/P2 index without changing Markdown sources, write protocols, or search ranking.

**Architecture:** Extend the existing `memory_manager.py` with shared validity and BFS lineage helpers, then add `memory-explain` and `memory-timeline` CLI commands. Both commands load/rebuild the complete Schema 3 index once, keep JSON stdout parseable, and render text from the same normalized result objects.

**Tech Stack:** Python 3.9+ standard library (`argparse`, `datetime`, `json`, `unittest`); existing Markdown source and Schema 3 index cache.

**Spec:** [docs/superpowers/specs/2026-11-13-moss-mem-p3-relation-time-views-design.md](/Users/mt/00XMT/99_Codebase/personal/morrow_skills/docs/superpowers/specs/2026-11-13-moss-mem-p3-relation-time-views-design.md)

## Global Constraints

- Read-only commands never modify Markdown, index payloads, locks, or manifests.
- stdout for `--json` contains exactly one JSON value; diagnostics go to stderr.
- `--depth` is integer `0..64`, default 3; `--limit` is integer `>=1`, default 10.
- Time comparisons normalize timezone-bearing ISO-8601 values to UTC and use half-open intervals.
- Legacy virtual IDs are queryable and case-sensitive; unknown IDs return structured errors.
- Supersession is explicit; default timeline hides records with direct `superseded_by`, while `--include-superseded` restores them.
- No third-party package, network service, event ledger, or source migration.

## Review Focus

- JSON mode must remain parseable when index rebuilds or errors happen; test stdout/stderr separation in Task 3.
- BFS depth and relation direction must be stable with multiple superseders and shared ancestors; test depth 0/1/3 in Task 1.
- Open intervals and exact half-open boundaries must classify correctly across timezones; test the truth table in Task 2.
- Timeline interval intersection must reject reversed/empty ranges and handle unknown intervals explicitly; test in Task 2.
- Legacy IDs, duplicate records, stale indexes, and source-byte preservation must remain compatible; test recovery in Task 3.

## File Map

- Modify: `moss-mem/scripts/memory_manager.py` — validity/lineage helpers, index loading wrapper, explain/timeline commands, CLI renderers.
- Modify: `moss-mem/tests/test_memory_manager.py` — relation, time, CLI, JSON, recovery, and compatibility tests.
- Modify: `moss-mem/SKILL.md` — document P3 commands, JSON shapes, time semantics, and error behavior.
- Modify: `MEMORY.md` / `.moss-mem/` only through moss-mem handoff commands.

### Task 1: Validity and lineage helpers

**Files:**
- Modify: `moss-mem/scripts/memory_manager.py` near P1 relation/search helpers.
- Modify: `moss-mem/tests/test_memory_manager.py`.

**Interfaces:**
- Produce `_classify_validity(metadata: dict, as_of: str | None) -> str` with `active/upcoming/expired/unknown` truth table.
- Produce `_build_lineage_view(payload: dict, memory_id: str, depth: int = 3) -> dict` returning `direct`, `ancestors`, and `descendants` with `{memory_id, depth}` nodes.
- Produce `_lineage_bfs(neighbours, start: str, depth: int) -> list[dict]` with per-level sorted IDs and visited-set deduplication.

- [ ] **Step 1: Write failing helper tests**

  Cover active/upcoming/expired/unknown, exact valid_to boundary, timezone normalization, depth 0/1/3, multiple superseders, shared ancestors, and unknown IDs.

- [ ] **Step 2: Run focused tests and verify failure**

  Run: `python3 -m unittest moss-mem.tests.test_memory_manager.MemoryManagerCLITest.test_p3_validity_and_lineage_helpers`

  Expected: FAIL because the new helpers do not exist.

- [ ] **Step 3: Implement helpers**

  Normalize `as_of` through `_normalize_time`; use direct metadata `supersedes` for ancestors and payload `superseded_by` for descendants. Reject depth outside `0..64` with `MetadataValidationError`.

- [ ] **Step 4: Run focused and regression tests**

  Run: `python3 -m unittest discover -s moss-mem/tests -p 'test_memory_manager.py'`

  Expected: existing P0/P1/P2 suite plus helper tests pass.

### Task 2: Timeline filtering and stable view objects

**Files:**
- Modify: `moss-mem/scripts/memory_manager.py`.
- Modify: `moss-mem/tests/test_memory_manager.py`.

**Interfaces:**
- Produce `_filter_timeline_records(records: list[dict], source=None, as_of=None, valid_from=None, valid_to=None, include_superseded=False) -> list[dict]`.
- Produce `_timeline_record_view(record: dict, as_of: str | None, payload: dict) -> dict` with record fields, validity, metadata, and direct superseded-by IDs.
- Produce `_sort_timeline_records(records: list[dict]) -> list[dict]` using the exact missing-value-last UTC key.

- [ ] **Step 1: Write failing timeline tests**

  Cover source trim/case sensitivity, as-of active filtering, open intervals, from/to intersection, from==to and reversed ranges, default superseded hiding, include override, limit ordering, and empty results.

- [ ] **Step 2: Run focused tests and verify failure**

  Run: `python3 -m unittest moss-mem.tests.test_memory_manager.MemoryManagerCLITest.test_p3_timeline_filters`

  Expected: FAIL because timeline helpers do not exist.

- [ ] **Step 3: Implement filters and view objects**

  Apply metadata filters before stable sorting and limit; keep supersession filtering independent from valid-time filtering. Unknown intervals are retained only without any time filter.

- [ ] **Step 4: Run focused and regression tests**

  Run: `python3 -m unittest discover -s moss-mem/tests -p 'test_memory_manager.py'`

  Expected: all timeline and existing tests pass.

### Task 3: CLI commands, JSON protocol, and recovery

**Files:**
- Modify: `moss-mem/scripts/memory_manager.py` in index loading, argparse, dispatch, and output.
- Modify: `moss-mem/tests/test_memory_manager.py`.

**Interfaces:**
- Add `cmd_memory_explain(memory_id, depth=3, as_of=None, json_output=False) -> int`.
- Add `cmd_memory_timeline(source=None, as_of=None, valid_from=None, valid_to=None, include_superseded=False, limit=10, json_output=False) -> int`.
- Add CLI commands `memory-explain MEMORY_ID` and `memory-timeline` with documented flags.
- Implement `_load_complete_index_for_view() -> tuple[dict | None, str | None]` with one rebuild attempt and no Markdown fallback.

- [ ] **Step 1: Write failing CLI tests**

  Assert text/JSON parity, structured errors and exit codes, legacy ID lookup, depth/limit validation, help text, one-shot rebuild, stderr diagnostics, and unchanged source bytes.

- [ ] **Step 2: Run focused tests and verify failure**

  Run: `python3 -m unittest moss-mem.tests.test_memory_manager.MemoryManagerCLITest.test_p3_view_cli`

  Expected: FAIL because argparse rejects the commands and no JSON error protocol exists.

- [ ] **Step 3: Implement command wiring and renderers**

  Keep stdout JSON-only, send rebuild/error diagnostics to stderr, return 2 for unknown ID/invalid arguments and 1 for unavailable index. Reuse the same view objects for text and JSON.

- [ ] **Step 4: Run CLI and full regression tests**

  Run: `python3 -m unittest discover -s moss-mem/tests -v`

  Expected: all P0/P1/P2/P3 tests pass.

### Task 4: Documentation and handoff

**Files:**
- Modify: `moss-mem/SKILL.md`.
- Modify: `MEMORY.md` / `.moss-mem/` through moss-mem commands.

- [ ] **Step 1: Write documentation contract tests**

  Assert SKILL.md documents both commands, JSON shapes, depth/limit defaults, valid-time semantics, error codes, and no-fallback policy.

- [ ] **Step 2: Update documentation**

  Add concise examples and explain that P3 is read-only and does not alter supersession or source history.

- [ ] **Step 3: Run complete verification**

  Run `python3 -m unittest discover -s moss-mem/tests -v`, `python3 -m py_compile moss-mem/scripts/memory_manager.py moss-mem/tests/test_memory_manager.py`, `git diff --check`, `knowledge-index`, and `knowledge-check --strict`.

- [ ] **Step 4: Perform fresh read-only review and commit**

  Resolve Critical/Important findings with tests first. Stage only P3 design/plan, runtime, tests, and SKILL documentation. Commit as `feat(moss-mem): add relation and time views`.

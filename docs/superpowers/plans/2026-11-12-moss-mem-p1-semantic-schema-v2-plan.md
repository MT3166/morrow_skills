# moss-mem P1 Semantic Schema v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional, validated semantic metadata layer for moss-mem records while preserving legacy Markdown, local indexing, and current CLI behavior.

**Architecture:** Keep Markdown as the only source of truth. Parse a normalized metadata object from frontmatter (and compact digest markers), publish it into index records, and apply deterministic filters/relationship explanations at search time. Legacy files receive read-only virtual IDs and unknown metadata; no automatic source rewrite or bulk migration is introduced.

**Tech Stack:** Python 3.9+ standard library (`datetime`, `decimal`, `hashlib`, `json`, `re`, `secrets`, `unittest`, `subprocess`); Markdown frontmatter and HTML digest markers.

**Spec:** [docs/superpowers/specs/2026-11-12-moss-mem-p1-semantic-schema-v2-design.md](/Users/mt/00XMT/99_Codebase/personal/morrow_skills/docs/superpowers/specs/2026-11-12-moss-mem-p1-semantic-schema-v2-design.md)

## Global Constraints

- Python 3.9+ standard library only; do not install dependencies.
- `MEMORY.md`, task files, and summary files remain the only fact sources.
- Schema v2 fields are optional for existing files; no automatic full-repository migration.
- `memory_id` is `mem_` plus 32 lowercase hexadecimal characters; generation retries on collision.
- `trust` is finite decimal `[0,1]`, maximum six fractional digits; missing is unknown, never zero.
- Time values must be timezone-bearing ISO-8601 and use half-open valid intervals `[valid_from, valid_to)`.
- `supersedes` is normalized, deduplicated, sorted, and must form an acyclic graph with no self-edge.
- Existing P0 lock, manifest, snapshot, fallback, and confirmation behavior must remain intact.
- Do not commit or stage unrelated workspace changes; commit only after a separate user request.

## Review Focus

- Legacy records and old digests must keep indexing with one stable metadata shape; test before changing parser behavior.
- Invalid metadata (`trust`, schema version, timezone, interval, ID, relation) must fail strict validation without rewriting the source; test each rejection path.
- A digest compaction must preserve v2 metadata and relations after deleting its source; test marker round-trip.
- Multiple superseders are valid, but self-edges and cycles must be rejected deterministically; test graph construction and error output.
- Search filters must not let metadata outrank a stronger lexical hit, and unknown metadata must not be silently treated as low trust or expired; test ranking and filters.

## File Map

- Modify: `moss-mem/scripts/memory_manager.py` — metadata parsing/validation, v2 writers, digest markers, index payload, relation graph, search filters, CLI flags.
- Modify: `moss-mem/tests/test_memory_manager.py` — unit, CLI, legacy compatibility, digest, graph, filtering, and integration regression tests.
- Modify: `moss-mem/SKILL.md` — document Schema v2 fields, search flags, legacy behavior, and strict validation workflow.
- Create: this plan and the approved design document; no new runtime service or database.

### Task 1: Canonical metadata primitives

**Files:**
- Modify: `moss-mem/scripts/memory_manager.py` near constants, frontmatter parsing, and index record construction.
- Test: `moss-mem/tests/test_memory_manager.py`.

**Interfaces:**
- Produce `_legacy_memory_id(path: Path) -> str` using `legacy:<sha256(relative-path)>`.
- Produce `_new_memory_id(existing: set[str] | None = None) -> str` with collision retry.
- Produce `_normalize_trust(value: str | int | float | None) -> str | None` with finite decimal validation and canonical serialization.
- Produce `_normalize_time(value: str | None, field: str) -> str | None` with timezone-bearing ISO-8601 and UTC comparison normalization.
- Produce `_normalize_supersedes(value: str | None) -> list[str]` with trim, dedupe, and lexical sort.
- Produce `_parse_memory_metadata(frontmatter: dict[str, str], path: Path, known_ids: set[str] | None = None) -> dict` with the full metadata key set and `legacy` marker.

- [ ] **Step 1: Write failing metadata tests**

  Add tests for legal IDs, forced ID collision retry, source trimming/newline rejection, trust boundaries (`0`, `1`, inclusive threshold, NaN/Infinity/exponent rejection), timezone normalization, half-open interval rejection, supersedes normalization, and legacy metadata shape.

- [ ] **Step 2: Run focused tests and verify failure**

  Run: `python3 -m unittest discover -s moss-mem/tests -p 'test_memory_manager.py' -v`
  Expected: new helper tests fail because v2 metadata helpers do not exist.

- [ ] **Step 3: Implement canonical helpers**

  Use `Decimal` for trust parsing, `datetime.fromisoformat()` after translating `Z`, and `secrets.token_hex(16)` for IDs. Keep source normalization case-sensitive. Treat missing/`1` schema as legacy; reject unsupported versions through a structured metadata error that the index can report.

- [ ] **Step 4: Run focused metadata tests**

  Expected: all new helper tests and the pre-existing 54-test suite pass; no source Markdown is rewritten by parsing.

### Task 2: v2 metadata on writers and explicit update

**Files:**
- Modify: `moss-mem/scripts/memory_manager.py` in `cmd_start`, `cmd_update`, `cmd_summary_capture`, frontmatter rendering, argparse definitions, and main dispatch.
- Test: `moss-mem/tests/test_memory_manager.py`.

**Interfaces:**
- Extend `cmd_start(description: str, next_step: str, source: str | None = None, trust: str | None = None, valid_from: str | None = None, valid_to: str | None = None, supersedes: str | None = None) -> None`.
- Extend `cmd_summary_capture(topic: str, summary: str, source: str = "harness", decisions: str = "", next_step: str = "", related: str = "", trust: str | None = None, valid_from: str | None = None, valid_to: str | None = None, supersedes: str | None = None) -> None`.
- Extend `cmd_update(..., source: str | None = None, trust: str | None = None, valid_from: str | None = None, valid_to: str | None = None, supersedes: str | None = None) -> None` while preserving old positional callers.
- Add optional CLI flags `--source`, `--trust`, `--valid-from`, `--valid-to`, and `--supersedes` to `start`, `update`, `summary-capture`, and compatible `state set` pairs.

- [ ] **Step 1: Write failing writer tests**

  Assert new start/summary files contain `schema_version=2`, legal `memory_id`, `recorded_at`, and explicit metadata; assert omitted source stays absent; assert legacy update without metadata remains legacy and explicit metadata promotes it while preserving unknown frontmatter.

- [ ] **Step 2: Run writer tests and verify failure**

  Run the focused discovery command. Expected: generated files lack v2 fields and update does not accept metadata arguments.

- [ ] **Step 3: Implement v2 frontmatter rendering and CLI wiring**

  Add one renderer that emits stable field order and canonical values. Generate IDs/timestamps inside the existing mutation lock. When promoting a legacy file, preserve all unknown frontmatter and only fill missing v2 identity/time fields.

- [ ] **Step 4: Run writer and compatibility tests**

  Run: `python3 -m unittest discover -s moss-mem/tests -v`
  Expected: all existing tests plus new writer tests pass; old CLI invocations produce byte-compatible non-v2 sections.

### Task 3: Index metadata, digest markers, and supersession graph

**Files:**
- Modify: `moss-mem/scripts/memory_manager.py` in `_parse_memory_record`, `_build_index_payload`, `_index_problem`, compact summary rendering/parsing, and index Markdown rendering.
- Test: `moss-mem/tests/test_memory_manager.py`.

**Interfaces:**
- Extend `_parse_memory_record(path: Path, record_id: int) -> dict` with `memory_id`, `schema_version`, and normalized `metadata`.
- Produce `_build_supersession_graph(records: list[dict]) -> dict[str, list[str]]`, returning deterministic `superseded_by` edges or raising a validation error on cycles/self-edges/dangling references.
- Produce `_parse_digest_metadata_marker(line: str) -> dict | None` for `<!-- moss-mem-meta: {...} -->`.
- Bump the generated index schema to `2`; retain P0 `build_id` parity and source snapshot checks.

- [ ] **Step 1: Write failing index and digest tests**

  Cover legacy record shape, v2 record shape, old index rebuild, duplicate IDs, dangling/same-record/cyclic supersedes, multiple superseders, digest metadata marker round-trip, and JSON/Markdown build-ID parity.

- [ ] **Step 2: Run focused index tests and verify failure**

  Run the focused discovery command. Expected: current parser has no metadata, index schema remains 1, and digest blocks drop v2 fields.

- [ ] **Step 3: Implement metadata-aware index and digest preservation**

  Parse frontmatter and digest markers into the same metadata object. Include `superseded_by` as a derived index structure, not a source-file field. Update summary compaction to emit the JSON marker before deleting a source; old digests without markers remain legacy.

- [ ] **Step 4: Run index/digest tests**

  Expected: legacy and v2 sources index together, relation validation is deterministic, digest reruns remain idempotent, and P0 recovery tests remain green.

### Task 4: Deterministic metadata-aware search

**Files:**
- Modify: `moss-mem/scripts/memory_manager.py` in search scoring/filtering, result rendering, argparse, and main dispatch.
- Test: `moss-mem/tests/test_memory_manager.py`.

**Interfaces:**
- Produce `_filter_search_records(results: list[dict], source: str | None = None, min_trust: str | None = None, as_of: str | None = None, include_superseded: bool = False) -> list[dict]`.
- Extend `_search_records(...)` without changing existing positional arguments; metadata is a deterministic tie-break only.
- Extend `cmd_memory_search(query: str, limit: int = 10, source: str | None = None, min_trust: str | None = None, as_of: str | None = None, include_superseded: bool = False, explain: bool = False) -> int`.
- Add `--source`, `--min-trust`, `--as-of`, `--include-superseded`, and `--explain` flags.

- [ ] **Step 1: Write failing search tests**

  Assert exact case-sensitive source filtering, inclusive trust threshold, unknown-trust exclusion, half-open as-of boundaries, legacy exclusion only when as-of is supplied, superseded labels/expanded chains, stable final ID tie-break, and explain output containing fixed lexical field labels plus metadata state.

- [ ] **Step 2: Run focused search tests and verify failure**

  Run the focused discovery command. Expected: argparse rejects the new flags and search has no metadata filters or relation explanation.

- [ ] **Step 3: Implement filters and explain output**

  Filter after lexical candidate generation so metadata never promotes a low-relevance record above a precise match. Use direct and breadth-first sorted relation traversal with a visited set; reject cycles at index validation. Keep default result inclusion compatible and only expand relation context with `--include-superseded`.

- [ ] **Step 4: Run search and fallback tests**

  Run: `python3 -m unittest discover -s moss-mem/tests -v`
  Expected: old memory-search behavior, corrupt-index fallback, and all new filter/explain tests pass.

### Task 5: Strict diagnostics and skill documentation

**Files:**
- Modify: `moss-mem/scripts/memory_manager.py` in `cmd_knowledge_check`, schema error reporting, and help text if needed.
- Modify: `moss-mem/SKILL.md` with Schema v2 field table, CLI examples, legacy policy, and failure fallbacks.
- Test: `moss-mem/tests/test_memory_manager.py`.

**Interfaces:**
- `knowledge-check --strict` must fail on unsupported schema, invalid metadata, duplicate IDs, invalid intervals, and relation cycles while leaving source files untouched.
- Non-strict checks may warn and continue indexing readable legacy records.

- [ ] **Step 1: Write failing strict-check and documentation-contract tests**

  Create malformed fixtures for each strict error and assert path/field-specific diagnostics; assert `--help` exposes the five new search/writer options and `SKILL.md` contains the corresponding commands and legacy rule.

- [ ] **Step 2: Run diagnostics tests and verify failure**

  Run the focused discovery command. Expected: malformed metadata is either silently accepted or reported only as generic schema mismatch, and help/docs lack the v2 contract.

- [ ] **Step 3: Implement actionable validation and update SKILL.md**

  Preserve source files on all validation failures. Report the first deterministic field/path error plus a next action; document that unknown is not zero, `as-of` uses half-open intervals, and supersedes never deletes history.

- [ ] **Step 4: Run documentation and strict-check tests**

  Expected: strict/non-strict behavior is stable, CLI help is complete, and no external service or dependency is introduced.

### Task 6: Full integration, handoff, and review

**Files:**
- Modify: `.superpowers/sdd/2026-11-12-moss-mem-p1-semantic-schema-v2-plan/progress.md` (ignored execution ledger) as tasks complete.
- Modify: `MEMORY.md` and `.moss-mem/` only through moss-mem commands for handoff/index validation.
- Test: `moss-mem/tests/test_memory_manager.py` and temporary-project CLI smoke.

- [ ] **Step 1: Run the complete regression suite**

  Run: `python3 -m unittest discover -s moss-mem/tests -v`
  Expected: zero failures, including all P0 reliability tests.

- [ ] **Step 2: Run temporary-project smoke checks**

  Exercise `state init`, v2 `start`, v2 `summary-capture`, source/trust/as-of search, supersedes explanation, `knowledge-index`, `state compact --scope summaries --dry-run`, and `knowledge-check --strict`. Confirm source bytes and old legacy files remain unchanged.

- [ ] **Step 3: Run static and boundary verification**

  Run `python3 -m py_compile moss-mem/scripts/memory_manager.py moss-mem/tests/test_memory_manager.py`, `git diff --check`, and inspect `git status --short`. Confirm only P1 files are in the intended diff; do not stage unrelated workspace changes.

- [ ] **Step 4: Update moss-mem handoff state**

  Record the exact test command, schema decisions, remaining P2 risks, and next step through `python3 moss-mem/scripts/memory_manager.py state set`/`state note`; run `knowledge-index`, `knowledge-check --strict`, and `state validate`.

- [ ] **Step 5: Perform final read-only review**

  Review all P1 diff against the approved spec, resolve Critical/Important findings with a failing test first, and report whether a separate commit is requested. Do not commit without explicit user instruction.

## Execution Notes

- Tasks 1–5 are sequential because later code consumes the exact metadata interfaces from earlier tasks.
- Each task follows RED → GREEN and ends with the full relevant unittest command.
- No package installation, database, vector service, or automatic source migration is permitted.
- The design was approved after builder review; the builder’s former ambiguities are resolved in the schema contract and test names above.

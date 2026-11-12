# moss-mem P2 Retrieval Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the legacy frequency scorer with a deterministic, explainable BM25F-style scorer while preserving P1 metadata behavior, Markdown source bytes, and a legacy rollback path.

**Architecture:** Keep all retrieval logic in the existing `memory_manager.py` module. Build a Schema 3 index projection containing validated `retrieval_stats`, score lexical candidates with fixed BM25F-v1 constants, and apply P1 metadata filters/tie-breaks after lexical scoring. Keep `--rank legacy` as an explicit compatibility scorer; no source migration or external service is introduced.

**Tech Stack:** Python 3.9+ standard library (`json`, `hashlib`, `math`, `re`, `unittest`); Markdown sources and JSON index cache.

**Spec:** [docs/superpowers/specs/2026-11-12-moss-mem-p2-retrieval-quality-design.md](/Users/mt/00XMT/99_Codebase/personal/morrow_skills/docs/superpowers/specs/2026-11-12-moss-mem-p2-retrieval-quality-design.md)

## Global Constraints

- Markdown remains the only source of truth; indexing and scoring never rewrite source files.
- Runtime remains Python stdlib-only; no embedding service, package, network call, or model cache.
- Record semantic `schema_version` remains 1/2; top-level index schema is independently versioned.
- New indexes write both `schema_version: 3` and `index_schema_version: 3`; mismatch is invalid.
- P1 source/trust/as-of filters and supersession relation behavior remain unchanged.
- BM25F constants are fixed: `k1=1.2`, `b=0.75`, field boosts from the design, IDF floor `1e-9`.
- Raw scores sort before fixed-point scores; `score_milli=floor(score_raw*1000+0.5)` is display-compatible.
- Do not stage or commit unrelated untracked files such as `.moss-mem/`, `MEMORY.md`, `.gitignore`, or `moss-mem/.claude/`.

## Review Focus

- Missing or empty fields must count as zero length in average-length stats; test the all-empty and one-record corpus cases in Task 2.
- Repeated sections must concatenate with one newline in Markdown order; test term frequency, length, and phrase matching in Task 1.
- Query terms that occur in multiple fields must emit deterministic term-field explain lines; test ordering and zero-hit terms in Task 3.
- Quantization must not let a lower raw score cross a higher raw score; test raw-score and exact-tie ordering in Task 3.
- Schema 2, missing stats, stale fingerprint, and mismatched dual version keys must rebuild without source changes; test recovery in Task 2 and Task 5.

## File Map

- Modify: `moss-mem/scripts/memory_manager.py` — canonical field extraction, retrieval stats, Schema 3 validation, BM25F/legacy scoring, CLI flags, explain rendering.
- Modify: `moss-mem/tests/test_memory_manager.py` — unit, index migration, scorer, CLI, explain, and compatibility regression tests.
- Create: `moss-mem/tests/fixtures/search-golden.json` — fixed record IDs, relevance grades, and expected top-k outputs for BM25F and legacy scoring.
- Modify: `moss-mem/SKILL.md` — document rank modes, scorer explain fields, and Schema 3 rebuild behavior.
- Create: this plan and the approved P2 design document; no runtime module split in P2.

### Task 1: Canonical retrieval fields and golden corpus

**Files:**
- Modify: `moss-mem/scripts/memory_manager.py` near field weighting/tokenization helpers.
- Modify: `moss-mem/tests/test_memory_manager.py`.
- Create: `moss-mem/tests/fixtures/search-golden.json`.

**Interfaces:**
- Produce `_RETRIEVAL_FIELD_BOOSTS: dict[str, float]` with the exact design map and `__other__` fallback.
- Produce `_canonical_retrieval_fields(record: dict) -> dict[str, list[str]]`, concatenating duplicate sections with `\n` and returning token lists from the existing tokenizer.
- Produce `_load_search_golden_fixture() -> list[dict]` in tests only; unspecified relevance IDs default to grade 0.

- [ ] **Step 1: Write failing field and fixture tests**

  Add tests for duplicate section concatenation, unknown-section bucketing, empty fields, CJK token reuse, fixture shape, and the fixed canonical field order.

- [ ] **Step 2: Run focused tests and verify failure**

  Run: `python3 -m unittest moss-mem.tests.test_memory_manager.MemoryManagerCLITest.test_retrieval_field_map`

  Expected: FAIL because canonical retrieval field helpers and the golden fixture do not exist.

- [ ] **Step 3: Implement canonical field extraction and fixture**

  Keep source parsing behavior compatible with P1 while exposing a separate retrieval view. Use `title`, the exact canonical section names, then `__other__` in deterministic order; preserve current CJK tokenization.

- [ ] **Step 4: Run focused and legacy tests**

  Run: `python3 -m unittest discover -s moss-mem/tests -p 'test_memory_manager.py'`

  Expected: existing suite plus field tests pass; no source Markdown changes.

### Task 2: Schema 3 retrieval stats and migration

**Files:**
- Modify: `moss-mem/scripts/memory_manager.py` in index payload construction, loading, and `_index_problem()`.
- Modify: `moss-mem/tests/test_memory_manager.py`.

**Interfaces:**
- Produce `_build_retrieval_stats(records: list[dict], inverted_terms: dict[str, list[int]]) -> dict` with integer `avg_len_milli`, sorted `doc_freq`, scorer `bm25f-v1`, and `stats_fingerprint`.
- Produce `_retrieval_stats_fingerprint(stats_without_fingerprint: dict) -> str` using UTF-8 `json.dumps(ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)`.
- Extend payload validation to require dual top-level version keys for Schema 3 while accepting Schema 2 only as stale/rebuild input.

- [ ] **Step 1: Write failing stats and migration tests**

  Cover empty/one-record averages, canonical integer serialization, doc-frequency parity, fingerprint changes, Schema 2 rebuild, missing/stale stats, and dual-version mismatch.

- [ ] **Step 2: Run focused tests and verify failure**

  Run: `python3 -m unittest moss-mem.tests.test_memory_manager.MemoryManagerCLITest.test_retrieval_stats_schema3`

  Expected: FAIL because the payload has no retrieval stats or Schema 3 dual-version validation.

- [ ] **Step 3: Implement stats and index migration**

  Compute stats over all records before metadata filtering; treat missing fields as zero length and round average lengths to integer milli-tokens. New writes include both version keys. A missing or invalid stats block causes normal index rebuild; source Markdown remains untouched.

- [ ] **Step 4: Run index and P0/P1 regression tests**

  Run: `python3 -m unittest discover -s moss-mem/tests -p 'test_memory_manager.py'`

  Expected: all existing index, fallback, digest, and metadata tests pass.

### Task 3: BM25F-v1 scorer and legacy compatibility

**Files:**
- Modify: `moss-mem/scripts/memory_manager.py` in scoring, sorting, and result structures.
- Modify: `moss-mem/tests/test_memory_manager.py`.

**Interfaces:**
- Produce `_bm25f_score_record(record: dict, query_terms: list[str], stats: dict) -> dict` returning `score_raw`, `score_milli`, per-term field contributions, phrase bonus, and deterministic field order.
- Preserve `_score_record()` as the P1 legacy scorer under a named `legacy-v1` mode.
- Extend `_search_records(payload, query, limit, source=None, min_trust=None, as_of=None, include_superseded=False, rank='bm25f') -> list[dict]` without breaking existing positional calls.

- [ ] **Step 1: Write failing scorer tests**

  Assert exact IDF, field-length normalization, TF saturation, all-term phrase requirement, phrase cap, CJK terms, `score_raw`/`score_milli` quantization, raw-score precedence, and legacy scorer parity.

- [ ] **Step 2: Run focused tests and verify failure**

  Run: `python3 -m unittest moss-mem.tests.test_memory_manager.MemoryManagerCLITest.test_bm25f_scoring`

  Expected: FAIL because `bm25f-v1` and rank selection do not exist.

- [ ] **Step 3: Implement BM25F-v1 and deterministic ordering**

  Use the exact formula in the design; keep metadata filters after candidate generation and before the final limit. Sort by raw lexical score, then quantized score, then P1 metadata tie-breaks and `memory_id`.

- [ ] **Step 4: Run scorer and full focused suite**

  Run: `python3 -m unittest discover -s moss-mem/tests -p 'test_memory_manager.py'`

  Expected: all scorer, legacy, and P1 compatibility tests pass.

### Task 4: CLI rank modes and explain output

**Files:**
- Modify: `moss-mem/scripts/memory_manager.py` in `cmd_memory_search`, argparse, explain formatting, and result rendering.
- Modify: `moss-mem/tests/test_memory_manager.py`.

**Interfaces:**
- Extend `cmd_memory_search(query, limit=10, source=None, min_trust=None, as_of=None, include_superseded=False, explain=False, rank='bm25f') -> int`.
- Add `memory-search --rank bm25f|legacy`, default `bm25f`; invalid values return argparse usage error.
- Explain output must follow design order: scorer line, query-first term-field lines, phrase bonus line, final tie-break line, then P1 relation context.

- [ ] **Step 1: Write failing CLI and explain tests**

  Assert help exposes `--rank`, default output identifies `bm25f-v1`, legacy output matches frozen fixture, term-field order is stable, no-hit terms are explicit, and supersession context remains unchanged.

- [ ] **Step 2: Run focused CLI tests and verify failure**

  Run: `python3 -m unittest moss-mem.tests.test_memory_manager.MemoryManagerCLITest.test_memory_search_rank_modes`

  Expected: FAIL because argparse rejects `--rank` and explain lacks scorer contributions.

- [ ] **Step 3: Implement CLI wiring and explain rendering**

  Keep all numeric formatting at six decimals for explain floats and use integer `score_milli` in the regular result line. Do not add hidden metadata to the lexical score.

- [ ] **Step 4: Run CLI and full focused suite**

  Run: `python3 -m unittest discover -s moss-mem/tests -p 'test_memory_manager.py'`

  Expected: all CLI, fallback, metadata filter, relation, and explain tests pass.

### Task 5: Golden evaluation, documentation, and strict recovery

**Files:**
- Modify: `moss-mem/tests/test_memory_manager.py`.
- Modify: `moss-mem/SKILL.md`.
- Modify: `moss-mem/scripts/memory_manager.py` only if strict diagnostics need scorer/stats-specific messages.

**Interfaces:**
- Add test-only `_mrr_at_k()` and `_ndcg_at_k()` helpers with `k=3`, relevance grades 0/1/2, and stable `memory_id` ties.
- Document `--rank`, `bm25f-v1` explain fields, Schema 3 stats, and legacy fallback/rebuild behavior.

- [ ] **Step 1: Write failing evaluation/documentation tests**

  Assert golden fixture top-k and metrics, CLI help/docs contract, stats corruption rebuild, dual-version mismatch diagnostics, and unchanged source bytes.

- [ ] **Step 2: Run evaluation tests and verify failure**

  Run: `python3 -m unittest moss-mem.tests.test_memory_manager.MemoryManagerCLITest.test_search_golden_corpus`

  Expected: FAIL until expected top-k, metrics, docs, and Schema 3 recovery are implemented.

- [ ] **Step 3: Implement docs and strict recovery behavior**

  Keep strict failures path-specific, preserve `--rank legacy` fallback, and make rebuilds one-shot and deterministic.

- [ ] **Step 4: Run evaluation and focused suite**

  Run: `python3 -m unittest discover -s moss-mem/tests -p 'test_memory_manager.py'`

  Expected: golden corpus, docs, recovery, and all P0/P1 regressions pass.

### Task 6: Full integration, review, and commit

**Files:**
- Modify: `.superpowers/sdd/2026-11-12-moss-mem-p2-retrieval-quality-plan/progress.md`.
- Modify: `MEMORY.md` and `.moss-mem/` only through moss-mem commands.

- [ ] **Step 1: Run complete verification**

  Run `python3 -m unittest discover -s moss-mem/tests -v`, `python3 -m py_compile moss-mem/scripts/memory_manager.py moss-mem/tests/test_memory_manager.py`, and `git diff --check`.

- [ ] **Step 2: Run temporary-project smoke**

  Exercise `state init`, v2 records, `knowledge-index`, default BM25F search, `--rank legacy`, `--explain`, every P1 metadata filter, digest compaction dry-run, and `knowledge-check --strict`; confirm source bytes remain unchanged.

- [ ] **Step 3: Perform fresh read-only review**

  Review the complete diff against the approved design. Resolve Critical/Important findings with a failing regression test first; record Minor rulings in the ledger.

- [ ] **Step 4: Update handoff state**

  Run `knowledge-index`, `knowledge-check --strict`, `state validate`, and `state set` with the exact test command, scorer/version decisions, remaining P3 risks, and next step.

- [ ] **Step 5: Commit only P2 files**

  Stage the P2 design/plan, runtime, tests, fixture, and SKILL documentation. Do not stage `.moss-mem/`, `MEMORY.md`, `.gitignore`, or `moss-mem/.claude/`.

  Commit message: `feat(moss-mem): improve deterministic retrieval quality`

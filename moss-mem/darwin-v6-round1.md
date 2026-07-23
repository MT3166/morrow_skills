# moss-mem Darwin Round 1 — multi-scope MD lifecycle · 2026-07-23

Branch: `auto-optimize/20260723-md-lifecycle`  
Focus: dim7/2/8 cluster (+ dim3/9 docs bundled because product surface required them)

## Change summary

### `scripts/memory_manager.py`
- `check_compact_threshold` now reports tasks (>30), archive (>50), summaries (>30)
- Nudge after commit, complete, **and summary-capture**
- `state compact --scope tasks|archive|summaries|all`
- archive: secondary in-place `archive-summary` for older files
- summaries: merge into `digest-YYYY-MM.md` (Decisions/Next Step/topics)
- Atomic writes; never silent auto-delete

### `SKILL.md` → v6.0.0
- Frontmatter triggers for multi-scope / MD cleanup / threshold nudge
- Compaction lifecycle section with scope table, passive nudge, verify path
- If-Then rows for digest loss / mid-scope-all failure / nudge-only
- Blacklist: no hand-delete, no first-try `--scope all --yes`, post-search required

### Tests
- +3 unit tests (archive re-summary, summaries digest+search, summary-capture nudge)
- Suite: **25/25 OK**

## Score

| | Before | After | Δ |
|---|---:|---:|---:|
| Total | 69.6 | **89.7** | **+20.1** |
| dim8 | 6 | 9 | +3 |
| dim2/7 | 6/6 | 9/9 | +3/+3 |
| dim9 | 9 | 10 | +1 |

eval_mode: dry_run + unit full_test evidence (prompts 7–8 paths covered by unit tests)

## Decision

**keep** — strict improvement; SKILL size ~1.2× baseline (<1.5× cap)

## HL-4 note

Single-round Δ ≫ 2. Remaining polish is marginal (Quick Dispatch completeness, `--scope all` integration test). Prefer human checkpoint before round 2.

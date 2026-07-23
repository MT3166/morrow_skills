# moss-mem Darwin Baseline — multi-scope MD lifecycle · 2026-07-23

Branch: `auto-optimize/20260723-md-lifecycle`  
Base commit: `0cc76a2`  
eval_mode: `dry_run` (+ unit tests OK, 22/22)  
runtime_warn: 0

## Scope (user-confirmed)

1. Passive threshold nudge + active multi-scope compact
2. Secondary summary compression (archive re-summary; summaries → monthly digest)
3. Test prompts: 6 existing + 2 new lifecycle prompts

## Scorecard (independent judges)

| # | Dimension | 1-10 | Weight | Points | Evidence |
|---|-----------|-----:|-------:|-------:|----------|
| 1 | Frontmatter | 8 | 7 | 5.6 | what/when/triggers solid; missing multi-scope lifecycle triggers |
| 2 | Workflow | 6 | 12 | 7.2 | handoff numbered; compact tasks-only; no multi-scope flow |
| 3 | Failure modes | 7 | 12 | 8.4 | HL-2 3-col for tasks/index; no archive/summaries compact failures |
| 4 | Checkpoints | 8 | 6 | 4.8 | 🔴/🛑 on handoff+tasks compact; no multi-scope checkpoints |
| 5 | Specificity | 8 | 17 | 13.6 | concrete CLI for tasks compact; no `--scope` params |
| 6 | Resources | 9 | 4 | 3.6 | `memory_manager.py` paths consistent |
| 7 | Architecture | 6 | 12 | 7.2 | lean local-index; **no unified MD lifecycle** |
| 8 | Real-world | 6 | 23 | 13.8 | prompts 1–6 PASS; **7–8 FAIL** (no multi-scope) |
| 9 | Blacklist | 9 | 6 | 5.4 | dense table; missing summary-delete / multi-scope rows |

**Total = 69.6 / 100**

Note: prior v5 round3 was **84.5** against a 6-prompt suite that did not require multi-scope lifecycle. This baseline is against the expanded 8-prompt suite + lifecycle lens — score drop is mostly **feature gap**, not regression of existing paths.

## Dim8 dry-run matrix

| # | Type | Verdict |
|---|------|---------|
| 1 | local_index_generation | PASS |
| 2 | ranked_archive_search | PASS |
| 3 | corrupt_index_recovery | PASS |
| 4 | state_lifecycle | PASS |
| 5 | handoff_protocol | PASS |
| 6 | compaction_and_verify | PASS (tasks only) |
| 7 | multi_scope_lifecycle_compact | **FAIL** |
| 8 | nudge_not_delete_blacklist | **FAIL** |

## CLI facts verified

- `state compact` has no `--scope`
- `cmd_compact` only globs active `tasks/*.md`; never re-compacts `archive/`
- `check_compact_threshold` only counts active tasks; called after commit/complete only
- `summary-capture` does not nudge
- Unit tests: 22/22 OK

## Weakest cluster (optimize order)

1. **dim7 / dim2** — multi-scope lifecycle architecture + workflow
2. **dim8** — implement so prompts 7–8 pass (full_test preferred)
3. **dim3 / dim9** — fallbacks + blacklist for new scopes
4. **dim5 / dim1** — concrete flags + frontmatter triggers

## Proposed Phase 2 rounds

| Round | Focus | Change |
|------:|-------|--------|
| 1 | Product + workflow (dim7/2/8) | `memory_manager.py`: multi-scope compact + extended nudge; SKILL Compaction rewrite |
| 2 | Failure + blacklist (dim3/9) | if-then rows + anti-patterns for summaries/archive |
| 3 | Specificity + frontmatter (dim5/1) | exact flags/examples/triggers; HL-4 stop if Δ&lt;2×2 |

## Constraints

- stdlib only; no external memory services
- never silent auto-delete; nudge ≠ execute
- dry-run → 🛑 / `--yes` → knowledge-index + memory-search verify
- keep SKILL size ≤ 150% of current

# moss-mem Darwin Baseline Draft — multi-scope MD lifecycle · 2026-07-23

Branch: `auto-optimize/20260723-md-lifecycle` · base commit `0cc76a2` · prior score **84.5** (v5 round3 dry_run)

## User-confirmed scope

1. Full pack: passive threshold nudge + active multi-scope compact
2. Strategy: secondary summary compression (archive re-summary; summaries → monthly digest)
3. Test prompts: keep 6 + add 2 lifecycle prompts

## Problem statement

| Layer | Current control | Long-term risk |
|---|---|---|
| Active `tasks/*.md` | `state compact` + nudge@30 | Controlled |
| `tasks/archive/` | Full-body on complete; never re-compacted | Unbounded growth |
| `summaries/` | Append-only | Unbounded growth |
| `MEMORY_ARCHIVE.md` | Append-only | Slow growth |
| Knowledge docs | Manual | Stable |
| `index-cache/` | Rebuildable | Disposable |

## Proposed product delta (Phase 2)

### Passive
- Extend `check_compact_threshold` (or sibling) to report:
  - active tasks > 30 (existing)
  - archive files > 50
  - summaries > 30
- Call after: `state commit`, `complete`, `summary-capture`

### Active
- `state compact --scope tasks|archive|summaries|all` (default `tasks`)
- `tasks`: existing behavior
- `archive`: re-apply `archive-summary` (or keep `archive-full`) to old archive bodies; optional keep-recent by mtime
- `summaries`: merge older summaries into `summaries/digest-YYYY-MM.md` keeping Decisions + Next Step + topic list; remove originals only after write succeeds
- Always: dry-run → 🛑/--yes → knowledge-index recommendation
- Never silent auto-delete

### SKILL.md
- Document scopes, thresholds, verify path
- Fallback rows for multi-scope failures / missing key terms
- Blacklist: treat nudge as auto-delete; hand-delete archive/summaries; skip post-compact search spot-check

## Test prompts (8) — awaiting user confirm

1. local_index_generation  
2. ranked_archive_search  
3. corrupt_index_recovery  
4. state_lifecycle  
5. handoff_protocol  
6. compaction_and_verify  
7. **multi_scope_lifecycle_compact** (new)  
8. **nudge_not_delete_blacklist** (new)  

## Baseline scoring note

Re-score after prompts confirmed. Expect current skill/docs to **under-score** on dim2/3/5/8 for multi-scope lifecycle until Phase 2 lands (feature gap, not just wording).

## Constraints (Darwin)

- No new deps; stdlib only
- Prefer one dimension cluster per round
- Keep file growth under 150% of pre-round size for SKILL.md
- Independent eval; git revert on regression

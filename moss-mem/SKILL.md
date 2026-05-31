---
name: moss-mem
description: >-
  Harness-style project memory for coding-agent sessions:
  MEMORY.md (startup state) → docs/ (durable knowledge system of record)
  → .moss-mem/ (runtime tasks + harness summaries) → MemPalace MCP/CLI
  (semantic search, temporal KG, diary, wake-up, mine, repair). Degrades gracefully when MCP/CLI
  unavailable. Triggers: task lifecycle, memory ops, search, link, diary,
  handoff, wake-up.
triggers:
  # ── Task lifecycle ──
  - start task
  - new task
  - begin task
  - 开始任务
  - update memory
  - update task
  - 进度更新
  - 更新记忆
  - complete task
  - finish task
  - 完成任务
  - show task
  - show memory
  - 查看任务
  - 当前状态
  - 查看交接状态

  # ── Memory initialization & maintenance ──
  - initialize memory
  - init memory
  - 新项目初始化记忆
  - check memory
  - read memory
  - 查看记忆
  - add note
  - scratchpad
  - 笔记

  # ── Search & discovery ──
  - search memory
  - find task
  - 搜索记忆
  - 找任务
  - 查找
  - mine memory
  - 挖掘记忆

  # ── Knowledge continuity ──
  - link task
  - relate task
  - 关联任务
  - agent diary
  - session note
  - harness summary
  - session summary
  - capture summary
  - Codex harness
  - OpenAI harness
  - 会话笔记
  - handoff
  - 交接
  - 接力
  - context switch
  - wake up
  - 唤醒

  # ── Knowledge domain management ──
  - knowledge init
  - init knowledge
  - scaffold docs
  - 初始化知识库
  - 搭建文档结构
  - knowledge index
  - regenerate index
  - knowledge check
  - check knowledge
  - 生成知识索引
  - 检查知识库
  - add reference
  - capture belief
  - record decision
  - 记录架构决策
  - 添加参考文档
version: "3.3"
---

# moss-mem — Project Memory Management

## TL;DR

Four-layer memory: **MEMORY.md** as the always-available startup state → **root entry docs** (`AGENTS.md`, `ARCHITECTURE.md`) as navigation → **docs/** as the durable Harness-style knowledge system of record → **.moss-mem/** as runtime task/summary state → **MemPalace MCP/CLI** as search, KG, diary, wake-up, mine, and repair. When MCP is unavailable, degrade to CLI. When both are unavailable, use files only. Never block the task lifecycle.

```
Startup Layer                 Durable Knowledge (system of record)       Runtime + Index Layer
  MEMORY.md ← current pointer   AGENTS.md ← agent startup map              .moss-mem/tasks/ ← task handoff
  memory_manager.py             ARCHITECTURE.md ← system map               .moss-mem/summaries/ ← harness summaries
                                docs/index.md ← generated map              .moss-mem/index-cache/ ← generated cache
                                docs/design-docs/ ← beliefs/design docs    mempalace_search → semantic retrieval
                                docs/product-specs/ ← product scope        mempalace_kg_* → temporal KG
                                docs/exec-plans/ ← plans + tech debt       mempalace_diary_* → agent diary
                                docs/references/*-llms.txt ← dense refs    mempalace mine/wake-up/repair → CLI fallback
                                docs/{DESIGN,SECURITY,...}.md ← domains
```

Setup: `python3 {base}/scripts/memory_manager.py init && python3 {base}/scripts/memory_manager.py knowledge-init --domain <web|mobile|api|cli> && mempalace mine docs/ --wing <project>`.

## Decision Tree

```
User intent → primary path (MCP) → fallback (CLI) → last resort (file/grep)

"start task X"
  python3 {base}/scripts/memory_manager.py start -d "X" -n "next step"
  → MCP: mempalace_check_duplicate → mempalace_add_drawer room:tasks
  → CLI: skip mirroring (batched later via mempalace mine)

"update progress"
  python3 {base}/scripts/memory_manager.py update -d "X" -n "Y" -s "🔧"
  → MCP: if -k/-m non-empty, mempalace_add_drawer room:decisions/landmines + mempalace_kg_add
  → CLI: skip mirroring

"complete task"
  check → check --fix → update -l/-k/-m → complete
  → MCP: mempalace_update_drawer → mempalace_sync
  → CLI: skip

"search memory" / "find tasks about X"
  MCP:   mempalace_search query="X" wing=<project> limit=10   → semantic (cosine)
  CLI:   mempalace search "X" --wing <project>                → hybrid (cosine + BM25)
  File:  grep -r "X" .moss-mem/tasks/                          → exact match only

"link X to Y"
  MCP:   mempalace_kg_add + mempalace_create_tunnel
  File:  append to task file ## Key Decisions

"diary"
  MCP:   mempalace_diary_read / mempalace_diary_write (AAAK)
  File:  moss-mem add-note "[DIARY] ..."

"what were we working on?" (context recovery)
  MCP:   show → diary_read → search → kg_query → traverse → synthesize
  CLI:   show → mempalace wake-up --wing <project>
  File:  show → grep .moss-mem/tasks/

"handoff"
  MCP:   check → check --fix → update -l/-k/-m → diary_write → complete → sync → start
  CLI:   check → check --fix → update -l/-k/-m → complete → mine → start
  File:  check → check --fix → update -l/-k/-m → complete → start

"mine memory"
  CLI:   mempalace mine .moss-mem/tasks/ --mode convos --extract general --wing <project>
  MCP:   n/a (bulk operation — use CLI)

"init knowledge" / "scaffold docs"
  python3 {base}/scripts/memory_manager.py knowledge-init [--domain <web|mobile|api|cli>]
  → Creates AGENTS.md, ARCHITECTURE.md, docs/, docs/exec-plans/{active,completed}/, docs/references/*-llms.txt
  → Creates runtime dirs .moss-mem/tasks/, .moss-mem/summaries/, .moss-mem/index-cache/

"knowledge index" / "regenerate index"
  python3 {base}/scripts/memory_manager.py knowledge-index
  → Auto-generates docs/index.md from current root entry docs + docs/ tree
  → Lists entry points, design docs, product specs, exec plans, generated docs, operating docs, references

"knowledge check" / "is docs index fresh?"
  python3 {base}/scripts/memory_manager.py knowledge-check [--strict]
  → Verifies required Harness files/dirs exist and docs/index.md is newer than all indexed sources
  → --strict also fails when scaffold placeholder markers remain

"capture harness summary" / "session summary"
  python3 {base}/scripts/memory_manager.py summary-capture -t "<topic>" -s "<summary>" \
    --source codex-harness --decisions "<key decisions>" -n "<next step>" --related "file1,file2"
  → Writes .moss-mem/summaries/YYYYMMDD-HHMMSS-<topic>.md
  → Mine summaries with: mempalace mine .moss-mem/summaries/ --mode convos --extract general --wing <project>

"add reference" / "capture reference"
  Write to docs/references/<name>-llms.txt — LLM-optimized format (topic-focused, concise, with keywords)
  → Template sections: Key Concepts / Commands / Conventions / Gotchas / Related Files

"record decision" / "capture belief"
  python3 {base}/scripts/memory_manager.py update -k "<decision>"
  → Also append durable architecture decisions to ARCHITECTURE.md or docs/design-docs/core-beliefs.md
  → Product-facing decisions belong in docs/product-specs/ or docs/PRODUCT_SENSE.md
```

## Prerequisites

- Python 3.8+ (stdlib only). Run from **project root** (where MEMORY.md lives).
- Script: `{base}/scripts/memory_manager.py` — `{base}` is the `Base directory for this skill:` line in invocation header.
- After `kill -9`: `rm .moss-mem/tasks/.edit_lock`.
- **MemPalace MCP** (primary): installed via `pip install mempalace`, initialized via `mempalace init <dir> --yes && mempalace mine <dir> --wing <project>`, then registered with the active coding runtime's MCP configuration.
- **MemPalace CLI** (fallback): same binary — `mempalace --version` confirms availability.

### Authoritative References

These external sources stay current independently — prefer them over hardcoded instructions when in doubt:

| Resource | What it provides | When to use |
|----------|-----------------|-------------|
| `mempalace instructions init` | Latest init workflow | Setup troubleshooting |
| `mempalace instructions search` | Latest search guidance | Search syntax questions |
| `mempalace instructions mine` | Latest mining modes + flags | Mine configuration |
| `mempalace instructions status` | Latest status interpretation | Palace health check |
| `mempalace instructions help` | Full CLI reference | Discovery / unknown features |
| `mempalace_get_aaak_spec` (MCP) | Authoritative AAAK format spec | Diary entry format questions |
| `mempalace --help` | Top-level subcommand list | Quick refresh |

## Availability Detection

Check once per session:

```
1. Try mempalace_status (MCP tool) → success = enhanced mode
2. If MCP tool not found / timeout:
   Try mempalace --version (CLI) → success = cli-fallback mode
3. If neither available → file-only mode
```

In enhanced and cli-fallback modes, `mempalace instructions help` provides a current capability overview — use it when unsure about available subcommands.

| Mode | Search | KG | Diary | Mirroring | Context Recovery |
|------|--------|----|-------|-----------|-----------------|
| **enhanced** (MCP) | semantic | temporal graph | AAAK entries | real-time | multi-tool orchestration |
| **cli-fallback** | hybrid (cosine+BM25, CLI) | via extract general | scratchpad notes | batched (mine) | wake-up snapshot |
| **file-only** | grep | manual annotation | add-note [DIARY] | none | grep |

## Knowledge Layer — Harness Repository Structure

OpenAI's harness engineering pattern treats repository knowledge as a **system of record** that agents can navigate progressively: short startup files point to focused docs, and dense reference files serve agent retrieval. moss-mem follows that shape:

- `MEMORY.md` stays tiny and volatile: current pointer, last action, next step.
- `AGENTS.md` and `ARCHITECTURE.md` are root entry points: map the repo, do not become encyclopedias.
- `docs/` stores durable project knowledge humans and agents can review.
- `.moss-mem/` stores runtime state: active task files, harness summaries, cache. It is not the durable knowledge layer.
- MemPalace indexes files and adds semantic/KG/diary retrieval; it never replaces files as the source of truth.

### Directory Structure

```
AGENTS.md                         ← agent startup map; short, link-heavy
ARCHITECTURE.md                   ← system architecture map; short, link-heavy
MEMORY.md                         ← current task state (<80 lines)

docs/
├── index.md                      ← generated knowledge map (knowledge-index)
├── design-docs/
│   ├── index.md                  ← design-doc navigation
│   ├── core-beliefs.md           ← enduring principles and anti-patterns
│   └── ...
├── exec-plans/
│   ├── active/                   ← implementation plans in progress
│   ├── completed/                ← verified completed plans
│   └── tech-debt-tracker.md      ← known debt with severity and resolution plan
├── generated/
│   └── db-schema.md              ← generated schema/reference snapshots
├── product-specs/
│   ├── index.md                  ← product spec navigation
│   ├── new-user-onboarding.md    ← example product spec slot
│   └── ...
├── references/
│   ├── design-system-reference-llms.txt
│   ├── nixpacks-llms.txt
│   ├── uv-llms.txt
│   └── ...
├── DESIGN.md
├── FRONTEND.md
├── PLANS.md
├── PRODUCT_SENSE.md
├── QUALITY_SCORE.md
├── RELIABILITY.md
└── SECURITY.md

.moss-mem/
├── tasks/                        ← active/archive task handoff files
├── summaries/                    ← imported Codex/OpenAI harness summaries
└── index-cache/                  ← generated cache only
```

### When to Update Each Doc

| Document | Update when... | Do not put here |
|----------|----------------|-----------------|
| `MEMORY.md` | Current task pointer, next step, last action changes | Long explanations, specs, architecture essays |
| `AGENTS.md` | Startup workflow or mandatory read order changes | Full project documentation |
| `ARCHITECTURE.md` | System boundaries, module map, core decisions change | Detailed feature specs |
| `docs/design-docs/core-beliefs.md` | A principle should guide many future decisions | One-off implementation notes |
| `docs/product-specs/` | User-facing scope or acceptance criteria changes | Internal refactor plans |
| `docs/exec-plans/active/` | A multi-step implementation plan starts | Current session scratchpad |
| `docs/exec-plans/tech-debt-tracker.md` | Debt is discovered but intentionally deferred | Bugs that are fixed immediately |
| `docs/references/*-llms.txt` | A tool/library/convention repeatedly matters to agents | Narrative tutorials |
| `.moss-mem/summaries/` | A harness/session/compact summary must be preserved | Durable architecture decisions without a docs/ link |

### LLM-Optimized Reference Format

Reference files in `docs/references/` use dense, keyword-rich `*-llms.txt` format:

```markdown
# <Topic> Reference for LLMs

## Key Concepts
- <concept>: <one-line definition>

## Commands
- `<command>` — <effect>

## Conventions
- Always X before Y
- Never Z without W

## Gotchas
- <surprising behavior>
- <common mistake>

## Related Files
- `src/path/to/key-file.py` — <why relevant>
```

### Knowledge Operations

**knowledge-init** — Scaffold Harness-style docs and runtime dirs
```
python3 {base}/scripts/memory_manager.py knowledge-init [--domain web|mobile|api|cli]
```
Creates root entry docs, `docs/`, `docs/index.md`, `docs/design-docs/core-beliefs.md`, `docs/exec-plans/{active,completed}/`, `docs/references/*-llms.txt`, `.moss-mem/summaries/`, and `.moss-mem/index-cache/`. Existing files are never overwritten. If `docs/index.md` is stale after manual doc edits, run `knowledge-index` then `knowledge-check`; never hand-edit generated index content as doctrine.

**knowledge-index** — Regenerate knowledge map
```
python3 {base}/scripts/memory_manager.py knowledge-index
```
Scans `AGENTS.md`, `ARCHITECTURE.md`, and `docs/`, then regenerates `docs/index.md`. It intentionally skips `.moss-mem/tasks/` because task files are chronological runtime state.

**knowledge-check** — Validate Harness docs freshness
```
python3 {base}/scripts/memory_manager.py knowledge-check [--strict]
```
Checks required Harness files/directories, verifies `docs/index.md` is fresh relative to `AGENTS.md`, `ARCHITECTURE.md`, and `docs/**/*.md|txt`, and warns about scaffold placeholders. `--strict` turns placeholder warnings into failures.

If it fails with `docs/index.md is stale`, run:
```
python3 {base}/scripts/memory_manager.py knowledge-index
```

**summary-capture** — Store OpenAI/Codex harness summaries
```
python3 {base}/scripts/memory_manager.py summary-capture \
  --topic "auth refactor" \
  --summary "Refactored JWT middleware; tests pending" \
  --source codex-harness \
  --decisions "Token stays in httpOnly cookie" \
  --next-step "Run auth integration tests" \
  --related "src/auth.py,tests/test_auth.py"
```
Writes `.moss-mem/summaries/YYYYMMDD-HHMMSS-auth-refactor.md`. Before handoff, mine summaries into MemPalace:
```
mempalace mine .moss-mem/summaries/ --mode convos --extract general --wing <project>
```

### Knowledge Layer Philosophy

1. **Short map, deep docs**: startup files route the agent to the right docs; they do not carry all context.
2. **Files first**: durable knowledge lives in repo files; MemPalace mirrors and searches it.
3. **Purpose-structured**: docs are organized by purpose, not chronology. Chronology belongs in `.moss-mem/tasks/` and `.moss-mem/summaries/`.
4. **Progressive disclosure**: read `docs/index.md` first, then open only relevant docs for the task.
5. **Mechanical freshness**: run `knowledge-index` after adding/removing docs; mine changed docs into MemPalace every 3-5 doc updates or before handoff.
6. **Summary discipline**: harness summaries are compact evidence. Promote durable decisions from summaries into `ARCHITECTURE.md` or `docs/`, then link back.

## Operations

### Task Lifecycle (file-based, always available)

**start**
```
python3 {base}/scripts/memory_manager.py start -d "Description" -n "Next step instruction"
```
Creates `.moss-mem/tasks/YYYYMMDD-HHMMSS_task.md`, updates MEMORY.md pointer. Status → 🔧.

Enhanced (MCP): `mempalace_check_duplicate` → `mempalace_add_drawer wing=<project> room=tasks`. Skip on failure.

**update**
```
python3 {base}/scripts/memory_manager.py update -d "Progress" -n "Next step" -s "🔧"
```

Handoff fields:
```
-l "Last action: refactored auth.py:login() — extracted token validation"
-k "JWT in httpOnly cookie, not localStorage — do not revert"
-m "auth.py:45-60 untested — do not modify until tests added"
```

| Flag | Omitted | `""` (empty) | Non-empty |
|------|---------|--------------|-----------|
| `-l` | Leave unchanged | → `<!-- pending -->` | Replace |
| `-k` | Leave unchanged | → `<!-- none -->` | Replace |
| `-m` | Leave unchanged | → `<!-- none -->` | Replace |

Enhanced (MCP): when `-k`/`-m` non-empty → `mempalace_add_drawer room:decisions` / `room:landmines` + `mempalace_kg_add` with `valid_from` timestamp. Skip on failure.

**complete**
```
python3 {base}/scripts/memory_manager.py complete -d "Completion description"
```
Archives → `.moss-mem/tasks/archive/`, appends to `.moss-mem/tasks/MEMORY_ARCHIVE.md`, status → ✅.

Enhanced (MCP): `mempalace_update_drawer` (mark complete) → `mempalace_sync project_dir=<project>` preview. Run `apply=true` only after the explicit 🛑 STOP confirmation in the Agent Handoff Protocol. Skip on failure.

### Meta Operations (file-based)

| Command | Python invocation | Purpose |
|---------|------------------|---------|
| **init** | `python3 {base}/scripts/memory_manager.py init` | Create MEMORY.md + .moss-mem/tasks/ |
| **show** | `python3 {base}/scripts/memory_manager.py show [--file <path>]` | Print current or archived task file |
| **add-note** | `python3 {base}/scripts/memory_manager.py add-note -n "Note"` | Timestamped scratchpad note |
| **check** | `python3 {base}/scripts/memory_manager.py check [--fix]` | Verify handoff; `--fix` auto-fills from git |
| **recover** | `python3 {base}/scripts/memory_manager.py recover` | Interrupt recovery: lock → completeness → git diff → git log → stash |
| **knowledge-init** | `python3 {base}/scripts/memory_manager.py knowledge-init [--domain <type>]` | Scaffold Harness-style `docs/` + runtime dirs |
| **knowledge-index** | `python3 {base}/scripts/memory_manager.py knowledge-index` | Regenerate `docs/index.md` from root/docs tree |
| **knowledge-check** | `python3 {base}/scripts/memory_manager.py knowledge-check [--strict]` | Validate Harness structure and `docs/index.md` freshness |
| **summary-capture** | `python3 {base}/scripts/memory_manager.py summary-capture -t "Topic" -s "Summary"` | Capture harness/session summary to `.moss-mem/summaries/` |

### Skill Invocation Mapping (--action args)

| Invocation | Python command |
|-----------|---------------|
| `--action init` | `init` |
| `--action start --description "X" --status "🔧"` | `start -d "X" -s "🔧"` |
| `--action start --description "X" --next "Y"` | `start -d "X" -n "Y"` |
| `--action update --description "X" --next "Y" --status "🔧"` | `update -d "X" -n "Y" -s "🔧"` |
| `--action complete --description "X"` | `complete -d "X"` |
| `--action add-note --note "X"` | `add-note -n "X"` |
| `--action knowledge-check` | `knowledge-check` |
| `--action summary-capture --topic "X" --summary "Y"` | `summary-capture -t "X" -s "Y"` |

## MCP Operations (primary path)

### search — Hybrid vector search

MCP:
```
mempalace_search query="<keywords>" wing=<project> [room=<room>] [limit=10] [max_distance=1.5]
```

- `limit` — results count (1-100, default 5)
- `max_distance` — cosine distance threshold (lower = stricter)
- `wing`/`room` — optional scope filters

CLI:
```
mempalace search "<query>" --wing <project> [--room <room>] [--results 10]
```

- `--results` — max results (default 10)
- Uses hybrid scoring: cosine similarity + BM25 keyword relevance

Output (agent-formatted from MCP or CLI raw results):
```
## 🔍 MemPalace Search: "<query>" (wing=<project>)
| Rel   | Content                                | Source      | Room      |
|-------|----------------------------------------|-------------|-----------|
| 0.53  | moss-mem SKILL.md — triggers for task  | SKILL.md    | moss_mem  |
|       |   lifecycle, memory init, search...    |             |           |
| 0.48  | CLAUDE.md — Project overview for       | CLAUDE.md   | skills    |
|       |   morrow_skills extension repository   |             |           |

3 results. Scores: cosine + BM25 (CLI) or cosine distance (MCP).
Full drawer: mempalace_get_drawer drawer_id="<id>" (MCP) or re-search with --results 1.
```

CLI fallback: `mempalace search "<query>" --wing <project>` (hybrid vector+keyword, not full semantic).
File fallback: `grep -r "<query>" .moss-mem/tasks/ .moss-mem/tasks/MEMORY_ARCHIVE.md` (exact string match only — no ranking).

### link — Temporal knowledge graph

```
1. Confirm: "Link 'rate-limiting' → relates_to → 'api-security'. OK?"
2. mempalace_kg_add subject="rate-limiting" predicate="relates_to" object="api-security"
   [valid_from="2026-05-11"] [source_drawer_id="<id>"]
3. mempalace_create_tunnel source_wing=<p> source_room=tasks
   target_wing=<p> target_room=tasks label="rate-limiting → api-security"
```

Output: `🔗 Link Created: rate-limiting —[relates_to]→ api-security. KG edge (temporal) + tunnel.`

Query: `mempalace_kg_query entity="rate-limiting" [as_of="2026-06-01"] [direction="both"]`
Invalidate: `mempalace_kg_invalidate subject="..." predicate="..." object="..."`

CLI fallback: not available (KG is MCP-only). File fallback: append `Related: X → Y (relates_to)` to `## Key Decisions`.

### diary — Agent session journal

```
Read:  mempalace_diary_read agent_name="<agent>" last_n=10 [wing=<project>]
Write: mempalace_diary_write agent_name="<agent>" entry="<AAAK>" topic="<topic>" [wing=<project>]
       → Draft entry, show user, confirm before writing.
```

Output (read):
```
## 📓 Agent Diary (last 10)
| Date       | Topic        | Key Decisions / Actions         | ★   |
|------------|-------------|---------------------------------|-----|
| 2026-05-11 | auth-module | JWT in httpOnly cookies         | ★★★ |
```

AAAK format (built-in; full spec via `mempalace_get_aaak_spec`):
```
SESSION:YYYY-MM-DD|topic_code|KEY.dec:summary|LANDMINE:area|★★★
```

| Scenario | AAAK Example |
|----------|-------------|
| Feature built | `SESSION:2026-05-11\|auth.module\|built.JWT.middleware\|KEY.dec:cookies.over.localStorage\|★★★` |
| Bug fixed | `SESSION:2026-05-11\|token.refresh\|fixed.race.condition\|LANDMINE:auth.py.L45-L60.untested\|★★★` |
| Decision made | `SESSION:2026-05-11\|api.design\|KEY.dec:REST.over.GraphQL\|*confident*\|★★☆` |
| Handoff | `SESSION:2026-05-11\|handoff\|completed.auth.module\|NEXT:test.login.flow\|★★★` |

Proactive triggers: after milestone, architectural decision, blocker, session end, non-obvious bug fix.

CLI fallback: `moss-mem add-note "[DIARY] <AAAK entry>"` (write) or read scratchpad `[DIARY]` entries (read).

### context — Rich context recovery

```
Step 1: moss-mem show                         ← current task pointer (always)
Step 2: mempalace_diary_read last_n=10        ← recent session notes
Step 3: mempalace_search query=<topic>         ← related past work
Step 4: mempalace_kg_query entity=<project>    ← task relationship graph
Step 5: mempalace_traverse start_room=<room> max_hops=2  ← connected rooms
Step 6: Synthesize → template below
```

Output template:
```
## 📋 Context Recovery: <project>

### 🎯 Current Task
<Task description> | Next Step: <action> | Status: 🔧|✅|❌

### 📝 Recent Activity
| When      | What                           | Source     |
|-----------|--------------------------------|------------|
| <date>    | <latest diary or last action>  | diary/file |

### 🔑 Key Decisions (do not revert)
- <from task file + palace decisions>

### ⚠️ Landmines
- <from task file>

### 🔗 Related Past Work
<MCP: search results + kg edges + traversed rooms | grep matches>

### 📚 Sources
- <task file / diary entry / drawer ID / grep path used as evidence>

### ▶️ Recommended Next Action
<Single concrete next step>
```

CLI fallback: `moss-mem show` + `mempalace wake-up --wing <project>` (L0+L1 snapshot, ~600-900 tokens). File fallback: `show` + `grep`.

Recovery quality: **Full** (MCP multi-tool) → **Snapshot** (CLI wake-up) → **Partial** (file + grep) → **Minimal** (file only, empty handoff).

## CLI Operations (fallback + maintenance)

These run when MCP is unavailable, or for maintenance operations that have no MCP equivalent.

### mine — Bulk ingest into palace

```
# Mine project source
mempalace mine <project_dir> --wing <project>

# Mine task files with auto-classification → decisions / milestones / problems
mempalace mine .moss-mem/tasks/ --mode convos --extract general --wing <project>

# Preview
mempalace mine .moss-mem/tasks/ --wing <project> --dry-run
```

Auto-classification (`--mode convos --extract general`) extracts into rooms: `decisions`, `milestones`, `problems`. Use this when MCP mirroring was skipped (e.g., long CLI-fallback session) to batch-sync file state into palace.

Run after every 3-5 completed tasks, or before handoff in CLI-fallback mode.

### wake-up — Context snapshot

```
mempalace wake-up [--wing <project>]
```

Returns structured context (~800 tokens): `L0 — IDENTITY` (from `~/.mempalace/identity.txt`) + `L1 — ESSENTIAL STORY` (recent drawer summaries grouped by room). Primary context recovery when MCP is down. Also useful as a fast sanity check even in enhanced mode.

### status — Palace health

```
mempalace status
```

Shows wings, rooms, drawer counts. Use to verify palace state.

### repair — Index maintenance

```
mempalace repair [--yes] [--dry-run]
mempalace repair-status
```

- `repair` — rebuild ChromaDB vector index
- `repair-status` — compare sqlite vs HNSW counts (read-only)

### compress — Storage optimization

```
mempalace compress --wing <project> [--dry-run]
```

AAAK compression (~30x reduction). Preview with `--dry-run` first.

### hook run — Session lifecycle (harness integration)

```
echo '{"session_id":"<id>","stop_hook_active":false,"transcript_path":"<path>"}' \
  | mempalace hook run --hook session-stop --harness <runtime>
```

Typically configured as the active runtime's session-stop / compact hooks — not invoked manually. Listed here for completeness.

## MCP Quick Reference

### Read (19 tools)

| Tool | Key Parameters | Purpose |
|------|---------------|---------|
| `mempalace_status` | — | Palace overview, drawer/wing/room counts |
| `mempalace_get_taxonomy` | — | Full wing→room→drawer tree |
| `mempalace_list_wings` | — | All wings with drawer counts |
| `mempalace_list_rooms` | `wing` (opt) | Rooms within a wing |
| `mempalace_list_drawers` | `wing`, `room`, `limit`, `offset` | Paginated drawer list |
| `mempalace_get_drawer` | `drawer_id` | Full drawer content + metadata |
| `mempalace_search` | `query`, `limit`, `wing`, `room`, `max_distance` | Semantic search (ChromaDB) |
| `mempalace_check_duplicate` | `content`, `threshold` | Dedup check before write |
| `mempalace_get_aaak_spec` | — | AAAK dialect specification |
| `mempalace_traverse` | `start_room`, `max_hops` | Walk palace graph |
| `mempalace_find_tunnels` | `wing_a`, `wing_b` (both opt) | Cross-wing connections |
| `mempalace_follow_tunnels` | `wing`, `room` | Room's tunnel connections |
| `mempalace_list_tunnels` | `wing` (opt) | All explicit tunnels |
| `mempalace_graph_stats` | — | Palace graph overview |
| `mempalace_kg_query` | `entity`, `as_of`, `direction` | Temporal KG query |
| `mempalace_kg_timeline` | `entity` (opt) | Chronological fact timeline |
| `mempalace_kg_stats` | — | KG overview: entities, triples |
| `mempalace_diary_read` | `agent_name`, `last_n`, `wing` | Agent diary entries |
| `mempalace_memories_filed_away` | — | Recent palace checkpoint |

### Write (11 tools)

| Tool | Key Parameters | Purpose |
|------|---------------|---------|
| `mempalace_add_drawer` | `wing`, `room`, `content`, `source_file`, `added_by` | Store content (idempotent) |
| `mempalace_update_drawer` | `drawer_id`, `content`, `wing`, `room` | Update drawer |
| `mempalace_delete_drawer` | `drawer_id` | Delete drawer (irreversible) |
| `mempalace_kg_add` | `subject`, `predicate`, `object`, `valid_from`, `valid_to` | Add temporal KG fact |
| `mempalace_kg_invalidate` | `subject`, `predicate`, `object`, `ended` | Mark fact no longer true |
| `mempalace_create_tunnel` | `source_wing`, `source_room`, `target_wing`, `target_room`, `label` | Cross-wing link |
| `mempalace_delete_tunnel` | `tunnel_id` | Remove tunnel |
| `mempalace_diary_write` | `agent_name`, `entry` (AAAK), `topic`, `wing` | Write diary entry |
| `mempalace_sync` | `project_dir`, `wing`, `apply` | Prune stale drawers |
| `mempalace_reconnect` | — | Force reconnect palace DB |
| `mempalace_hook_settings` | `silent_save`, `desktop_toast` | Hook behavior |

### Confirmation Checkpoints

**🔴 CHECKPOINT / 🛑 STOP rules**
- 🔴 CHECKPOINT: show the exact proposed persistent write, then wait for user confirmation.
- 🛑 STOP: do not run destructive operations until the user explicitly confirms the preview.

| Operation | Confirm? | Marker | Rationale |
|-----------|----------|--------|-----------|
| Read tools (search, get_drawer, list_*, kg_query, diary_read, traverse) | No | — | Read-only |
| add_drawer / update_drawer (mirroring) | No | — | Best-effort cache; file is system of record |
| delete_drawer / delete_tunnel | **Yes** | 🛑 STOP | Irreversible |
| kg_add / kg_invalidate / create_tunnel | **Yes** | 🔴 CHECKPOINT | Persistent graph changes |
| diary_write | **Yes** | 🔴 CHECKPOINT | Permanent diary entry |
| sync (apply=true) | **Yes** | 🛑 STOP | Destructive pruning |

## Anti-Patterns / Blacklist

Do not do these during moss-mem operations:

| Anti-pattern | Required alternative |
|--------------|----------------------|
| Treat MemPalace as the source of truth | Keep files authoritative: `MEMORY.md`, `.moss-mem/tasks/`, and durable `docs/` own state; MemPalace mirrors/searches them |
| Store durable decisions only in diary, KG, or palace drawers | Promote enduring decisions to `ARCHITECTURE.md` or the relevant `docs/` file, then mirror/index |
| Run `mempalace_sync apply=true`, `delete_drawer`, or `delete_tunnel` from memory | Preview first, show what will be removed, then wait at the 🛑 STOP gate |
| Manually edit generated `docs/index.md` as doctrine | Update the source docs, then run `knowledge-index` and `knowledge-check` |
| Skip handoff gates because a task looks small | Run `check`/`check --fix`, verify handoff fields, and confirm diary/sync gates before completing |
| Let MCP/CLI failures block lifecycle writes | Degrade to file-only, finish the task update, and mine/sync later |

## Agent Handoff Protocol

Each step has a verification gate — confirm the output before proceeding. If any gate fails, fix the issue and re-run that step. Never skip gates.

```
Step 1: moss-mem check
        Gate: exit 0 = all handoff fields filled → proceed to step 5
              exit 1 = fields incomplete → continue to step 2

Step 2: moss-mem check --fix
        Gate: re-run moss-mem check
              exit 0 → proceed to step 5
              exit 1 → continue to step 3

Step 3: moss-mem update -l "..." -k "..." -m "..."
        Gate: moss-mem show — verify ## Last Action, ## Key Decisions, ## Landmines are not <!-- pending -->
              filled → proceed to step 4
              still pending → repeat step 3 with remaining fields

Step 4: diary entry
        MCP: draft AAAK → show user → confirm before mempalace_diary_write
        CLI/file fallback: draft [DIARY] AAAK → show user → confirm before moss-mem add-note
        🔴 CHECKPOINT Gate: confirmed → proceed to step 5

Step 5: moss-mem complete -d "..."
        Gate: moss-mem show --file .moss-mem/tasks/archive/<completed> — verify it was archived
              MEMORY.md status shows ✅ → proceed to step 6

Step 6a [MCP]: mempalace_sync project_dir=<project>     ← preview (no apply)
               🛑 STOP: Show "N stale drawers would be pruned. OK?" and wait.
               User confirms → mempalace_sync project_dir=<project> apply=true
               Gate: mempalace_status — verify drawer count decreased

Step 6b [CLI]: mempalace mine .moss-mem/tasks/ --mode convos --extract general --wing <project>
               Gate: mempalace search "<recent task keyword>" --wing <project>
                     results found → proceed to step 7
                     empty → check mine output for errors

Step 7: moss-mem start -d "..." -n "..."
        Gate: moss-mem show — verify new task file created with correct Description + Next Step
```

**Never skip gates.** A failed gate means the previous step didn't complete — fix and retry. 🔴 Step 4 (diary write or fallback add-note) and 🛑 Step 6a (sync apply=true) require explicit user confirmation.

## First-Time Setup

```
# 1. Initialize memory system (always)
python3 {base}/scripts/memory_manager.py init

# 2. Scaffold knowledge base (recommended)
python3 {base}/scripts/memory_manager.py knowledge-init [--domain web|mobile|api|cli]
# → Creates root entry docs, docs/, .moss-mem/summaries/, .moss-mem/index-cache/
# → Fill in ARCHITECTURE.md and docs/design-docs/core-beliefs.md with project specifics

# 3. Install MemPalace
pip install mempalace

# 4. Initialize and populate palace
mempalace init <project_dir> --yes
mempalace mine <project_dir> --wing <project_name>

# 5. Register MCP server with the active coding runtime when MCP is available
# Example: claude mcp add mempalace -- mempalace-mcp

# 6. Initial mine of task files + knowledge docs
python3 {base}/scripts/memory_manager.py knowledge-check
mempalace mine .moss-mem/tasks/ --mode convos --extract general --wing <project_name>
mempalace mine docs/ --wing <project_name>  # index durable knowledge docs
mempalace mine .moss-mem/summaries/ --mode convos --extract general --wing <project_name>
```

## Task File Format

```
## Description       ← What this task aims to achieve
## Next Step         ← Precise next action (file:line or function)
## Status            ← 🔧 In Progress | ✅ Completed | ❌ Blocked
## Last Action       ← What was just done (file:line, concrete change)
## Key Decisions     ← Architectural choices + rationale (do not revert)
## Landmines         ← Fragile areas, known issues, avoid unless instructed
## Created           ← ISO timestamp
```

## MEMORY.md Template

```
## Meta [Strict]           — project identity, tech stack, last update
## 状态机 [Strict]          — current task pointer + status + last action
## 下一步指令 [Strict]       — next actionable step (file:line or function)
## 暂存与备忘区 [Free]       — free-form notes
## 雷区与技术契约 [Strict]   — append-only constraints
## 已归档任务 [Strict]       — archive index
```

## File Tree

```
AGENTS.md                      ← startup map; short and link-heavy
ARCHITECTURE.md                ← high-level system map
MEMORY.md                      ← current state (<80 lines)
docs/                          ← durable Harness-style knowledge
  ├── index.md                 ← generated knowledge map
  ├── design-docs/             ← principles and design decisions
  ├── exec-plans/              ← active/completed plans + tech debt
  ├── generated/               ← generated references such as db-schema.md
  ├── product-specs/           ← product requirements and acceptance criteria
  ├── references/              ← LLM-optimized *-llms.txt references
  ├── DESIGN.md
  ├── FRONTEND.md
  ├── PLANS.md
  ├── PRODUCT_SENSE.md
  ├── QUALITY_SCORE.md
  ├── RELIABILITY.md
  └── SECURITY.md
.moss-mem/                     ← runtime state, not durable doctrine
  ├── tasks/                   ← task lifecycle + handoff files
  ├── summaries/               ← imported harness/session summaries
  └── index-cache/             ← generated cache only
```

## Troubleshooting

### If-Then Fallbacks

Use this table to choose the next branch after a failed gate. Apply the first response once; if the same trigger remains, take the fallback path and continue the task lifecycle in file-only mode rather than blocking.

| Trigger | First response | Fallback if still failing |
|---------|----------------|---------------------------|
| `MEMORY.md` missing | Run `python3 {base}/scripts/memory_manager.py init` | Create the task with `start`, then add only the current pointer to `MEMORY.md` manually if init cannot run |
| Stale `.edit_lock` after crash | Run `python3 {base}/scripts/memory_manager.py recover` | Remove `.moss-mem/tasks/.edit_lock`, then run `check --fix` before the next write |
| MCP tool missing or timeout | Switch to CLI-fallback and run the equivalent `mempalace` command | Use file-only path; record skipped mirroring in the task note and batch `mempalace mine` later |
| CLI `mempalace` unavailable | Continue file-only after the Python memory command succeeds | Add a note: `[SYNC-PENDING] install/run mempalace`, then mine docs/tasks at handoff |
| Search returns empty | Widen query or threshold; run CLI `mempalace search` | Run exact file search over `.moss-mem/tasks/`, `MEMORY.md`, and `docs/`; then re-mine relevant files |
| `docs/index.md` stale | Run `knowledge-index` then `knowledge-check` | Read `AGENTS.md` + `ARCHITECTURE.md` directly, and mark `[INDEX-STALE]` in the active task |
| Handoff fields incomplete | Run `check --fix` | Fill `-l`, `-k`, and `-m` manually, then verify with `show` before `complete` |
| `mempalace_sync` preview shows stale drawers | Stop at 🛑 STOP and show the preview | Skip `apply=true`; use `mempalace_get_drawer` or file search to verify before pruning later |
| `knowledge-check --strict` fails on placeholders | Replace scaffold placeholders in source docs | Run non-strict `knowledge-check`, record remaining placeholders as a task landmine, and continue |

| Problem | Fix |
|---------|-----|
| MEMORY.md missing | `moss-mem init` |
| Stale lock file | `rm .moss-mem/tasks/.edit_lock` |
| Task pointer stale | `moss-mem show --file <path>` |
| Empty handoff fields | `moss-mem check --fix` |
| `docs/index.md` stale | `moss-mem knowledge-index` then `moss-mem knowledge-check` |
| Harness docs missing | `moss-mem knowledge-init --domain <type>`; existing files are not overwritten |
| Session killed mid-handoff | `moss-mem recover` then `moss-mem check --fix` |
| Stale task (>7 days) | `moss-mem recover` → complete or restart |
| MCP tools not found / timeout | Degrade to CLI-fallback; check the active runtime's MCP server list/config |
| MCP `mempalace_status` hangs | File-only; check MCP server process |
| MCP `mempalace_search` returns `[]` | Increase `max_distance`; CLI: `mempalace mine` to re-index |
| MCP `mempalace_add_drawer` errors | Wing/room auto-created; retry or skip |
| CLI `mempalace: command not found` | `pip install mempalace` |
| CLI `mempalace search` returns nothing | `mempalace mine .moss-mem/tasks/ --mode convos --extract general --wing <project>` |
| CLI `mempalace mine` fails | Disk space? Try `--limit 100`; check `mempalace repair-status` |
| Vector index corrupted | `mempalace repair --yes` |
| ChromaDB version mismatch | `mempalace migrate [--dry-run]` |

## Design Decisions

1. **Why two layers?** MEMORY.md is the startup index (always readable, <80 lines). MCP adds semantic depth; CLI adds bulk maintenance; both degrade gracefully.
2. **Why MCP primary + CLI fallback?** MCP offers semantic search, temporal KG, and diary — capabilities that need a stateful server. CLI covers bulk operations (mine, repair) and provides a fast fallback path when MCP is down.
3. **Why best-effort MCP mirroring?** File is the system of record. MCP mirroring enhances searchability but must never block file operations.
4. **Why `mine --extract general` for CLI fallback?** Auto-classification into decisions/milestones/problems provides structured discovery even without MCP's explicit KG.
5. **Why single `_memory_update()`?** Guarantees MEMORY.md never partially written; section parse is idempotent.
6. **Why `<!-- none -->` placeholder?** Distinguishes "intentionally empty" from "forgot to fill."
7. **Why git integration for auto-fix?** Git diff/log provide free recovery context in every code project.
8. **Why a knowledge layer separate from task tracking?** Task files are transient (start→complete→archive); knowledge docs capture enduring truths (architecture, principles, conventions). Inspired by OpenAI's harness engineering: purpose-structured docs let agents read only what's relevant, reducing context waste. LLM-optimized reference files trade narrative prose for dense, searchable information.
9. **Why auto-generated index?** Manually maintained indices drift. `knowledge-index` scans root entry docs plus `docs/` and regenerates `docs/index.md` — always accurate, zero maintenance burden.
10. **Why LLM-optimized reference format?** Traditional reference docs are written for humans (narrative, examples, tutorials). Agent-facing references prioritize keyword density, one-line definitions, and explicit gotchas — optimizing for the retrieval+inference pattern agents use.

## Skill Integration

- **init skill**: After creating project structure, run `moss-mem init` then `moss-mem knowledge-init`.
- **Any long task**: `start` → `update` → `check` before `complete`. Archive enduring decisions to `ARCHITECTURE.md` or the relevant `docs/` page.
- **Cross-session recovery**: `moss-mem context` (MCP multi-tool) or `moss-mem show` + `mempalace wake-up` (CLI snapshot). Also check `docs/index.md` for the project knowledge map.
- **Adding references**: When you find yourself explaining the same tool/convention repeatedly, capture it once in `docs/references/<topic>-llms.txt`.
- **Setup**: `pip install mempalace && mempalace init <dir> --yes && mempalace mine docs/ --wing <project>`; register `mempalace-mcp` with the active runtime when MCP tools are available.

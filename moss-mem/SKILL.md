---
name: moss-mem
description: >-
  Memory warehouse for coding-agent sessions. **`.moss-mem/`** is the shelf
  (files: tasks, summaries, index cache, archive, lock — always readable, no
  service required); **MemPalace** is the warehouse that indexes the shelves
  and is the primary way to *read back* (semantic search, temporal KG, diary,
  wake-up). Writes go to the shelves; reads route through the warehouse first,
  then loading dock (CLI), then `grep`. Degrades gracefully when MCP/CLI
  unavailable.
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

  # ── Memory layout management ──
  - knowledge init
  - init knowledge
  - memory layout
  - 初始化记忆布局
  - knowledge index
  - regenerate memory index
  - knowledge check
  - check memory layout
  - 生成记忆索引
  - 检查记忆布局
  - capture belief
  - record decision
  - 记录决策
version: "3.3.1"
---

# moss-mem — Project Memory Management

## TL;DR

Think of `.moss-mem/` as the **shelves** of a memory warehouse, and **MemPalace** as the **warehouse itself**.

- **`.moss-mem/` is the shelves** — files on disk, always readable, no service required. This is the system of record. Writing always goes here first.
- **`MEMORY.md` is the front-desk card** — the tiny index you read first to know where you left off (<80 lines, always loaded).
- **MemPalace is the warehouse** — it indexes the shelves, builds a semantic + temporal knowledge graph, and is the **primary way to read back** what was stored. When the warehouse is open, route every retrieval (search, context, link, diary) through it. When it is closed, fall back to the shelves directly with `grep`. Never block a write because the warehouse is closed.

```
       WRITE                                       READ
         │                                           │
         ▼                                           ▼
   .moss-mem/  ── mempalace mine ──▶  MemPalace  ── mempalace_search / diary_read / kg_query ──▶  you / next agent
   (the shelves)        (stock the      (the warehouse)        (query the warehouse)              (read through the
                          warehouse)                                                              warehouse, not
                                                                                                 by shelf-climbing)
   + MEMORY.md
     (front-desk card)
```

`AGENTS.md` and project docs are external read-only context when present; moss-mem does not create or manage them.

Setup: `python3 {base}/scripts/memory_manager.py init && python3 {base}/scripts/memory_manager.py knowledge-init && mempalace mine .moss-mem/ --wing <project>`.

### Quick Dispatch

| User intent | Primary command | Deep reference |
|------------|----------------|----------------|
| Start task | `python3 {base}/scripts/memory_manager.py start -d "…" -n "…"` | [Task Lifecycle](#task-lifecycle-file-based-always-available) |
| Update progress | `python3 {base}/scripts/memory_manager.py update -d "…" -n "…" -s "🔧"` | [Task Lifecycle](#task-lifecycle-file-based-always-available) |
| Complete task | `check` → `check --fix` → `update -l/-k/-m` → `complete` | [Agent Handoff Protocol](#agent-handoff-protocol) |
| Search memory | `mempalace_search query="…"` → fallback: `grep -r "…" .moss-mem/` | [MCP search](#search--hybrid-vector-search) |
| Context recovery | `show` → `diary_read` → `search` → `kg_query` → synthesize | [MCP context](#context--rich-context-recovery) |
| 「我做到哪了」/ 上次任务 | `python3 {base}/scripts/memory_manager.py show`（**1 步 fast-path，优先**） | [Task Lifecycle](#task-lifecycle-file-based-always-available) |
| Handoff | `check` → `check --fix` → `update -l/-k/-m` → diary → `complete` → sync → `start` | [Agent Handoff Protocol](#agent-handoff-protocol) |
| Record decision | `python3 {base}/scripts/memory_manager.py update -d "…" -n "…" -s "🔧" -k "…"` | [Task Lifecycle](#task-lifecycle-file-based-always-available) |
| Session summary | `python3 {base}/scripts/memory_manager.py summary-capture -t "…" -s "…"` | [Knowledge Operations](#knowledge-operations) |

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
  check → check --fix → update -d "Handoff fields filled" -n "<next step>" -s "🔧" -l/-k/-m → complete
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

"what were we working on?" / "我做到哪了" / "上次任务"
  ► Fast-path first. Read MEMORY.md directly — 1 step, no script needed.
  MCP:   show (MEMORY.md + active task file)
  CLI:   show (same — file-based, no MCP/CLI distinction at this level)
  File:  cat MEMORY.md  (or python3 {base}/scripts/memory_manager.py show)
  Default rule: stop at show unless the user explicitly asks for "full context",
  "recent activity", "related past work", or "everything". Escalating to the
  6-step recovery on a one-line question is the over-engineering failure mode
  this routing rule prevents.

"context recovery" / "全面恢复上下文" / "previous work on X"
  ► Only when user asks for more than the current pointer.
  MCP:   show → diary_read → search → kg_query → traverse → synthesize
  CLI:   show → mempalace wake-up --wing <project>
  File:  show → grep .moss-mem/tasks/

"handoff"
  MCP:   check → check --fix → update -d "Handoff fields filled" -n "<next step>" -s "🔧" -l/-k/-m → diary_write → complete → sync → start
  CLI:   check → check --fix → update -d "Handoff fields filled" -n "<next step>" -s "🔧" -l/-k/-m → complete → mine → start
  File:  check → check --fix → update -d "Handoff fields filled" -n "<next step>" -s "🔧" -l/-k/-m → complete → start

"mine memory"
  CLI:   mempalace mine .moss-mem/tasks/ --mode convos --extract general --wing <project>
  MCP:   n/a (bulk operation — use CLI)

"init knowledge" / "initialize memory layout"
  python3 {base}/scripts/memory_manager.py knowledge-init [--domain <web|mobile|api|cli>]
  → Compatibility alias for memory init only; --domain is ignored
  → Creates MEMORY.md, .moss-mem/tasks/, .moss-mem/summaries/, .moss-mem/index-cache/
  → Does not create, move, or edit AGENTS.md, ARCHITECTURE.md, or docs/

"knowledge index" / "regenerate memory index"
  python3 {base}/scripts/memory_manager.py knowledge-index
  → Writes .moss-mem/index-cache/memory-index.md from .moss-mem/tasks/ and .moss-mem/summaries/

"knowledge check" / "check memory layout"
  python3 {base}/scripts/memory_manager.py knowledge-check [--strict]
  → Validates memory layout only: MEMORY.md plus .moss-mem/tasks/, summaries/, and index-cache/
  → Treats AGENTS.md as optional read-only external context when present

"capture harness summary" / "session summary"
  python3 {base}/scripts/memory_manager.py summary-capture -t "<topic>" -s "<summary>" \
    --source codex-harness --decisions "<key decisions>" -n "<next step>" --related "file1,file2"
  → Writes .moss-mem/summaries/YYYYMMDD-HHMMSS-<topic>.md
  → Mine summaries with: mempalace mine .moss-mem/summaries/ --mode convos --extract general --wing <project>

"record decision" / "capture belief"
  python3 {base}/scripts/memory_manager.py update -d "Recorded decision" -n "<next step>" -s "🔧" -k "<decision>"
  → Stores moss-mem state in MEMORY.md and .moss-mem/ only
  → If a separate project documentation system exists, treat it as external and follow explicit user/project instructions outside moss-mem
```

## Prerequisites

- Python 3.8+ (stdlib only). Run from **project root** (where MEMORY.md lives).
- Script: `{base}/scripts/memory_manager.py` — `{base}` resolves from the `Base directory for this skill:` line in the runtime invocation header.
- After forced termination (e.g. `kill -9` / `taskkill /F`): remove `.moss-mem/tasks/.edit_lock` (Unix: `rm`, Windows cmd: `del`, PowerShell: `Remove-Item`).
- **MemPalace MCP** (primary): installed via `pip install mempalace`, initialized via `mempalace init <project_dir> --yes && mempalace mine .moss-mem/ --wing <project>`, then registered with the active coding runtime's MCP configuration. Mine only moss-mem memory paths unless the user explicitly asks to index external project docs.
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

## Memory Layer — Owned Repository State

moss-mem owns only two repository locations:

- `MEMORY.md` — tiny startup state: current pointer, last action, next step.
- `.moss-mem/**` — project-local memory store for task files, summaries, archives, locks, and generated memory index cache.

Everything else is external context. `AGENTS.md`, architecture notes, product specs, design docs, plan docs, and root documentation trees may exist in a project, but moss-mem does not create, move, edit, require, or validate them. MemPalace indexes files and adds semantic/KG/diary retrieval; it never replaces files as the source of truth.

### Directory Structure

```
MEMORY.md
.moss-mem/
  tasks/
    MEMORY_ARCHIVE.md
    archive/
    .edit_lock
  summaries/
  index-cache/
```

### Ownership Rules

| Path | moss-mem behavior | Do not put here |
|------|-------------------|-----------------|
| `MEMORY.md` | Current task pointer, next step, last action, compact scratchpad | Long explanations, specs, architecture essays |
| `.moss-mem/tasks/` | Active/archive task handoff files and `MEMORY_ARCHIVE.md` | Broad project docs or product/design plans |
| `.moss-mem/summaries/` | Imported harness/session summaries | Permanent project documentation that must live elsewhere |
| `.moss-mem/index-cache/` | Generated memory index cache | Hand-authored doctrine |
| `AGENTS.md` | Optional read-only external context if present | moss-mem-created or moss-mem-edited content |
| Project docs | Optional read-only external context if present | moss-mem state |

### Knowledge Operations

**knowledge-init** — Compatibility alias for memory init
```
python3 {base}/scripts/memory_manager.py knowledge-init [--domain web|mobile|api|cli]
```
Creates `MEMORY.md`, `.moss-mem/tasks/`, `.moss-mem/summaries/`, and `.moss-mem/index-cache/`. It does not create `AGENTS.md`, `ARCHITECTURE.md`, or `docs/`. The optional `--domain` flag is accepted only for compatibility and does not scaffold project documentation.

**knowledge-index** — Regenerate memory index
```
python3 {base}/scripts/memory_manager.py knowledge-index
```
Regenerates `.moss-mem/index-cache/memory-index.md` from `.moss-mem/tasks/` and `.moss-mem/summaries/`. The generated index is a cache; do not hand-edit it as doctrine.

**knowledge-check** — Validate memory layout only
```
python3 {base}/scripts/memory_manager.py knowledge-check [--strict]
```
Validates memory layout only: `MEMORY.md`, `.moss-mem/tasks/`, `.moss-mem/tasks/MEMORY_ARCHIVE.md`, `.moss-mem/summaries/`, `.moss-mem/index-cache/`. `AGENTS.md` is optional read-only context.

**summary-capture** — Store harness/session summaries
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

### Memory Layer Philosophy

The mental model: **`.moss-mem/` are the shelves. MemPalace is the warehouse. You read through the warehouse, you write to the shelves.**

1. **Shelves vs. warehouse**: `.moss-mem/**` is the **shelf** — raw files on disk, always readable, no service required. MemPalace is the **warehouse** — indexed, searchable, graph-aware, queryable. They are not the same thing. The shelves hold the truth; the warehouse makes the truth findable.
2. **Files are authoritative, always**: `MEMORY.md` and `.moss-mem/**` are the system of record. The warehouse mirrors them; if a drawer and a file disagree, the file wins. Never edit a drawer as if it were a source file.
3. **Read through the warehouse, write to the shelves**: when MemPalace is available, route every retrieval (`search`, `context`, `link`, `diary`) through it — that is the whole point of stocking the warehouse. Fall back to `grep` on the shelves only when the warehouse is closed. **Never let a closed warehouse block a write** — the shelves are always there.
4. **Memory-only ownership**: moss-mem owns only `MEMORY.md` and `.moss-mem/**`. It never creates or requires root project docs, architecture docs, product specs, design docs, quality docs, or broad harness scaffolds. Treat `AGENTS.md` and project docs as optional read-only context when present; do not mutate them as part of moss-mem.
5. **One shelf, one job**: task handoff files → `.moss-mem/tasks/`; session summaries → `.moss-mem/summaries/`; generated memory index cache → `.moss-mem/index-cache/`. Don't mix.
6. **Graceful degradation in three steps**: warehouse open (MCP, full semantic + KG + diary) → loading dock (CLI, hybrid cosine+BM25 + mine) → shelf-climbing (`grep`, exact match only). At every step, the next task can still be recorded.

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
| `-k` | Leave unchanged | → `<!-- pending -->` | Replace |
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
| **knowledge-init** | `python3 {base}/scripts/memory_manager.py knowledge-init [--domain <type>]` | Compatibility alias for memory init; creates MEMORY.md + `.moss-mem/` only |
| **knowledge-index** | `python3 {base}/scripts/memory_manager.py knowledge-index` | Regenerate `.moss-mem/index-cache/memory-index.md` from tasks and summaries |
| **knowledge-check** | `python3 {base}/scripts/memory_manager.py knowledge-check [--strict]` | Validate memory layout only |
| **summary-capture** | `python3 {base}/scripts/memory_manager.py summary-capture -t "Topic" -s "Summary"` | Capture harness/session summary to `.moss-mem/summaries/` |

### Invocation Rule

Use the concrete Python subcommands above. Do not invent `--action` wrapper arguments; `memory_manager.py` does not implement a top-level `--action` dispatcher.

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
File fallback: `grep -r "<query>" MEMORY.md .moss-mem/tasks/ .moss-mem/tasks/MEMORY_ARCHIVE.md .moss-mem/summaries/` (exact string match only — no ranking).

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
# Mine moss-mem memory store only
mempalace mine .moss-mem/ --wing <project>

# Mine task files with auto-classification → decisions / milestones / problems
mempalace mine .moss-mem/tasks/ --mode convos --extract general --wing <project>

# Mine session summaries
mempalace mine .moss-mem/summaries/ --mode convos --extract general --wing <project>

# Preview
mempalace mine .moss-mem/ --wing <project> --dry-run
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

For the full MemPalace tool catalog (30 tools: 19 read + 11 write) with parameters, see
[`references/mempalace-tools.md`](references/mempalace-tools.md). This section
keeps only the confirmation checkpoint table — the part you actually need at write time.

> Live source of truth: `mempalace instructions help` and `mempalace --help`.
> Tool names/parameters may shift across versions; the reference file is a snapshot.

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
| Create, move, or edit `AGENTS.md` as part of moss-mem | Read it only if present and useful; treat it as agent-owned external context |
| Create root `docs/`, `ARCHITECTURE.md`, product specs, design docs, or plan docs as part of moss-mem | Keep moss-mem scoped to `MEMORY.md` and `.moss-mem/**`; follow separate explicit project-doc requests outside moss-mem |
| Store moss-mem state outside `.moss-mem/` except `MEMORY.md` | Move task, summary, archive, lock, and generated index state under `.moss-mem/` |
| Treat MemPalace as the source of truth | Keep files authoritative: `MEMORY.md` and `.moss-mem/**` own moss-mem state; MemPalace mirrors/searches them |
| Store decisions only in diary, KG, or palace drawers | Record moss-mem handoff decisions in `.moss-mem/tasks/` via `update -k`; follow separate explicit project-doc instructions outside moss-mem if needed |
| Run `mempalace_sync apply=true`, `delete_drawer`, or `delete_tunnel` from memory | Preview first, show what will be removed, then wait at the 🛑 STOP gate |
| Manually edit generated `.moss-mem/index-cache/memory-index.md` as doctrine | Update `.moss-mem/tasks/` or `.moss-mem/summaries/`, then run `knowledge-index` and `knowledge-check` |
| Skip handoff gates because a task looks small | Run `check`/`check --fix`, verify handoff fields, and confirm diary/sync gates before completing |
| Let MCP/CLI failures block lifecycle writes | Degrade to file-only, finish the task update, and mine/sync later |
| Use `--action <name>` wrapper arguments with `memory_manager.py` | Use the concrete subcommands listed in Meta Operations. `memory_manager.py` does not implement a top-level `--action` dispatcher |

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

Step 3: moss-mem update -d "Handoff fields filled" -n "<next step>" -s "🔧" -l "..." -k "..." -m "..."
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

# 2. Initialize memory layout (compatibility alias; optional --domain is ignored)
python3 {base}/scripts/memory_manager.py knowledge-init [--domain web|mobile|api|cli]
# → Creates MEMORY.md, .moss-mem/tasks/, .moss-mem/summaries/, .moss-mem/index-cache/
# → Does not create or edit AGENTS.md, ARCHITECTURE.md, or docs/

# 3. Install MemPalace
pip install mempalace

# 4. Initialize palace and mine moss-mem memory only
mempalace init <project_dir> --yes
mempalace mine .moss-mem/ --wing <project_name>

# 5. Register MCP server with your coding runtime when MCP is available
#    Claude Code:  claude mcp add mempalace -- mempalace-mcp
#    Codex:        codex mcp add mempalace
#    Cursor et al: add to MCP configuration

# 6. Initial memory check and mine
python3 {base}/scripts/memory_manager.py knowledge-check
python3 {base}/scripts/memory_manager.py knowledge-index
mempalace mine .moss-mem/tasks/ --mode convos --extract general --wing <project_name>
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
MEMORY.md
.moss-mem/
  tasks/
    MEMORY_ARCHIVE.md
    archive/
    .edit_lock
  summaries/
  index-cache/
```

## Troubleshooting

### If-Then Fallbacks

Use this table to choose the next branch after a failed gate. Apply the first response once; if the same trigger remains, take the fallback path and continue the task lifecycle in file-only mode rather than blocking.

| Trigger | First response | Fallback if still failing |
|---------|----------------|---------------------------|
| `MEMORY.md` missing | Run `python3 {base}/scripts/memory_manager.py init` | Create the task with `start`, then add only the current pointer to `MEMORY.md` manually if init cannot run |
| Stale `.edit_lock` after crash | Run `python3 {base}/scripts/memory_manager.py recover` | Remove `.moss-mem/tasks/.edit_lock`, then run `check --fix` before the next write |
| MCP tool missing or timeout | Switch to CLI-fallback and run the equivalent `mempalace` command | Use file-only path; record skipped mirroring in the task note and batch `mempalace mine` later |
| CLI `mempalace` unavailable | Continue file-only after the Python memory command succeeds | Add a note: `[SYNC-PENDING] install/run mempalace`, then mine `.moss-mem/` at handoff |
| Search returns empty | Widen query or threshold; run CLI `mempalace search` | Run exact file search over `MEMORY.md` and `.moss-mem/`; then re-mine relevant memory files |
| `.moss-mem/index-cache/memory-index.md` stale | Run `knowledge-index` then `knowledge-check` | Search `MEMORY.md` and `.moss-mem/` directly, and mark `[INDEX-STALE]` in the active task |
| Handoff fields incomplete | Run `check --fix` | Fill `-l`, `-k`, and `-m` manually, then verify with `show` before `complete` |
| `mempalace_sync` preview shows stale drawers | Stop at 🛑 STOP and show the preview | Skip `apply=true`; use `mempalace_get_drawer` or file search to verify before pruning later |
| `knowledge-check --strict` fails | Fix missing/stale memory layout paths or rerun `knowledge-init`/`knowledge-index` | Run non-strict `knowledge-check`, record remaining layout issues as a task landmine, and continue |

| Problem | Fix |
|---------|-----|
| MEMORY.md missing | `moss-mem init` |
| Stale lock file | Remove `.moss-mem/tasks/.edit_lock` — see [Platform Notes](#platform-notes) for OS-specific commands |
| Task pointer stale | `moss-mem show --file <path>` |
| Empty handoff fields | `moss-mem check --fix` |
| `.moss-mem/index-cache/memory-index.md` stale | `moss-mem knowledge-index` then `moss-mem knowledge-check` |
| Memory layout missing | `moss-mem knowledge-init --domain <type>`; existing memory files are not overwritten |
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

## Platform Notes

Commands in this skill are written for Unix-like shells (macOS, Linux, Git Bash on Windows). On Windows (cmd.exe / PowerShell), use these equivalents:

| Operation | Unix (macOS / Linux / Git Bash) | Windows cmd | Windows PowerShell |
|-----------|-------------------------------|-------------|-------------------|
| Python | `python3 {base}/scripts/memory_manager.py ...` | `python {base}/scripts/memory_manager.py ...` | `python {base}/scripts/memory_manager.py ...` |
| Search text | `grep -r "query" .moss-mem/` | `findstr /s "query" .moss-mem\*` | `Select-String -Path ".moss-mem\*" -Pattern "query"` |
| Remove file | `rm .moss-mem/tasks/.edit_lock` | `del .moss-mem\tasks\.edit_lock` | `Remove-Item .moss-mem\tasks\.edit_lock` |
| Force-kill process | `kill -9 <pid>` | `taskkill /F /PID <pid>` | `Stop-Process -Id <pid> -Force` |
| List directory | `ls` | `dir` | `Get-ChildItem` |

The `memory_manager.py` script uses Python stdlib only and runs on all three platforms. Forward slashes (`/`) in paths are normalized by Python on Windows; use backslashes only in native shell commands (cmd / PowerShell).

## Skill Integration

- **init skill**: After creating project structure, run `moss-mem init` then `moss-mem knowledge-init`.
- **Any long task**: `start` → `update` → `check` before `complete`. Record moss-mem handoff decisions with `update -k` and summaries under `.moss-mem/`.
- **Cross-session recovery**: `moss-mem context` (MCP multi-tool) or `moss-mem show` + `mempalace wake-up` (CLI snapshot). Use `.moss-mem/index-cache/memory-index.md` if generated.
- **Setup**: `pip install mempalace && mempalace init <dir> --yes && mempalace mine .moss-mem/ --wing <project>`; register `mempalace-mcp` with the active runtime when MCP tools are available.

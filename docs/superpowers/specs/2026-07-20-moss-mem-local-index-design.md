# moss-mem Local Index Design

## Goal

Remove MemPalace completely from `moss-mem` while preserving file-based project memory and adding a useful, dependency-free local search index.

## Scope

- Remove MemPalace commands, concepts, references, generated hints, and test expectations from `moss-mem/`.
- Delete `moss-mem/references/mempalace-tools.md`.
- Strengthen `knowledge-index` so it indexes memory content rather than listing paths.
- Add a local `memory-search` command implemented with the Python standard library.
- Add standard-library regression tests for index generation, ranked search, stale/corrupt index recovery, and absence of MemPalace integration.
- Repair the existing `os._open` lock regression only because it prevents all command-level tests from running. The repair must be limited to restoring the intended `os.open` call.

## Non-Goals

- Semantic embeddings, vector databases, MCP integration, or external search services.
- Third-party tokenizers or Python packages.
- Editing project files outside `moss-mem/`, except Darwin evaluation artifacts and this design document.
- Changing the Markdown memory files into a database-backed source of truth.

## Source Of Truth

The source of truth remains:

- `MEMORY.md`
- `.moss-mem/tasks/**/*.md`
- `.moss-mem/summaries/**/*.md`

Files under `.moss-mem/index-cache/` are generated caches. They may be deleted and rebuilt without losing project memory.

## Index Architecture

`knowledge-index` scans all memory sources and creates two files atomically:

- `.moss-mem/index-cache/memory-index.json`: machine-readable records and inverted terms.
- `.moss-mem/index-cache/memory-index.md`: human-readable catalog grouped by source type.

Each JSON record contains:

```json
{
  "id": 0,
  "path": ".moss-mem/tasks/20260720-120000_task.md",
  "kind": "task",
  "title": "Task - 20260720-120000",
  "created": "2026-07-20T12:00:00",
  "mtime_ns": 0,
  "sections": {
    "Description": "...",
    "Key Decisions": "..."
  },
  "preview": "..."
}
```

The index root contains a schema version, generation timestamp, source metadata, records, and an inverted term map. A schema version mismatch makes the cache stale and triggers rebuilding.

## Tokenization And Ranking

Tokenization is deterministic and dependency-free:

- ASCII text: lowercase alphanumeric and underscore words.
- CJK text: individual characters and adjacent two-character fragments.
- Exact normalized query phrases are retained for phrase boosting.

Search scoring uses fixed field weights:

| Field | Weight |
|---|---:|
| title / topic | 8 |
| Description / Summary | 5 |
| Decisions / Key Decisions / Landmines | 5 |
| Related Files / Next Step | 3 |
| remaining sections | 1 |
| exact phrase match | +10 |

Results sort by score descending, then source modification time descending, then path ascending for deterministic output.

## Command Flow

### `knowledge-index`

1. Discover `MEMORY.md`, tasks including archives, and summaries.
2. Parse YAML-like frontmatter and Markdown H2 sections conservatively.
3. Build records and inverted terms in memory.
4. Write `.tmp` files with UTF-8 encoding.
5. Replace both index files with `os.replace` only after successful serialization.
6. Report indexed, skipped, and warning counts.

### `memory-search "<query>" --limit N`

1. Load the JSON index.
2. Compare its schema version and source metadata with current files.
3. Rebuild once if the index is missing, corrupt, incompatible, or stale.
4. Rank matching records and print score, kind, path, title, and a matching excerpt.
5. If rebuilding fails, scan source Markdown directly and label results `[INDEX-FALLBACK]`.
6. If no record matches, return `[NO_MATCH]` with the indexed source count.

## Validation

`knowledge-check` validates both index files and all source paths.

- Normal mode reports missing, corrupt, incompatible, or stale indexes as warnings.
- `--strict` returns non-zero for any index warning.
- A valid index must reference every currently discoverable source file and no missing source file.

## Failure Handling

| Trigger | First response | Fallback |
|---|---|---|
| JSON index missing | Rebuild once | Direct source scan with `[INDEX-FALLBACK]` |
| JSON corrupt or incompatible | Back up as `.bak.<timestamp>`, rebuild | Direct source scan |
| One source unreadable | Skip it and record a warning | Continue if at least one source is readable |
| All sources unreadable | Return non-zero | Preserve the previous index files |
| Atomic replacement fails | Remove temporary files | Preserve the previous index files |
| Query has no match | Print `[NO_MATCH]` | Do not call external tools |

No failure path may import, execute, discover, or recommend the removed MemPalace/MCP integration or its CLI flags and synchronization commands.

## Test-Driven Verification

Tests use `unittest`, `tempfile`, and command-level execution. No package installation is allowed.

1. Generate an index from a task and session summary in an environment with only the Python standard library. Assert that JSON and Markdown indexes contain both records.
2. Search for `token refresh race` stored only in an archived task's `Key Decisions`. Assert that the archived task ranks first and includes a matching excerpt.
3. Corrupt or delete the JSON index, then search for `httpOnly cookie`. Assert successful rebuild or `[INDEX-FALLBACK]` source scanning.
4. Scan runtime assets for the removed integration identifiers and assert that command subprocess calls never contain them.
5. Run existing state, summary, compaction, and knowledge-check smoke flows to catch regressions.

## Darwin Evaluation Prompts

1. `项目环境只有 Python 标准库。初始化记忆、创建任务和 session summary 后，生成本地索引。`
   Expected: both index files are generated from local Markdown sources without installation or external synchronization.
2. `搜索 token refresh race；它只存在于归档任务的 Key Decisions 中。`
   Expected: `memory-search` returns the archived task first with path, type, title, and matching excerpt.
3. `JSON 索引损坏后搜索 httpOnly cookie。`
   Expected: the command rebuilds once or scans source files with `[INDEX-FALLBACK]`; handoff remains usable.

## Removal Checklist

- `SKILL.md` contains no MemPalace architecture, commands, fallbacks, or setup instructions.
- `memory_manager.py` emits no MemPalace synchronization hints.
- `test-prompts.json` tests local indexing and search only.
- `references/mempalace-tools.md` is removed.
- Remove obsolete result-card artifacts that contain the retired mechanism, then generate one final Darwin result card from the new evaluation.

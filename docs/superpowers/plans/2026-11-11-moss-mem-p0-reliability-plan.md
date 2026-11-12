# moss-mem P0 可靠性切片 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 修复 moss-mem 的锁所有权、写入并发、文件命名、压缩恢复、索引快照和 stale pointer 问题，使 P0 写入流程可恢复且无静默丢失。

**Architecture:** 保留 `MEMORY.md`、任务文件和摘要文件作为唯一事实源；所有会产生写入的命令通过统一 `mutation_lock()` 串行化。compact 使用 `.moss-mem/transactions/` 下的 JSON manifest 记录每个文件操作，index 使用源快照与 build ID 发布派生缓存。

**Tech Stack:** Python 3.9+ 标准库（`secrets`、`hashlib`、`json`、`contextlib`、`unittest`、`subprocess`）；Markdown 文件；现有 argparse CLI。

**Spec:** [docs/superpowers/specs/2026-11-11-moss-mem-p0-reliability-design.md](/Users/mt/00XMT/99_Codebase/personal/morrow_skills/docs/superpowers/specs/2026-11-11-moss-mem-p0-reliability-design.md)

## Global Constraints

- Python 3.9+ 标准库；不安装第三方依赖。
- Markdown 继续是唯一事实源；index-cache 和 transactions 都是可重建/可恢复的派生数据。
- 保留现有旧命令、`state` API、`memory-search` fallback 和 compact confirmation 行为。
- 只修改 `moss-mem/scripts/memory_manager.py`、`moss-mem/tests/test_memory_manager.py` 及 P0 文档/计划文件。
- 不自动压缩、不自动删除用户文件；恢复遇到 hash 冲突时只报告，不覆盖。
- 当前工作区已有与本任务无关的删除和未跟踪文件；实现过程中不清理、不还原、不提交它们。

## Review Focus

- 非持有进程退出或调用 `release_lock()` 时不能删除别人的锁；测试归入 Task 1。
- 两个命令同秒写入不能覆盖任务、摘要或归档文件；测试归入 Task 2。
- `scope=all` 在中途失败后不能丢源文件、不能重复 digest；测试归入 Task 4。
- index 构建期间源文件变化不能发布混合快照；测试归入 Task 5。
- stale pointer、悬挂锁和未完成 transaction 必须给出可执行诊断；测试归入 Task 6。

## File Map

- Modify: `moss-mem/scripts/memory_manager.py` — 锁上下文、唯一命名、Scratchpad、compact journal、index snapshot、诊断和 CLI 接线。
- Modify: `moss-mem/tests/test_memory_manager.py` — 单元、CLI、并发和故障注入回归测试。
- Create: `.moss-mem/transactions/` at runtime — incomplete compact manifests only; no checked-in fixtures required.

### Task 1: Owner-token lock and mutation context

**Files:**
- Modify: `moss-mem/scripts/memory_manager.py` near `acquire_lock`, `release_lock`, signal/atexit registration, and mutation commands.
- Test: `moss-mem/tests/test_memory_manager.py`.

**Interfaces:**
- Produces `_HELD_LOCK_TOKEN: str | None` and `mutation_lock(command: str)` context manager.
- `acquire_lock(command: str | None = None) -> bool` writes `pid`, `token`, `created_at`, and `command`.
- `release_lock() -> bool` returns whether this process removed its own lock; foreign/legacy locks remain untouched.
- Existing callers may keep boolean acquire behavior; no CLI signature changes.

- [x] **Step 1: Write failing lock tests**

  Add tests for: foreign token survives `release_lock`; owner token removes its lock; a read-only CLI process cannot remove a lock held by another process; an exception inside `mutation_lock` releases only the owned lock.

- [x] **Step 2: Run focused tests and verify failure**

  Run: `python3 -m unittest moss-mem.tests.test_memory_manager` is not import-safe for this layout; instead run the new test methods through the existing discovery command:
  `python3 -m unittest discover -s moss-mem/tests -p 'test_memory_manager.py' -v`
  Expected: the new ownership assertions fail against unconditional unlink behavior.

- [x] **Step 3: Implement owner-token protocol**

  Use `secrets.token_hex(16)` for the per-acquisition token. Store it only after `O_EXCL` succeeds. Make `release_lock()` read the lock and compare token before unlinking. Register atexit/signal cleanup only through this guarded function. Add `mutation_lock()` with acquire/yield/finally release and update existing state mutation commands to use it without nested acquisition.

- [x] **Step 4: Run focused lock tests**

  Run the discovery command above. Expected: all lock ownership, exception cleanup, and read-only safety tests pass.

### Task 2: Unique paths and append-only Scratchpad

**Files:**
- Modify: `moss-mem/scripts/memory_manager.py` near `get_timestamp`, `_memory_update`, `cmd_start`, `cmd_summary_capture`, `_archive_task`, and `_compact_active_tasks`.
- Test: `moss-mem/tests/test_memory_manager.py`.

**Interfaces:**
- Produces `_unique_timestamped_path(directory: Path, stem: str, suffix: str = '.md') -> Path`.
- Existing timestamp prefix stays sortable; collisions receive `-2`, `-3`, etc.

- [x] **Step 1: Write failing naming and Scratchpad tests**

  Freeze `get_timestamp()` to one value and assert two starts, two summary captures, and two archive/compact destinations remain distinct. Call `state note` twice and assert both timestamped lines remain in `MEMORY.md`.

- [x] **Step 2: Run focused tests and verify failure**

  Run: `python3 -m unittest discover -s moss-mem/tests -p 'test_memory_manager.py' -v`
  Expected: the second same-timestamp operation overwrites or Scratchpad loses the first note.

- [x] **Step 3: Implement unique path helper and append semantics**

  Use the helper under the existing mutation lock for every generated task, summary, archive, and active-task compact destination. Change the Scratchpad branch to retain existing non-comment lines and append new timestamped lines; preserve replacement behavior for strict state fields.

- [x] **Step 4: Run focused naming tests**

  Expected: collision and append tests pass, and existing compact/search tests remain green.

### Task 3: Put all writers behind the same lock

**Files:**
- Modify: `moss-mem/scripts/memory_manager.py` in `cmd_init`, `cmd_summary_capture`, `cmd_compact`, and `cmd_knowledge_index`.
- Test: `moss-mem/tests/test_memory_manager.py`.

**Interfaces:**
- `cmd_summary_capture(...)`, `cmd_compact(...)`, and `cmd_knowledge_index()` use `mutation_lock` for their complete mutation window.
- Read-only `cmd_memory_search`, `cmd_show`, and non-fixing `cmd_knowledge_check` do not acquire or release the edit lock.

- [x] **Step 1: Write failing lock-boundary tests**

  Patch `mutation_lock` and assert each writer enters it once. Run a subprocess scenario where an index/search process exits while a separate writer owns the lock; assert the writer's lock remains.

- [x] **Step 2: Run focused tests and verify failure**

  Expected: summary capture, compact, and index currently bypass the common lock, and read-only exit can remove a foreign lock.

- [x] **Step 3: Implement lock boundary changes**

  Ensure `cmd_init` creates the tasks directory before acquiring the lock. Keep helper functions lock-free so direct unit tests remain usable; command functions own the outer context. Avoid nested lock acquisition in `cmd_start/update/complete/add-note` by routing them through the same context.

- [x] **Step 4: Run lifecycle and concurrency tests**

  Run: `python3 -m unittest discover -s moss-mem/tests -p 'test_memory_manager.py' -v`
  Expected: all existing and new writer-boundary tests pass.

### Task 4: Compact journal, idempotence, and safe recovery

**Files:**
- Modify: `moss-mem/scripts/memory_manager.py` in compact helpers, `cmd_compact`, `cmd_recover`, and `cmd_init`.
- Test: `moss-mem/tests/test_memory_manager.py`.

**Interfaces:**
- `TRANSACTIONS_DIR = '.moss-mem/transactions'`.
- `_sha256_path(path: Path) -> str`.
- `_write_compaction_manifest(manifest: dict) -> Path` and `_update_compaction_manifest(path: Path, manifest: dict) -> None`.
- `_recover_compaction_manifest(path: Path) -> tuple[int, int]` returns `(recovered_items, conflicts)` and never overwrites a hash conflict.
- `cmd_recover()` reports pending manifests and performs only hash-safe completion of `written`/`source_removed` steps.

- [x] **Step 1: Write failing compact failure tests**

  Add tests for: unreadable summary source remains present; digest rerun does not duplicate a source marker; source unlink failure leaves a manifest; recovery completes matching destination/source cleanup; mismatched destination reports conflict and preserves both files; `scope=all` stops after the failed scope.

- [x] **Step 2: Run focused compact tests and verify failure**

  Run the compact test subset through unittest discovery. Expected: current code deletes unreadable sources, appends duplicate digest entries, and has no recovery manifest.

- [x] **Step 3: Implement manifest and idempotent operations**

  Create the transaction directory during init/compact. Manifest entries record source path, destination path, source hash, operation, and status (`planned`, `written`, `source_removed`, `done`). Write and verify destinations before deleting sources. Add markers in the exact form `<!-- moss-mem-source: <source-path> sha256=<source-hash> -->` to digest blocks and skip markers already present. On any failure, persist the manifest and stop the remaining scope. `recover` only removes a source when the recorded destination exists with the expected hash; conflicts are reported without overwrite.

- [x] **Step 4: Run compact/recovery tests**

  Expected: all compact scopes remain data-preserving and repeated runs are idempotent; dry-run creates no manifest and changes no bytes.

### Task 5: Stable index snapshot and integrity validation

**Files:**
- Modify: `moss-mem/scripts/memory_manager.py` in `_build_index_payload`, `_write_index_files`, `_index_problem`, and `cmd_knowledge_index`.
- Test: `moss-mem/tests/test_memory_manager.py`.

**Interfaces:**
- `_build_index_payload() -> tuple[dict, list[str]]` remains compatible but internally validates pre/post source metadata and retries twice when sources change.
- Index payload gains `build_id: str`; Markdown header includes the same ID.
- `_index_problem` validates build ID parity, complete inverted-token coverage, and no orphan references.

- [x] **Step 1: Write failing index tests**

  Add tests for unique concurrent temp paths, build ID parity, missing inverted token detection, orphan reference detection, and a source mtime change during the first build causing one retry before publish.

- [x] **Step 2: Run focused index tests and verify failure**

  Expected: fixed `.tmp` paths race, the payload has no build ID, and incomplete inverted terms are accepted as fresh.

- [x] **Step 3: Implement snapshot and integrity checks**

  Use a source metadata snapshot before and after parsing, retry at most twice, and raise a clear `OSError`/`ValueError` while leaving the old index intact if unstable. Generate one build ID per payload, use PID/token-specific temp names, and extend `_index_problem` with deterministic token/reference checks.

- [x] **Step 4: Run index and search tests**

  Expected: existing corruption/fallback behavior remains unchanged and all new index contract tests pass.

### Task 6: Stale pointer and recovery diagnostics

**Files:**
- Modify: `moss-mem/scripts/memory_manager.py` in `cmd_show`, `cmd_knowledge_check`, `cmd_recover`, and init layout checks.
- Test: `moss-mem/tests/test_memory_manager.py`.

**Interfaces:**
- `knowledge-check --strict` reports a missing current task pointer as a layout error.
- `cmd_show` reports a concise stale-pointer error without traceback.
- `cmd_recover` reports stale pointer, stale/legacy lock state, and pending compact manifests.

- [x] **Step 1: Write failing diagnostics tests**

  Create a `MEMORY.md` pointing to a missing task, a legacy lock, and a pending manifest; assert each command reports the exact path and a next action while leaving unrelated files unchanged.

- [x] **Step 2: Run diagnostics tests and verify failure**

  Expected: current `show`/`state show` exits with a generic missing-file error and `knowledge-check` does not validate the pointer.

- [x] **Step 3: Implement diagnostics**

  Add pointer validation without guessing a replacement. Extend recover output with safe manifest reconciliation and explicit manual action for legacy locks. Ensure `knowledge-check --strict` retains existing missing-layout behavior.

- [x] **Step 4: Run diagnostics tests**

  Expected: stale states are actionable and no diagnostic command deletes a lock it does not own.

### Task 7: Full regression and handoff validation

**Files:**
- Modify: `moss-mem/tests/test_memory_manager.py` only if integration gaps remain.
- Verify: `moss-mem/scripts/memory_manager.py`, `MEMORY.md`, `.moss-mem/` runtime layout.

- [x] **Step 1: Run the complete test suite**

  Run: `python3 -m unittest discover -s moss-mem/tests -v`
  Expected: all tests pass with no traceback.

- [x] **Step 2: Run CLI smoke checks in a temporary project**

  Run `state init`, `state commit`, two `state note`, `summary-capture`, `knowledge-index`, `memory-search`, `state compact --dry-run`, and `knowledge-check --strict` in a temporary directory. Expected: no stale pointer, no lock residue, both notes searchable, and dry-run leaves source bytes unchanged.

- [x] **Step 3: Run targeted fault-injection checks**

  Re-run the manifest, unlink-failure, index replace-failure, and foreign-lock tests individually to make their failure evidence easy to review.

- [x] **Step 4: Inspect the diff boundary**

  Run `git status --short` and `git diff -- moss-mem/scripts/memory_manager.py moss-mem/tests/test_memory_manager.py docs/superpowers/specs/2026-11-11-moss-mem-p0-reliability-design.md docs/superpowers/plans/2026-11-11-moss-mem-p0-reliability-plan.md`. Confirm no unrelated deleted or untracked files were modified.

- [x] **Step 5: Update moss-mem handoff state**

  Use `python3 moss-mem/scripts/memory_manager.py state set` to record the verified P0 status, exact test command, remaining risks, and next step for P1 schema work. Do not commit or stage unrelated pre-existing changes.

## Execution Notes

- The plan is intentionally native/execution-oriented: tasks depend on the shared helper interfaces above, so implementation should proceed in order in the current session.
- Do not install packages or create a worktree that would hide the user's existing dirty workspace.
- Do not commit unless the user separately asks for a commit after reviewing the final diff.

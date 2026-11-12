# moss-mem P0 可靠性切片设计

## 意图

让 `moss-mem` 在多个 Agent、命令中断、同秒写入、压缩中途失败和索引重建时保持可恢复、可审计、无静默丢失。Markdown 继续是唯一事实源，Python 标准库继续是唯一运行时约束。

当前 P0 解决确定性一致性问题，不扩展到记忆语义、时间有效性或智能检索。

## 目标

- 所有写入动作使用同一套 owner-token 锁；只有实际持有锁的进程可以释放锁。
- `start/update/complete/add-note/init/summary-capture/compact/knowledge-index` 的写入边界一致；只读搜索不会碰锁。
- 任务、摘要和压缩生成的文件名在时间戳相同时仍唯一。
- Scratchpad 追加笔记，不覆盖已有笔记。
- `compact` 在部分完成、删除失败或进程中断后保留足够信息继续恢复，并且重复执行不会产生重复摘要。
- 索引发布只使用稳定的源文件快照；JSON 和 Markdown 索引使用同一 build ID，临时文件不互相覆盖。
- stale pointer、悬挂锁和未完成压缩都能被 `knowledge-check` / `recover` 明确报告。
- 为上述性质增加标准库测试，不安装新依赖。

## 非目标与反目标

- 不引入 SQLite、向量数据库、图数据库、外部记忆服务或第三方锁库。
- 不改变 `MEMORY.md`、任务文件、摘要文件的现有 Markdown 作为事实源的角色。
- 不自动压缩、不自动删除用户文件；增长提示仍然只是提示。
- 不在 P0 引入 `source/trust/valid_from/supersedes` 等 schema v2 字段。
- 不借机重构搜索排序、CLI 命令名称或无关 skill 文件。

## 约束

- Python 3.9+ 标准库；macOS、Linux、Windows 的路径和 UTF-8 行为保持兼容。
- 保留现有旧命令和 `state` 声明式 API。
- 现有 26 项测试必须继续通过。
- 工作区存在与本任务无关的删除和未跟踪文件，实施时只改 P0 相关文件。

## 方案比较

### A：最小外科修复

只修 owner-token 锁、Scratchpad 追加、文件名冲突，并补生命周期测试。改动小、回归面低，但 `summary-capture`、`compact`、`knowledge-index` 仍可能各自使用不同的并发边界，无法解决跨命令的一致性问题。

### B：完整可靠性切片（已选）

在 A 的基础上统一所有写操作的锁协议，给压缩增加轻量 journal/manifest 和幂等恢复，让索引构建检查源快照并使用唯一临时文件，再补并发、异常、回滚、stale pointer 和恢复测试。它覆盖同一根因的完整生命周期，改动集中在 `memory_manager.py` 与测试文件中。

### C：存储层重做

用 SQLite 或 journal 取代 Markdown 状态层。它能提供更强事务性，但会改变 source of truth、迁移方式和用户可见文件协议，超出 P0。

选择 B，因为当前风险集中在写入协议而不是检索能力；统一边界能用较小改动消除整类问题。

## 设计

### 1. Owner-token 锁

增加进程内 `_HELD_LOCK_TOKEN`。`acquire_lock()` 用 `O_CREAT|O_EXCL` 创建 JSON 锁，字段至少包含 `pid`、`token`、`created_at`、`command`。成功后只在进程内保存 token。

`release_lock()` 只有在当前进程持有 token、且磁盘锁的 token 与之匹配时才删除；没有成功 acquire 的进程、只读进程和旧格式锁都不能删除锁。`atexit` 和信号处理器复用同一安全释放函数。

`check_concurrent_edit()` 读取旧格式锁时继续给出兼容警告；新格式锁显示 PID、时间和命令，并尝试判断 PID 是否仍存活。它不自动删除存活锁。`recover` 只对明确 stale 的锁给出可执行修复提示，保留显式人工确认路径。

新增 `mutation_lock()` 上下文管理器，统一处理 acquire、异常释放和退出码。所有会修改事实源或生成索引文件的命令都使用它；`memory-search`、`show`、普通 `knowledge-check` 保持只读。

### 2. 唯一命名与 Scratchpad 追加

增加 `_unique_timestamped_path(directory, prefix, suffix)`：先使用现有时间戳格式，再在目标已存在时追加 `-2`、`-3` 等后缀。任务、摘要、归档任务和 active-task compact 都通过它生成路径。这样保留可读时间排序，也消除同秒覆盖。

`_memory_update()` 在 Scratchpad 区域保留已有非注释行，并将新笔记追加到末尾；`state update` 与 `state note` 都不再删除历史笔记。其他严格区块的替换语义保持不变。

### 3. 可恢复、幂等的 compact

live compact 在统一 mutation lock 内运行。执行前在 `.moss-mem/transactions/` 写一个唯一 manifest，记录 transaction ID、scope、strategy、源文件、目标文件、源 SHA-256 和每个条目的状态：`planned`、`written`、`source_removed`、`done`。

- 任务归档：先写并验证目标，再记录 `written`，最后删除源并记录 `source_removed`。源删除失败时保留 manifest 和源文件，重复恢复只执行缺失步骤；若目标已存在但内容 hash 不匹配，停止并报告冲突。
- archive 重写：继续使用原子替换，manifest 记录旧 hash 和新 hash；失败时原文件仍可读。
- summary digest：每个 topic block 写入稳定的 source marker。已存在 marker 的条目不会重复追加；只有确认 marker 已进入 digest 后才删除源。读取失败的源不进入删除集合。
- `scope=all` 共用一个 manifest。任一 scope 失败时停止后续 scope，报告已完成步骤和 transaction ID；`recover` 能列出未完成 manifest，并对 hash 一致的 `written` 项安全完成清理，对冲突项只报告不覆盖。

dry-run 不创建 manifest、不改文件、不改变字节。

### 4. 稳定索引快照

`knowledge-index` 使用 mutation lock，并在 `_build_index_payload()` 前后各取一次源文件路径与 `mtime_ns` 快照。两次不一致时丢弃本次 payload 并重试，最多两次；仍不稳定则失败且保留旧索引。

每次构建生成 `build_id`，同时写入 JSON 和 Markdown 索引。临时文件使用 `.<pid>.<token>.tmp` 唯一后缀；保留现有双文件回滚逻辑，失败时清理本次临时文件并恢复旧 pair。

索引校验增加：JSON/Markdown build ID 一致、每条记录的真实 token 都出现在倒排表、倒排引用无幽灵 ID。索引仍是可删除的派生缓存，源 Markdown 不受影响。

### 5. stale pointer 与恢复诊断

`knowledge-check --strict` 检查 `MEMORY.md` 当前指针是否存在；缺失时报告路径、当前状态和建议动作，但不猜测应指向哪个任务。`state show` 对 stale pointer 输出可读错误，不打印 traceback。`recover` 同时报告 stale pointer、悬挂 lock 和未完成 compact manifest。

## 文件与接口影响

- 修改：`moss-mem/scripts/memory_manager.py`、`moss-mem/tests/test_memory_manager.py`。
- 新增运行时目录：`.moss-mem/transactions/`；它属于 moss-mem，可安全清理已完成 manifest。
- 新增内部 helper：`mutation_lock`、唯一命名、manifest 读写/恢复、源快照校验。
- CLI 命令保持兼容；只增加恢复诊断信息和必要的 `recover` 行为，不删除旧参数。

## 验证标准

1. 非持有进程调用 `release_lock()` 不会删除别人的锁；持有者释放后锁消失。
2. 两个并发 `summary-capture` 或 `state note` 不覆盖内容，Scratchpad 两条都保留。
3. 固定时间戳下连续 `start`、`summary-capture`、archive/compact 仍生成不同文件。
4. summary 源读取失败时源文件保留；digest 重复执行不会重复 topic block。
5. compact 在目标写成功、源删除失败和进程中断模拟下可通过 manifest 恢复，不丢原文。
6. `scope=all` 中途失败不会静默执行后续 scope，恢复后可继续。
7. 索引源在构建中变化时重试；无法稳定时旧索引仍可用。
8. 损坏/过期/幽灵倒排引用会被识别并触发重建或明确失败。
9. stale pointer、悬挂锁和未完成 manifest 均能被 `knowledge-check --strict` 或 `recover` 指出。
10. `python3 -m unittest discover -s moss-mem/tests -v` 全部通过。

## 实施顺序

1. 先实现锁上下文、唯一命名和 Scratchpad 追加，并补其单元/CLI 测试。
2. 将 init、summary-capture、compact、knowledge-index 纳入统一锁，补并发测试。
3. 加入 compact manifest、幂等 digest 和 recover 诊断，补故障注入测试。
4. 加入索引 build ID、源快照重试、倒排完整性检查，补索引契约测试。
5. 运行完整测试与 `knowledge-check --strict`，检查工作区只包含 P0 相关变更。

## 留给实现者的判断

- token 使用 `secrets.token_hex`，hash 使用 `hashlib.sha256`，均为标准库。
- manifest 使用 JSON，写入采用现有原子写 helper；完成 manifest 可删除，未完成 manifest 永久保留直到恢复。
- 不为旧锁自动猜测所有权；旧锁只能在 `recover` 明确识别为 stale 后处理。

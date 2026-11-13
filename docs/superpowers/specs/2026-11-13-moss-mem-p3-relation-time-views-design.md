# moss-mem P3 关系与时间视图设计

> 状态：待用户批准
> 日期：2026-11-13
> 基线：P2 commit `11c872d`

## 意图

P1 已把 `supersedes`、`superseded_by`、`valid_from`、`valid_to` 和
`recorded_at` 纳入可验证 Schema；P2 又让检索结果可解释。当前仍缺少一个
只读入口来回答三个实际问题：某条记忆由什么演化而来、哪些记录替代了它、
以及在某个时间点它处于什么有效状态。

P3 增加确定性的关系与时间视图，不改变 Markdown 事实源、写入锁、索引格式
或检索排序。所有视图都从当前可重建索引计算，输出可用于审计、交接和故障
排查。

## 当前基线

- 索引 payload Schema 3 已保存每条 record 的 normalized metadata 和
  `superseded_by` 反向邻接表。
- `memory-search --as-of` 可以过滤半开 valid-time 区间，`--explain` 可以显示
  当前命中的 metadata，但不能独立查看一条记录的完整 lineage。
- `_supersession_chain()` 已有排序 BFS，但仅作为搜索结果附加输出，没有深度限制、
  时间状态和机器可读视图。

## 目标

1. 提供 `memory-explain MEMORY_ID`，展示记录正文摘要、normalized metadata、
   valid-time 状态、直接关系和限定深度的 lineage。
2. 提供 `memory-timeline`，按 valid-time/transaction-time 稳定排序查看一组记录，
   支持 source、as-of、from/to 和 superseded 过滤。
3. 提供 `--json` 机器可读输出，字段顺序和关系顺序稳定，便于脚本和交接工具消费。
4. 对 dangling reference、cycle、重复 ID 和未知 valid-time 保持 P1 的严格语义，
   不自动推断冲突、不删除旧记录、不修改源文件。

## 非目标与反目标

- 不改变 `MEMORY.md`、任务/摘要 Markdown 或 Schema 3 index payload。
- 不自动把相似文本判定为冲突，也不自动生成 `supersedes`。
- 不引入事件账本、向量图数据库、外部依赖或网络服务。
- 不把 unknown valid-time 当作 expired，也不把 superseded 记录从历史中删除。
- 不让关系分数影响 P2 的 lexical ranking。

## 备选方案

### A：只扩展 `memory-search --explain`

继续把关系和时间信息附在搜索结果上。改动最小，但无法解释一个没有命中 query
的 ID，也不适合查看完整链路或时间序列。

### B：独立只读关系/时间视图（选择）

增加 `memory-explain` 和 `memory-timeline` 两个只读命令，共享一个关系图和时间
分类 helper。它直接消费现有索引，输出 JSON/文本两种稳定格式，不影响写入和搜索
主路径，能逐步验证关系 UX。

### C：先引入 append-only 事件账本

从写入协议开始重建关系和时间历史。审计能力更强，但会引入迁移、重放和一致性
问题；P3 只读视图无法先验证用户真正需要的 lineage 形态，因此延后到 P4。

## 选定设计

### `memory-explain`

```bash
python3 {base}/scripts/memory_manager.py memory-explain mem_... \
  --depth 3 --as-of 2026-11-13T12:00:00Z --json
```

默认文本输出固定为：

1. `memory_id`、path、title、schema 和完整 normalized metadata；
2. `validity=active|upcoming|expired|unknown`；
3. `supersedes` 直接边；
4. `superseded-by` 直接边；
5. `ancestors`（被当前记录替代的多跳链）和 `descendants`（替代当前记录的多跳链），
   按 BFS 层级、每层按 `memory_id` 排序，超过 `--depth` 的节点不展开。

`--as-of` 使用已有半开谓词 `valid_from <= as_of < valid_to`；缺失一端表示开放区间，
两端都缺失为 `unknown`。不传 `--as-of` 时只输出 `validity=unknown`，不猜测当前
现实有效性。

`--depth` 默认 3，只接受整数 `0..64`；`0` 只返回当前 record 和 direct 边，
`ancestors`/`descendants` 数组为空。BFS 按层收集节点，每层按大小写敏感的
`memory_id` 排序后拼接；超过深度的节点不输出。方向固定：`ancestors` 沿当前
record 的 `supersedes` 目标前进（旧记录），`descendants` 沿 `superseded_by`
反向边前进（新记录）。例如 `C supersedes B` 且 `B supersedes A` 时，解释 C 得到
ancestors `B(depth=1), A(depth=2)`，解释 A 得到 descendants `B(depth=1), C(depth=2)`。

`--json` 返回一个对象：

```json
{
  "record": {"memory_id": "mem_...", "path": "...", "title": "...", "preview": "...", "schema_version": 2, "metadata": {}},
  "validity": "active",
  "direct": {"supersedes": [], "superseded_by": []},
  "lineage": {
    "ancestors": [{"memory_id": "mem_...", "depth": 1}],
    "descendants": []
  }
}
```

`preview` 使用索引已有的 240 字符上限；text/JSON 使用同一字段集合。stdout
始终只写一个 JSON 值，诊断和 rebuild 提示写 stderr。错误 JSON 统一为
`{"error":{"code":"unknown_id|index_unavailable|invalid_argument","message":"..."}}`；
未知 ID、索引一次重建仍失败、参数错误分别返回退出码 2、1、2。legacy virtual ID
（`legacy:<sha256>`）可查询，ID 大小写敏感。不扫描源文件之外的关系，也不修改索引。

### `memory-timeline`

```bash
python3 {base}/scripts/memory_manager.py memory-timeline \
  --source human:mt --from 2026-01-01T00:00:00Z \
  --to 2026-12-31T00:00:00Z --include-superseded --json
```

过滤语义：

- `--source` 先执行与 P1 相同的 trim，再进行大小写敏感精确匹配；
- `--as-of` 只保留该时刻 active 的 valid interval；
- `--from`/`--to` 选择与查询区间有交集的半开 interval，谓词为
  `[valid_from,valid_to) ∩ [from,to) ≠ ∅`；缺失左端视为 `-∞`，缺失右端视为 `+∞`。
  两端都缺失的 unknown 记录只有在未指定时间过滤时保留；`from == to` 或 `to < from`
  是 `invalid_argument`，单端查询按开放区间解释；
- 默认隐藏被 supersede 的记录，`--include-superseded` 显式恢复完整历史；
- `--limit` 默认 10，必须 `>=1`，在稳定排序后截断。

无 `--as-of` 时 timeline 的 `validity` 一律为 `unknown`，但保留原始区间并允许
返回所有记录；有 `--as-of` 时使用同一真值表：`as_of < valid_from` 为 `upcoming`，
`valid_from <= as_of < valid_to` 为 `active`，`as_of >= valid_to` 为 `expired`；
缺失一端分别表示没有 upcoming 或没有 expired 边界，两端都缺失为 `unknown`。时间
先 `_normalize_time` 到 UTC。JSON 顶层固定为 `{"records":[...]}`；每个 record 包含
`memory_id`、`path`、`title`、`preview`、`schema_version`、`metadata`、`validity`
和 `superseded_by`，空结果为 `{"records":[]}`。排序键固定为
`(valid_from_missing, valid_from_utc_or_empty, recorded_at_missing, recorded_at_utc_or_empty, memory_id)`，
缺失值最后；文本输出每行包含 validity、trust、source、memory_id 和 title。

### 共享关系与时间 helper

- `_build_lineage_view(payload, memory_id, depth) -> dict`：使用现有正向
  `metadata.supersedes` 和反向 `superseded_by`，visited set 防御性去重；索引构建
  已拒绝 cycle，因此运行时只需稳定 BFS。
- `_classify_validity(metadata, as_of) -> str`：返回 `active/upcoming/expired/unknown`，
  所有比较先用 `_normalize_time` 转 UTC。
- `_filter_timeline_records(records, source=None, as_of=None, valid_from=None,
  valid_to=None, include_superseded=False) -> list[dict]`：只做过滤，不改变 record。

两个新命令沿用搜索的恢复策略：载入索引失败或 stale 时最多执行一次
`knowledge-index`；重建仍失败则返回 `index_unavailable` JSON 错误，不进行不完整的
Markdown fallback，因为 lineage 需要完整快照。重建提示只写 stderr，`--json` stdout
保持可解析。默认隐藏依据为直接 `superseded_by` 非空；它与 valid-time 过滤独立，
不会因为某个时间点 active 就恢复被替代历史。

## 测试与验收

- lineage 测试覆盖单链、多 superseder、深度截断、未知 ID、稳定排序和 JSON/text parity。
- 时间测试覆盖开放区间、半开边界、upcoming/expired/active/unknown、跨时区和区间交集。
- timeline 测试覆盖 source、as-of、from/to、默认隐藏 superseded、limit 和 stable ID tie。
- CLI 测试覆盖缺失/损坏索引的一次重建、`--json` 可解析、错误退出码、源文件字节不变。
- 现有 P0/P1/P2 全部测试继续通过；不增加第三方包。

## P3 范围外

- append-only event ledger/materialized views（P4 候选）。
- 自动冲突检测、概率真值维护和自动 supersedes 推断。
- 向量图检索或跨项目关系合并。

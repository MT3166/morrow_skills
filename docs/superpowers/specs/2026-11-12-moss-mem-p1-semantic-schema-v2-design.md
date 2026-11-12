# moss-mem P1 语义 Schema v2 设计

## 意图

P0 已经保证 Markdown 写入、压缩恢复和本地索引发布的可靠性。P1 解决下一层问题：同一个主题可能有多个来源、不同时间范围和相互取代的结论，但当前记录只有自由文本，搜索无法解释“这条记忆为什么可信、何时有效、是否已经被新记录取代”。

P1 保留 `MEMORY.md`、任务文件和摘要文件作为唯一事实源，继续只使用 Python 标准库。Schema v2 是可选元数据层：旧文件继续可读，新写入逐步携带语义字段，索引和搜索可以利用这些字段而不要求一次性迁移全库。

## 目标

- 为任务和摘要提供可验证的来源、可信度、有效时间和稳定身份。
- 支持显式的 `supersedes` 关系，让新结论可以解释它替代的旧结论。
- 让本地索引保留这些字段，并提供按来源、可信度和有效时间过滤的搜索入口。
- 对 legacy 文件采用惰性兼容：不重写、不猜测来源、不把缺失元数据伪装成低可信度。
- 在 `knowledge-check --strict` 中发现非法字段、时间区间和悬挂关系。

## 非目标与反目标

- 不引入 SQLite、向量数据库、外部记忆服务或第三方 YAML/日期库。
- 不自动推断事实矛盾，不根据文本相似度自动覆盖或删除记忆。
- 不强制一次性给历史 Markdown 补字段，不改变用户可见的现有任务/摘要正文。
- 不在 P1 重做搜索引擎；排序改进只服务于元数据解释和明确过滤。
- 不把 `trust` 当作统计学概率，也不为不同来源凭空设定默认分数。

## 依据与取舍

- W3C PROV-DM 将 provenance 拆成 Entity、Activity、Agent；P1 采用同一分工的轻量投影：记录是 Entity，写入命令是 Activity，`source` 是 Agent/来源标识。见 [PROV-DM](https://www.w3.org/TR/prov-dm/)。
- 时间数据库区分“事实在现实中有效的 valid time”和“事实被记录的 transaction time”；P1 使用 `valid_from`/`valid_to` 表达前者，用自动生成的 `recorded_at` 表达后者。见 Jensen 与 Snodgrass 的 [Temporal Specialization and Generalization](https://www2.cs.arizona.edu/~rts/pubs/TKDEDec94.pdf)。
- Doyle 的 Truth Maintenance System 强调保留信念的理由并在冲突时修订依赖；P1 只采用可审计的显式 `supersedes` 边，不引入自动推理或依赖回溯。见 [A Truth Maintenance System](https://doi.org/10.1016/0004-3702(79)90008-0)。

## 方案比较

### A：语义 Schema v2（已选）

在现有 frontmatter 上增加少量可选字段，索引记录携带规范化 metadata，搜索提供显式过滤和解释。旧文件不变，新文件逐步获得稳定身份与 provenance。它直接解决“记忆是否仍有效、为什么相信、被什么替代”的问题，且不改变事实源。

### B：只升级检索排序

保持所有 Markdown 格式不变，加入 BM25 风格词频、时间衰减和更多字段权重。实现风险较低，但无法可靠区分来源与冲突；搜索质量提升不能替代事实生命周期。

### C：事件账本与物化视图

把每次写入记录为 append-only event，再生成 `MEMORY.md`、任务和索引视图。审计能力最强，但会改变当前 source-of-truth 协议并引入迁移、重放和视图一致性问题，超出 P1。

## Schema v2

### 文件级 frontmatter

新生成的任务和摘要使用以下可选字段；字段缺失表示未知，不表示不可信：

```yaml
schema_version: 2
memory_id: mem_0123456789abcdef0123456789abcdef
source: human:mt
trust: 0.0
recorded_at: 2026-11-12T10:30:00-08:00
valid_from: 2026-11-01T00:00:00-08:00
valid_to: 2026-12-01T00:00:00-08:00
supersedes: mem_abcdefabcdefabcdefabcdefabcdefab;mem_0123456789abcdef0123456789abcdef
```

字段契约：

- `schema_version`：整数 `2`。缺失或 `1` 的文件按 legacy 读取。
- `memory_id`：稳定的 `mem_` + 32 个小写十六进制字符，由 `secrets.token_hex(16)` 生成；创建时若发生碰撞必须重试。legacy 记录在索引中使用只读的 `legacy:<sha256(relative-path)>` 虚拟 ID，不回写源文件；legacy 文件改名后视为新的 legacy 记录。
- `source`：先去除首尾空白，禁止换行/回车，最多 160 个 Unicode code point，大小写敏感；例如 `human:mt`、`agent:codex`、`tool:ci` 或 `import:repo-x`。它是 provenance 标签，不是权限声明。
- `trust`：可选的有限十进制数，范围 `[0, 1]`，最多 6 位小数；不接受 NaN、Infinity 或指数形式，`-0` 规范化为 `0.0`。缺失保持 unknown；搜索的 `--min-trust` 使用包含边界，不会把 unknown 当作 0。
- `recorded_at`：写入时由 moss-mem 生成的、必须带时区的 ISO-8601 时间；只表达 transaction time，不代表事实发生时间。`Z` 规范化为 `+00:00`，比较时统一转 UTC。
- `valid_from` / `valid_to`：可选、必须带时区的 ISO-8601 时间区间，采用半开区间 `[valid_from, valid_to)`；缺失的一端表示开放区间。`valid_to <= valid_from` 为错误。`--as-of t` 的谓词是 `(valid_from is null or valid_from <= t) and (valid_to is null or t < valid_to)`。
- `supersedes`：以分号分隔的 `memory_id` 列表；解析时 trim、去重并按 ID 排序，空值等同于没有关系。只允许指向本次完整索引快照中已知的 ID；自身引用和环在严格检查中报错。

P1 不提供 `trust` 的自动校准。`source`、可信度和有效时间由写入者声明；系统负责格式校验、保留原值和在查询中透明呈现。

### Legacy 兼容

- `_parse_memory_record()` 保留未知 frontmatter 字段供原文重写，metadata 只规范化上述 v2 字段；系统不因索引而丢弃未知字段。
- legacy 记录继续参加默认搜索，`schema_version` 显示为 `1`，索引和 explain 输出使用统一的 metadata 对象：`{"source": null, "trust": null, "recorded_at": null, "valid_from": null, "valid_to": null, "supersedes": [], "legacy": true}`。
- `knowledge-index` 不修改源 Markdown；索引 payload 增加 `metadata` 与 `schema_version` 后，旧索引按 schema mismatch 重建。
- P1 不做全库自动迁移。未来若需要，可增加显式、可预览的 `state schema-migrate --dry-run`，但不作为本阶段前置条件。
- `schema_version` 缺失或整数 `1` 按 legacy；整数 `2` 按 v2；`0`、非整数、未知未来版本按 unsupported schema 处理，索引给出 warning，严格检查失败。

## 写入与命令行为

- `state start`、`summary-capture` 为新文件写入 `schema_version=2`、`memory_id`、`recorded_at`；`source` 默认使用调用方显式传入值，未传时省略，不猜来源。
- 现有 CLI 参数保持兼容；新增可选参数：`--source`、`--trust`、`--valid-from`、`--valid-to`、`--supersedes`。参数只影响新文件。
- `state update` 不会默默改变已有事实的有效时间或可信度；修改这些字段需要显式传参，并在任务文件的最后动作中留下可读记录。对 legacy 文件显式传入任一 v2 元数据时才升级为 v2，同时生成缺失的 `memory_id`/`recorded_at`；普通 update 保持 legacy。
- `supersedes` 只建立关系，不删除旧文件。索引从正向边派生 `superseded_by` 反向邻接表；多个新记录可指向同一旧记录，输出按 memory_id 排序，链路按层遍历并拒绝环。

## 索引与搜索

索引 payload 的 `schema_version` 升为 `2`，每条 record 增加：

```json
{
  "memory_id": "mem_0123456789abcdef0123456789abcdef",
  "schema_version": 2,
  "metadata": {
    "source": "human:mt",
    "trust": 0.9,
    "recorded_at": "...",
    "valid_from": "...",
    "valid_to": null,
    "supersedes": []
  }
}
```

legacy 记录使用与 explain 相同的全键 metadata（值为 `null`/`[]`，并带 `legacy: true`）和虚拟 ID。索引 payload 另存由正向边派生的 `superseded_by`，不把反向边重复写入每个源文件。`_index_problem()` 额外检查字段类型、时间区间、ID 唯一性、引用完整性和无环性。

summary digest 删除源文件时，在每个 topic block 后保留一行 JSON metadata marker：

```markdown
<!-- moss-mem-meta: {"memory_id":"mem_0123456789abcdef0123456789abcdef","schema_version":2,"source":"human:mt","trust":0.9,"recorded_at":"2026-11-12T10:30:00-08:00","valid_from":null,"valid_to":null,"supersedes":[]} -->
```

索引解析 digest block 时优先读取该 marker；没有 marker 的旧 digest 按 legacy 处理。这样 P0 的摘要压缩不会制造新的悬挂关系。

`memory-search` 新增：

- `--source VALUE`：只返回精确来源匹配。
- `--min-trust FLOAT`：只返回显式 trust 不低于阈值的记录；unknown 被排除并在输出中说明。
- `--as-of ISO_TIME`：按 valid-time 过滤；没有 valid 区间的 legacy/unknown 记录只在未指定该参数时返回。
- `--include-superseded`：默认结果仍包含被取代记录，但只增加一行 `superseded-by` 标签；指定后在 explain/结果中展开完整的直接与多跳关系上下文。P1 不默认隐藏或删除旧结果。
- `--explain`：输出命中原因、字段权重、metadata 状态和 supersedes 链，不引入不可复现的模型分数。

默认排序继续以词法相关性为主，metadata 只做确定性 tie-break：active valid-time > 已过期、显式 trust > unknown、未被 supersede > 已被 supersede，最终以 `memory_id` 排序；没有 `--as-of` 时不把未知 valid-time 当作过期。不得让低相关但高 trust 的记录压过精确命中。`--explain` 中的“字段权重”是固定的命中解释标签，不引入隐藏评分。

## 冲突与恢复

- 只有显式 `supersedes` 才表示版本关系；相同主题但没有关系的记录并列保留。
- `superseded_by` 是索引构建时从正向边派生的确定性映射；多个入边合法，环和自环非法。
- `knowledge-check --strict` 报告非法 trust、无法解析的时间、反向区间、重复 memory_id 和悬挂 supersedes。
- `memory-search --explain` 展示冲突链，但不自动选择“真相”。用户通过新增记录 supersede 旧记录完成修订。
- P0 的 lock、manifest、snapshot 机制继续承担写入和恢复安全；P1 不改变其事务协议。

## 验证标准

1. 旧格式任务/摘要无需迁移仍能索引和搜索，legacy metadata 在 JSON 和 explain 中形状一致。
2. 新建任务/摘要生成合法 `memory_id` 和 `recorded_at`，显式参数原样保留。
3. 非法 trust、时间区间、重复 ID、悬挂 supersedes 在严格检查中被拒绝。
4. `--source`（大小写敏感精确匹配）、`--min-trust`（包含边界）、`--as-of`（半开区间）、`--include-superseded` 结果稳定且可解释。
5. 同一主题的旧新记录不会被删除；supersedes 链可在搜索输出中追踪。
6. index JSON/Markdown 继续使用同一 build ID，并能从旧 schema 自动重建。
7. 全部现有测试继续通过，并新增 schema、迁移兼容、过滤和冲突链测试。

## P1 范围外的后续工作

- 语义矛盾自动检测、概率校准和多跳知识图谱。
- append-only 事件账本与完整历史重放。
- 向量检索或外部 embedding 服务。
- 面向自然语言的复杂时间查询语言。

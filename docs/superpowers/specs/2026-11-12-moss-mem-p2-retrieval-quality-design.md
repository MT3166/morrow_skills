# moss-mem P2 检索质量优先设计

> 状态：待用户批准
> 日期：2026-11-12
> 基线：P1 commit `fb097d4`（Semantic Schema v2）

## 意图

P1 让记录具备可验证的语义元数据，但当前 `memory-search` 仍主要使用
“词频 × 固定字段权重 + 短语加分”。它对短标题、长摘要、重复词和稀有词
的区分不够稳定，也无法解释一个词为什么把某条记录排在另一条前面。

P2 优先改善日常检索质量，同时保持 Markdown 事实源、stdlib-only 运行时和
P0/P1 的写入与恢复协议不变。目标是一个可重建、可解释、可回归测试的
BM25F 风格字段检索器，而不是引入向量数据库或黑盒模型。

## 当前基线

- 候选来自 `inverted_terms`；记录包含 title、sections、preview 和 P1 metadata。
- `_score_record()` 对每个字段按固定整数权重计词频，并对完整短语加固定 bonus。
- P1 metadata 只参与过滤和确定性 tie-break，不得把低词法相关性记录抬到精确命中之上。
- 索引 JSON/Markdown 可丢弃并重建，源 Markdown 不由索引写回。

## 目标

1. 使用 BM25F 风格的字段长度归一化和 IDF，降低长文重复词的误导。
2. 保留 title、Description、Summary、Decisions、Key Decisions、Next Step 等字段差异，
   让标题和决策字段的命中更有辨识度。
3. 让 `--explain` 展示每个 query term 的字段贡献、IDF、长度归一化、短语 bonus
   和最终排序 tie-break。
4. 保持旧 CLI positional 参数和默认结果格式可用，并提供 legacy scorer 回退开关。
5. 用仓库内的可审计 golden queries 验证 top-k 排序，避免“感觉更相关”的主观回归。

## 非目标与反目标

- 不引入 embedding、向量服务、第三方 Python 包或网络依赖。
- 不做学习排序、用户画像、自动 query expansion 或自动事实合并。
- 不把 trust、freshness 或 supersession 混进主词法分数；它们只能过滤或做已定义的 tie-break。
- 不修改 `MEMORY.md`、任务文件、摘要文件的事实内容，也不要求全库迁移。
- 不在 P2 同时重做 append-only 事件账本；那是独立的存储协议项目。

## 备选方案

### A：继续微调固定权重

只调整现有词频权重和短语 bonus。改动小、兼容风险低，但没有长度归一化、IDF
或可靠的解释基础，长记录和常见词问题仍会反复出现。

### B：BM25F 风格字段检索（选择）

在现有倒排候选上计算标准库实现的字段化 BM25：每个字段有固定 boost 和长度
归一化，term rarity 使用当前索引快照的 document frequency，短语 bonus 保持为
有界的附加项。主分数固定点量化为整数，保持 CLI 输出可比较；explain 输出未量化
的贡献。它不改变 Markdown 和写入协议，能用小型 golden set 验证。

### C：向量/语义检索

使用 embedding 或外部模型处理同义词和自然语言问题。语义覆盖更广，但引入模型
版本、缓存、网络/依赖和不可重复性，违反当前本地 stdlib-only 约束，也会把 P1 的
可审计排序变成黑盒，不适合作为 P2 第一切片。

## 选定设计

### 排分模型

采用 BM25F 的简化、固定参数版本。这里明确区分两个版本号：顶层
`index_schema_version`（索引格式，P2 为 3）与每条 record 的
`schema_version`（事实记录语义格式，P1 仍为 2）。为兼容 P1，P2 新索引必须
同时写入 `schema_version: 3` 和 `index_schema_version: 3`，两者不一致即视为
索引损坏；只含旧顶层 `schema_version: 2` 的 payload 判定为旧索引并重建。记录
对象只校验自己的 semantic `schema_version`（1 或 2），不与顶层版本比较。

对 query term `t` 和 record `d`，字段集合为 canonical field map 中的字段，
`tf(t,f,d)` 是该字段的 token 次数，`len(f,d)` 是同一 tokenizer 产生的 token
数，`avg_len(f)` 是当前完整索引快照中该字段的平均 token 数，定义为所有 record
（缺失字段按长度 0）之上的 `sum(len(f,d)) / N`。字段归一化为：

```text
field_tf(t,f,d) = boost(f) * tf(t,f,d)
                 / ((1-b) + b * len(f,d) / max(avg_len(f), 1))
norm_tf(t,d) = Σ field_tf(t,f,d)
term_score(t,d) = idf(t) * (k1 + 1) * norm_tf(t,d) / (k1 + norm_tf(t,d))
```

其中 `k1=1.2`、`b=0.75`，`idf(t)` 固定为
`max(1e-9, log1p((N-df(t)+0.5)/(df(t)+0.5)))`。`N` 是完整索引 record 数，
`df` 是包含该 term 的 record 数；候选过滤、source/trust/as-of 过滤都发生在
IDF 和平均长度统计之后。`N=0` 时没有候选也不计算分数；倒排候选中不可能出现
`df=0`，但实现仍返回 0，避免除零。

- `k1=1.2`、`b=0.75`；字段 boost 固定写在代码常量中，不暴露成运行时配置。
- canonical field map 固定为：`title=3.0`、`Description=2.0`、`Summary=2.0`、
  `Decisions=2.5`、`Key Decisions=2.5`、`Next Step=1.5`、`Related Files=1.0`、
  `Landmines=1.0`；大小写按现有 section 名精确匹配，未知 section 归入
  `__other__=0.5`。同名重复 section 按 Markdown 出现顺序，以单个 `\n` 拼接；
  空段贡献 0 token；frontmatter 的 `title` 只进入 title 字段，不与同名 section
  合并。
- 对完整 query phrase，在单个字段的 token 序列中按词序匹配；CJK 仍使用现有
  tokenizer，跨字段不算 phrase。只有 query 的所有唯一 term 都按原始 query 顺序
  出现时才计算 bonus；部分命中没有 bonus。`term_score_sum` 是所有 query term
  的未量化 `term_score` 之和，每条 record 只取命中字段中最高的一次：
  `phrase_bonus = min(0.25 * max(term_score_sum, 1), 2.0)`；没有 token 序列命中
  就输出 0。
- 内部保存非负 `score_raw`，并以 `score_milli = floor(score_raw * 1000 + 0.5)`
  量化为整数，采用 round-half-up；CLI 的 `score=` 输出 `score_milli`，结果对象
  同时保留这两个字段。排序先比较 `score_raw`；仅当差距小于 `1e-9` 时才比较
  `score_milli`，若仍相同则按 P1 的 validity、trust、superseded、`memory_id`
  顺序 tie-break，避免量化把低相关记录抬过精确命中。

索引 payload 升为 Schema 3，增加以下可重建的 `retrieval_stats`：

```json
{
  "scorer": "bm25f-v1",
  "doc_count": 42,
  "fields": {"title": {"avg_len_milli": 4250}, "Summary": {"avg_len_milli": 31000}},
  "doc_freq": {"cookie": 7},
  "stats_fingerprint": "sha256-of-canonical-stats-json"
}
```

`doc_count` 必须等于 record 数；`fields` 覆盖 canonical map 和 `__other__`，
`avg_len_milli` 是非负整数，表示平均 token 数乘 1000 后 round-half-up；
`doc_freq` 的 term 使用现有 tokenizer、按字典序序列化，并与倒排表中的 record
引用数一致。`stats_fingerprint` 对删除自身后的 stats 对象执行
`json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
allow_nan=False).encode("utf-8")` 后取 SHA-256，数值字段全部为整数，因此不存在
`4.25`/`4.250000` 差异。缺失、类型错误、指纹不匹配或从 records 重算不一致都
触发一次普通 `knowledge-index` 重建，不修改源文件。

### 查询与 CLI

- `memory-search QUERY` 默认使用 `bm25f`，保持现有 positional query 和
  `--limit N` option、metadata filters 和 result order contract；当前 CLI 没有
  未记录的 positional limit 形式，P2 不新增该兼容承诺。
- 新增 `--rank bm25f|legacy`，用于回归、故障回退和 A/B 对照；`legacy` 复用 P1
  之前的 scorer，不改变过滤和 relation context；默认值为 `bm25f`，非法值立即
  返回 usage error。
- `--explain` 对每条 record 先输出一行 `scorer=bm25f-v1`，再对每个 `tf>0` 的
  term-field pair 按 query 首次出现顺序、canonical field 顺序各输出一行；
  `length_norm` 是公式中的分母 `((1-b)+b*len/avg_len)`，不是其倒数。最后总是
  输出一行 phrase bonus（无匹配也输出 `0.000000`）和一行 tie-break：

  ```text
  term=cookie field=Summary tf=2 idf=1.609438 length_norm=0.812500 contribution=2.104321
  phrase_bonus=0.500000
  final_tiebreak=validity:active,trust:explicit,superseded:0,memory_id:mem_...
  ```

  浮点统一 6 位小数；无命中 term 输出 `term=<q> field=none tf=0 contribution=0.000000`，
  不输出隐藏模型状态。

### 评估与测试

- 新增 fixture `moss-mem/tests/fixtures/search-golden.json`，每项格式为
  `{"query": "...", "relevance": {"memory_id": grade}, "expected_bm25_top": [...],
  "expected_legacy_top": [...]}`；未列出的 ID 默认 grade 0，grade 越大越相关，
  同 grade 按 scorer 的稳定排序处理，expected 列表固定 top-k 断言。grade 为 0/1/2；
  record 使用固定合法 `mem_` ID，CJK query 明确写出期望 token。加入 20–30 条
  小型 golden query，覆盖精确短语、稀有词、长摘要、
  title/decision 字段冲突、CJK token、legacy/v2 混合和 metadata tie-break。
- fixture 的 `expected_legacy_top` 固定 P1 `legacy-v1` 的输出，commit `fb097d4` 只作
  provenance；对每条 query 断言 top-1/top-3、`--rank legacy` 回退和 explain 文本。
  实现一个轻量 MRR@k/NDCG@k helper，只用于测试，不增加运行时依赖；NDCG cutoff
  固定为 3，并列按 memory_id 稳定排序。
- 保留现有 P0/P1 故障注入测试，并增加 schema 3 stats 缺失、旧索引自动重建、
  scorer 参数边界和 explain 输出稳定性测试。

### 兼容与回滚

- Markdown、frontmatter、digest markers、P1 metadata 和 supersession graph 保持不变。
- Schema 2 index 自动重建为 Schema 3；旧 index 不被原地升级写回，直到正常重建完成。
- 若 BM25F 评分异常，`--rank legacy` 提供即时回退；`knowledge-index` 仍是唯一的
  索引修复入口。

## 参考理念

- Robertson、Walker、Beaulieu、Gatford、Payne 的
  [Okapi at TREC-3](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/okapi_trec3.pdf)
  提供 term rarity 与饱和词频的基础。
- Zaragoza、Robertson、Taylor 等的
  [BM25F fielded retrieval paper](https://www.microsoft.com/en-us/research/wp-content/uploads/2004/01/Microsoft-Cambridge-at-TREC-2004-Web-and-HARD-track.pdf)
  将字段结构和字段长度归一化纳入排序，适合 moss-mem 的 title/summary/decision
  多字段记录。
- P2 只采用这些模型的可解释、可重现部分；不引入论文中需要训练数据或线上反馈
  的部分。

## 验收标准

1. 相同 query 在相同索引快照上得到相同顺序和相同解释文本。
2. BM25F 在 golden set 的 top-k 指标不低于当前 scorer，且精确标题命中不会被低相关
   高 trust 记录压过。
3. `--rank legacy` 与 P1 scorer 结果一致；metadata filters 和 supersession explain
   行为不回归。
4. Schema 2/损坏 stats 能自动重建，Markdown 源文件字节不变。
5. 全部现有测试加新增检索测试通过，运行时仍只有 Python 标准库。

## P2 范围外

- append-only event ledger/materialized views。
- embedding、向量检索和外部 reranker。
- 自动事实冲突检测、概率校准和自动 supersedes 推断。

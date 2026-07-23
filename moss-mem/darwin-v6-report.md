# moss-mem Darwin 优化报告 · multi-scope MD lifecycle · 2026-07-23

## 总览

| 项 | 值 |
|----|----|
| Skill | moss-mem v6.0.1 |
| 分支 | `auto-optimize/20260723-md-lifecycle` |
| Baseline (v6 lens) | **69.6** |
| After Round 1 | **89.7** (+20.1) |
| After Round 2 | **89.7** (Δ0 hygiene) |
| 实验 | 1 score-keep / 1 hygiene / 0 revert |
| 实测 | unit full_test 26/26 + dim8 dry_run；prompts 7–8 PASS |
| runtime_warn | 0 |

## 分数变化

| Dimension | Baseline | R1 | R2 |
|-----------|---------:|---:|---:|
| 1 Frontmatter | 8 | 9 | 9 |
| 2 Workflow | 6 | 9 | 9 |
| 3 Failure modes | 7 | 9 | 9 |
| 4 Checkpoints | 8 | 9 | 9 |
| 5 Specificity | 8 | 9 | 9 |
| 6 Resources | 9 | 9 | 9 |
| 7 Architecture | 6 | 9 | 9 |
| 8 Real-world | 6 | 9 | 9 |
| 9 Blacklist | 9 | 10 | 10 |
| **Total** | **69.6** | **89.7** | **89.7** |

## 主要改进

1. **被动 nudge 扩层**：tasks>30 / archive>50 / summaries>30；触发点含 summary-capture
2. **主动 multi-scope compact**：`--scope tasks|archive|summaries|all`
3. **二次压缩策略**：archive 就地 summary；summaries → `digest-YYYY-MM.md`
4. **永不静默删除**：dry-run → 🛑/`--yes` → knowledge-index + memory-search 抽查
5. **Round 2 hygiene**：Quick Dispatch 补全 + defaults 表 + `--scope all` 集成测试

## 使用方式

```bash
# 预览
python3 {base}/scripts/memory_manager.py state compact --scope all --dry-run
# 确认执行
python3 {base}/scripts/memory_manager.py state compact --scope all --keep-recent 10 --yes
# 验证
python3 {base}/scripts/memory_manager.py knowledge-index
python3 {base}/scripts/memory_manager.py memory-search "关键决策词"
```

## HL-4

Round 1 Δ=+20.1；Round 2 Δ=0 → **触顶，停止再轮**。

## 待用户决定

- merge 分支到 main？
- 同步 `~/.agents/skills/moss-mem` 安装副本？

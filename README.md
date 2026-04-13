# morrow_skills

Claude Code 扩展技能仓库，通过 `/技能名` 方式为 Claude 提供专业化能力。

## 可用技能

### MOSS_MEM

项目记忆管理系统，实现跨会话上下文持久化。

**功能：**
- 初始化项目 MEMORY 系统
- 启动、更新、完成任务
- 维护 MEMORY.md 和 MEMORY_TASKS/ 目录
- 并发冲突检测

**触发词：**
- "initialize memory"、"update memory"、"start task"、"complete task"、"add note"

**命令示例：**
```
/MOSS_MEM init
/MOSS_MEM start -d "任务描述" -n "下一步指令"
/MOSS_MEM update -d "进度描述" -s "🔧"
/MOSS_MEM complete -d "完成描述"
```

## 目录结构

```
morrow_skills/
├── MOSS_MEM/           # MOSS_MEM 技能定义
│   ├── SKILL.md         # 技能说明文档
│   └── scripts/         # 核心脚本
├── MEMORY_TASKS/        # 任务文件目录
├── MEMORY.md            # 项目状态记忆文件
└── README.md
```

## MEMORY.md 格式

项目状态跟踪采用严格格式，核心区块：

- **Meta**：最后更新时间、项目画像、技术栈
- **状态机**：当前指针、全局目标、最后状态
- **下一步指令**：明确的可执行指令
- **暂存与备忘区**：自由记录复杂推理
- **雷区与技术契约**：已知约束和陷阱
- **已归档任务**：历史任务记录

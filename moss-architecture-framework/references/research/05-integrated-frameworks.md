# 融合性全流程框架调研：业务需求→技术分解→团队协同

**核心问题**：有没有一种框架可以贯穿「业务需求→技术分解→团队协同」全流程？

**结论**：不存在单一银弹框架，但存在可无缝衔接的框架组合。本文档分析各框架的**接口**（如何与其他框架衔接）及其适用规模/阶段。

---

## 1. Wardley Mapping

**定位**：战略层→战术层 的桥梁

### 核心概念

**Value Chain（价值链）**
- 横轴：用户需求 → 价值链活动 → 能力/组件
- 展示"价值如何流动"，识别瓶颈和机会

**Evolution（进化阶段）**
```
[发明] → [自定义构建] → [产品] → [商品化] → [Utility]
```
- **Genesis（发明）**：未知问题，未知解决方案
- **Custom Built（定制）**：已知问题，少数供应商
- **Product（产品）**：市场验证，竞争加剧
- **Commodity（商品）**：同质化，价格驱动
- **Utility（公用事业）**：按使用量计费

**Anchor Actions（锚定行动）**
- 强制性的、不可改变的约束条件
- 通常与法规、物理法则、核心业务选择相关

**接口**：

| 上游框架 | 接口 |
|----------|------|
| Business Model Canvas | 价值链直接映射 |
| Impact Mapping | Why层直接驱动Anchor定位 |

| 下游框架 | 接口 |
|----------|------|
| Shape Up | 进化阶段决定技术债容忍度 |
| Team Topologies | 进化阶段决定团队规模/专业度需求 |

**适用规模**：
- 战略层面：任何规模组织
- 战术层面：建议至少10人以上的多团队组织

**来源**：wardleymaps.com（Simon Wardley官方）

---

## 2. Shape Up

**定位**：产品层→执行层 的闭环方法论

### 核心概念

**Appetite（胃口）**
- 区别于"估算"：估算回答"需要多少时间"，Appetite回答"我们愿意花多少时间"
- **固定时间，弹性范围**：设定6周上限，范围围绕此调整

**Breadboarding（面包板）**
- 低保真UI原型，仅显示功能及其连接关系
- 用于快速验证技术可行性

**Circuit Diagrams（电路图）**
- 技术层面的组件连接图
- 展示：胖服务/瘦服务、数据库共享、同步/异步调用

**Scope Boxing（范围盒子）**
- 将范围装入固定时间盒的实践
- **Hill Chart**：可视化工作复杂性分布

**接口**：

| 上游框架 | 接口 |
|----------|------|
| Wardley Mapping | Evolution阶段决定技术风险 |
| Impact Mapping | 直接生成Pitch的Why层 |

| 下游框架 | 接口 |
|----------|------|
| Scrum/Kanban | 直接适配，Shape Up输出可直接进入Sprint |
| Team Topologies | 团队边界与Circuit Diagram对应 |

**适用规模**：
- 适合10-150人的产品团队
- 不适合需要长周期（>6周）的大规模项目

**来源**：basecamp.com/shapeup（Basecamp官方）

---

## 3. Impact Mapping

**定位**：业务目标→技术任务的追溯框架

### 核心概念

**四问结构**
```
Why (为什么) → What (做什么) → Who (谁做) → How (怎么做)
```

- **Why**：业务目标/预期影响（不是功能需求）
- **What**：交付物/功能（直接支持Why）
- **Who**：受益者/用户（不是开发者）
- **How**：假设/风险/里程碑

**接口**：

| 上游框架 | 接口 |
|----------|------|
| OKR | Goal层直接对应KR |
| Wardley Mapping | Impact层驱动Anchor定位 |

| 下游框架 | 接口 |
|----------|------|
| Story Splitting | Deliverable直接分割为User Story |
| Shape Up Pitch | 直接生成Shape Up Pitch的Problem Statement |

**适用规模**：
- 任何规模，但大型组织更需要
- 适合需要多团队协作的复杂交付

**来源**：impactmapping.org（Gojko Adzic官方）

---

## 4. Story Splitting

**定位**：Epic/Feature→User Story 的分解技术

### INVEST原则（Bill Wake提出）

| 字母 | 含义 | 检查问题 |
|------|------|----------|
| **I**ndependent | 独立的 | 能独立实现/测试吗？ |
| **N**egotiable | 可协商的 | 细节可以调整吗？ |
| **V**aluable | 有价值的 | 对用户有意义吗？ |
| **E**stimable | 可估算的 | 团队能估算工作量吗？ |
| **S**mall | 小的 | 1-3天能完成吗？ |
| **T**estable | 可测试的 | 能写验收标准吗？ |

### 分割模式

1. **沿数据边界分割**：同一实体的不同操作分割
2. **沿接口/seams分割**：API边界、模块边界
3. **沿用户角色分割**：Admin vs User vs Guest
4. **沿操作步骤分割**：订单流程：创建→审批→支付→发货
5. **沿业务规则分割**：普通用户 vs VIP用户
6. **沿数据类型分割**：主数据 vs 交易数据
7. **沿性能要求分割**：同步响应 vs 异步处理

**接口**：

| 上游框架 | 接口 |
|----------|------|
| Impact Mapping | Deliverable直接分割 |
| Story Map | 横向（工作流）→纵向（用户角色）双重分割 |

| 下游框架 | 接口 |
|----------|------|
| Scrum Sprint | 分割后的Story直接进入Sprint |
| Kanban | 分割后的Story进入WIP限制的列 |

**来源**：xp123.com（Bill Wake，INVEST原始提出者）

---

## 5. Agile Architecture

**定位**：架构决策与敏捷执行的融合

### 核心概念

**Evolutionary Design（演进式设计）**
- 不是"预先设计一切"，而是"持续重构"
- 架构在每个Sprint中演进

**Just-Enough Architecture（适度架构）**
- 不做过度设计
- 足够支持当前需求 + 适度未来扩展性

**Architecture Epic（架构Epic）**
- 跨越多个Sprint的大型技术Epic
- 与业务Epic并行，但独立追踪

**接口**：

| 上游框架 | 接口 |
|----------|------|
| Wardley Mapping | Evolution阶段决定架构债务容忍度 |
| Shape Up | Circuit Diagram直接映射为Architecture Epic |

| 下游框架 | 接口 |
|----------|------|
| Team Topologies | 架构决策决定平台/Enable team边界 |
| ADR | 架构决策记录为ADR |

**来源**：martinfowler.com - Agile Architecture

---

## 6. Team Topologies

### 四种团队类型

| Team Topologies | 核心职责 |
|-----------------|----------|
| Stream-aligned Team | 端到端价值交付 |
| Platform Team | 提供内部产品 |
| Enabling Team | 赋能+专业发展 |
| Complicated-subsystem Team | 专业子系统 |

### 三种交互模式

- **Collaboration**：共同发现新事物，有时间限制
- **X-as-a-Service**：一方提供、一方消费
- **Facilitation**：帮助和指导

**接口**：

| 上游框架 | 接口 |
|----------|------|
| Wardley Mapping | Evolution阶段决定是否需要Platform Team |
| Shape Up | Circuit Diagram决定服务边界→Team边界 |

| 下游框架 | 接口 |
|----------|------|
| Scrum/Kanban | Stream-aligned Team内实施 |
| ADR | Team API定义跨Team接口协议 |

**时效性**：第二版于2025年9月发布

**来源**：teamtopologies.com（Skelton & Pais官方）

---

## 7. 框架接口串联方案

### 核心接口矩阵

```
Impact Mapping输出
       ↓
   Deliverable
       ↓
Story Splitting (INVEST)
       ↓
    User Story
       ↓
Shape Up Pitch (Appetite约束)
       ↓
Circuit Diagram (技术分解)
       ↓
Team Topologies (团队边界)
       ↓
Stream-aligned Squad执行
```

### 推荐串联路径

**路径A：产品主导型（Shape Up + Impact Mapping）**
```
Impact Map → Shape Up Pitch → Breadboard/Circuit → Sprint
```
- 优点：快速闭环，用户价值导向
- 缺点：可能忽视长期架构健康度

**路径B：架构主导型（Wardley + Team Topologies）**
```
Wardley Map → Architecture Epic → Platform/Enable Team → Stream-aligned Team
```
- 优点：架构与技术债系统性管理
- 缺点：前期投入大，可能过度工程

**路径C：平衡型（推荐大多数组织）**
```
Impact Map → Shape Up Pitch → 
   ├─ Wardley Map (关键决策点) → ADR
   └─ Circuit Diagram → Team Topologies → Sprint
```

---

## 8. 框架选择指南

### 按项目规模

| 规模 | 推荐组合 | 不推荐 |
|------|----------|--------|
| **初创/小型** (<10人) | Shape Up + Story Splitting | Spotify Model（过度复杂）|
| **成长型** (10-50人) | Shape Up + Impact Mapping + Team Topologies Stream-aligned | Wardley（战略层投入不足）|
| **中型** (50-150人) | 全框架组合 | — |
| **大型** (150+人) | Wardley + Spotify + Team Topologies | 纯Shape Up（协调不足）|

### 按项目阶段

| 阶段 | 推荐框架 | 重点 |
|------|----------|------|
| **探索期** | Impact Mapping | 验证Why |
| **成形期** | Shape Up Pitch | 约束范围 |
| **交付期** | Story Splitting + Sprint | 执行 |
| **演进期** | Wardley + ADR | 技术债务管理 |

---

## 核心结论

### Q: 有没有一种框架可以贯穿全流程？

**没有单一框架可以贯穿**，但存在**最小必要组合**：

```
Impact Mapping (WHY层)
       ↓
Story Splitting (WHAT层)
       ↓
Team Topologies (WHO层)
       ↓
Shape Up (HOW层)
```

### 各框架的最佳拍档

| 框架 | 最佳拍档 | 理由 |
|------|----------|------|
| Wardley Mapping | Team Topologies | Evolution阶段决定团队类型 |
| Impact Mapping | Shape Up | Impact直接生成Pitch |
| Shape Up | Story Splitting | Appetite约束促进Story细分 |
| Story Splitting | Scrum/Kanban | Story是Sprint的基础单位 |
| Spotify Model | Team Topologies | Squad ≈ Stream-aligned Team |

---

## 信息源

- [Wardley Maps](https://wardleymaps.com/) — Simon Wardley官方
- [Basecamp Shape Up](https://basecamp.com/shapeup) — Basecamp官方
- [Impact Mapping](https://impactmapping.org/) — Gojko Adzic官方
- [Team Topologies](https://teamtopologies.com/) — Skelton & Pais官方，2025年第二版
- [Martin Fowler](https://martinfowler.com/) — 业界权威
- xp123.com (Bill Wake) — INVEST原始提出者

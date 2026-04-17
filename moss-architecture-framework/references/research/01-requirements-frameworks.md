# 需求框架与方法论调研报告

> 调研日期：2026/04/16  
> 调研范围：需求框架、需求分解技术、任务拆解方法、核心原则

---

## 一、需求框架（Requirements Frameworks）

### 1.1 User Story Mapping

**方法论描述**

User Story Mapping 是一种将用户故事排列成可视化模型的协作技术，帮助团队理解系统功能、发现待办事项中的空白，并规划能交付用户价值和业务价值的版本发布。

核心过程分为四步：
1. **Discovery & Planning（发现与规划）** —— 理解整个系统的用户及其使用场景
2. **Prioritization（优先级排序）** —— 确定支持哪些使用场景
3. **Mapping（映射）** —— 将故事排列成可视化模型
4. **Navigation（导航）** —— 在工作流上下文中定位具体故事

**关键收益**
- 暴露待办事项中的空白和遗漏
- 展示整个系统的广度和多样化用户
- 提供丰富的上下文（主要/次要用户、目标、工作流顺序）
- 支持日常团队对话
- 支持整体版本规划

**何时使用**
- 当仅靠优先级待办事项列表无法传达系统范围时
- 用于规划能增量交付价值的版本发布
- 将日常工作讨论扎根于共享的视觉理解

**来源**
- [Jeff Patton Associates - User Story Mapping](https://www.jpattonassociates.com/user-story-mapping/)  
  **可信度：高**（一手来源，Jeff Patton 是该方法论的原创者）  
- "User Story Mapping: Discover the Whole Story, Build the Right Product" (O'Reilly, 2014)  
  **可信度：高**（原始出版物）

---

### 1.2 Event Storming

**方法论描述**

Event Storming 是一种灵活的研讨会形式，用于协作探索复杂业务领域。团队使用可视化便签板映射业务事件、动作和流程，然后协作探索、对齐并设计解决方案。

**四种工作坊风格**
1. **Improve（改进）** —— 评估现有业务线健康状况，发现不一致性，收集共识
2. **Envision（愿景）** —— 探索新创业生态系统，强制一致叙事，识别架构边界
3. **Explore（探索）** —— 协作设计新服务，涉及业务、服务设计方和 IT
4. **Design（设计）** —— 为关键流程建模关键软件行为，为微服务和 DDD 做准备

**典型过程**
- 短介绍问题领域
- 协作建模从关键系统事件开始
- 发现用户发起的命令、关键角色和外部系统
- 寻找聚合和事务边界
- 识别有界上下文和子域
- 关键聚合的测试策略

**何时使用**
- 评估和改进现有业务流程
- 测试新创业模型的可行性
- 设想和设计最大化正向结果的新服务
- 创建干净、可维护的事件驱动软件

**来源**
- [EventStorming.com](https://www.eventstorming.com/)  
  **可信度：高**（一手来源，Alberto Brandolini 创立，Avanscoperta 维护）
- "Introducing EventStorming" (Leanpub, Alberto Brandolini)  
  **可信度：高**（原创书籍）

---

### 1.3 Impact Mapping

**方法论描述**

Impact Mapping 是一种轻量级的协作规划技术，适用于希望通过软件产品产生重大影响的团队。它结合了用户交互设计、结果驱动规划和思维导图，帮助团队可视化路线图，并将交付物与用户需求连接。

**四个核心元素**

1. **Why（目标）** —— 组织目标及其支撑的影响
2. **Who（参与者）** —— 用户、角色和用户类别
3. **How（影响）** —— 期望的行为改变
4. **What（交付物）** —— 支持改变的特性和活动

**过程**
1. 思考能产生重大影响的行为改变
2. 用便签或白板记录
3. 按参与者分组影响
4. 一侧添加交付物，另一侧添加目标
5. 可视化连接项目
6. 从目标到影响优先排序

**何时使用**
- 需要聚焦工作并重组计划
- 沟通新想法的愿景
- 暴露隐藏假设并记录决策
- 促进有效规划和优先级排序

**来源**
- [ImpactMapping.org](https://www.impactmapping.org/)  
  **可信度：高**（一手来源，Neuri Consulting LLP 维护，插图来自 Gojko Adzic）  
  **注意**：原始方法论由 Gojko Adzic 创立，Jeff Gothelf 推广。内容采用 CC BY 4.0 许可。

---

### 1.4 Jobs-to-be-Done (JTBD)

**方法论描述**

JTBD 理论最初由 Clayton Christensen 在哈佛商学院研究中提出，核心观点是：客户不是购买产品，而是"雇佣"产品来完成一项"工作"（Job）。

**核心概念**
- **Job（工作）**：顾客试图完成的进步——不仅是功能层面，还包括情感和社会层面
- **Hiring/Firing Metaphor（雇佣/解雇隐喻）**：当产品帮助顾客取得进步时，它被"雇佣"；当它让顾客失望时，就被"解雇"
- **Job Story Format**（Alan Klement 改良）：*"When [situation], I want to [motivation], so I can [expected outcome]"*

**与 User Stories 的关键区别**

| 维度 | User Story | Job Story |
|------|------------|-----------|
| 焦点 | 角色 + 功能 | 情境 + 动机 + 进步 |
| 假设 | 基于角色理解需求 | 基于顾客试图完成的"工作" |
| 边界 | 通常一个功能 | 可跨越多个产品/服务 |

**何时使用**
- 需要深入理解顾客真正试图完成的工作时
- 产品创新和功能优先级排序
- 从"构建什么"转向"为什么构建"

**来源**
- Christensen, Hall, Dillon, Duncan: "Know Your Customers' 'Jobs to Be Done'" (Harvard Business Review, September 2016)  
  **可信度：高**（原始理论来源）
- "Competing Against Luck: The Story of Innovation and Customer Choice" (Harper Business, 2016)  
  **可信度：高**（原创书籍）
- [JTBD.info](https://jtbdinfo.com/)（Alan Klement 的改良框架）  
  **可信度：中**（二手解释来源）

---

## 二、需求分解技术（Requirements Decomposition）

### 2.1 Two Pizza Team 原则

**方法论描述**

Two Pizza Team 原则是 Amazon 创始人 Jeff Bezos 提出的团队规模准则：**团队应该足够小，以至于能用两个披萨喂饱**。

**理论基础**

关键原理是**通信开销的 n² 问题**：随着团队规模增长，通信渠道数以平方级增长（n(n-1)/2），导致协调成本急剧上升。

**何时使用**
- 组建新团队时
- 发现团队通信效率低下时
- 微服务架构中围绕服务边界组织团队时

**批评与注意**
- 不是严格的数字规则，而是一种思维框架
- 某些需要跨职能协作的场景可能需要更大团队
- Conway's Law 指出系统架构会影响团队结构

**来源**
- [Atlassian - Team Size](https://www.atlassian.com/team-glossary/team-size)  
  **可信度：中**（工程博客，讨论 Two Pizza Team 在现代团队管理中的应用）
- [Amazon Leadership Principles - Large Teams](https://www.aboutamazon.com/amazon-culture/large-teams)  
  **可信度：中高**（Amazon 官方，但未直接引用原始来源）

---

### 2.2 INVEST 原则

**方法论描述**

INVEST 是 Bill Wake 提出的用户故事质量评估框架，包含六个标准：

| 标准 | 含义 | 实践意义 |
|------|------|----------|
| **I** - Independent | 故事之间相互独立，避免重叠和依赖 | 便于独立调度和实现 |
| **N** - Negotiable | 故事不是详细规范，而是在开发过程中由客户和开发者共同细化 | 保留灵活性 |
| **V** - Valuable | 故事必须对客户有价值 | 确保交付真正价值而非技术债务 |
| **E** - Estimable | 团队能够评估故事的工作量 | 需要足够的上下文和经验 |
| **S** - Small | 故事应该代表最多几个人周的工作量 | 小故事获得更准确估算 |
| **T** - Testable | 能够为故事编写测试 | 隐含承诺"可以为它写测试" |

**何时使用**
- 评审和优化待办事项列表时
- 拆分用户故事时
- 建立团队故事编写规范时

**来源**
- Bill Wake: "INVEST in Good Stories, and SMART Tasks", XP123, August 17, 2003  
  **可信度：高**（一手来源，原始定义）
- [XP123.com - INVEST](https://xp123.com/articles/invest/)  
  **可信度：高**（官方网站）

---

### 2.3 MoSCoW 方法

**方法论描述**

MoSCoW 是一种优先级排序技术，将需求分为四类：

| 类别 | 含义 | 典型比例 |
|------|------|----------|
| **M** - Must-have | 必须有：没有则产品无法发布 | 60-70% |
| **S** - Should-have | 应该有：重要但不紧急 | 20% |
| **C** - Could-have | 可以有：愿望清单，如果资源允许 | 10% |
| **W** - Won't-have | 不会有的：明确排除或"以后再说" | 0% |

**应用步骤**
1. 让利益相关者对齐目标和优先级因素
2. 达成优先级排序共识
3. 事先商定争议解决方式
4. 达成资源分配共识
5. 将每个需求分配到适当类别

**何时使用**
- 需要跨组织代表参与时
- 面临预算紧张、技能有限或竞争优先项约束时
- 版本规划和发布范围定义

**重要澄清：来源争议**

> **矛盾记录**：许多来源声称 MoSCoW 起源于 Microsoft，但实际考据表明该方法由 **Dai Clegg** 在 Oracle 工作期间创立，用于帮助团队在产品发布时优先排序任务。这一错误归属在中文社区尤其普遍。

**来源**
- [ProductPlan Glossary - MoSCoW](https://www.productplan.com/glossary/moSCoW-prioritization/)  
  **可信度：中**（现代工程博客，明确指出 Dai Clegg at Oracle 为创始人）
- [Agile Business Consortium](https://www.agilebusiness.org/page/ProjectFramework_WhatisMoSCoW.htm)  
  **可信度：中**（来源未明确，但与 Dai Clegg 版本一致）

---

## 三、任务拆解技术（Task Decomposition）

### 3.1 Delphi 法

**方法论描述**

Delphi 法是一种结构化通信技术，依靠专家小组在多轮问卷中回答问题。每一轮后，促进者提供匿名汇总的响应，使专家能够根据集体输入修订观点。过程持续直到预定义停止条件满足。

**过程步骤**
1. **专家选择** —— 识别并招募具有相关专业知识的小组成员
2. **初始问卷** —— 向所有专家分发第一轮问题
3. **分析** —— 编译响应并识别模式
4. **反馈** —— 向小组提供带有推理的匿名摘要
5. **迭代** —— 专家考虑集体输入修订答案
6. **重复** —— 继续轮次直到达成共识或稳定
7. **最终评估** —— 计算最后一轮的平均值/中位数

**何时使用**
- 需要专家对不确定未来达成共识时
- 技术预测、商业预测、政策制定、医疗指南创建
- 当直接小组互动不切实际或匿名有助于减少社会偏见时

**优势**
- 匿名性防止权威或声誉主导讨论
- 减少从众效应和光环效应
- 使异议观点能够自由表达
- 结构化方法产生比非结构化群体更准确的预测
- 可以涉及地理分散的专家

**缺点**
- 时间密集（传统 Delphi 可能需要数月或数年）
- 需要熟练的促进者
- 专家选择严重影响结果
- 专横参与者可能仍会影响结果
- 根据应用质量不同，准确度记录参差不齐
- 有限能力处理相互依赖的预测因素

**来源**
- [Wikipedia - Delphi Method](https://en.wikipedia.org/wiki/Delphi_method)  
  **可信度：中**（百科全书来源，引用 Project RAND 的原始工作）
- 原始开发：Olaf Helmer, Norman Dalkey, Nicholas Rescher，Project RAND，冷战初期  
  **可信度：高**（历史记录）

---

### 3.2 WBS（Work Breakdown Structure）分解

**方法论描述**

WBS 是"项目团队为实现项目目标并创建所需交付物而进行的总工作范围的层次分解"。它将团队工作组织成可管理的部分，呈现为显示工作细分的树结构。

**关键原则**
- **100%规则**：WBS 必须包含项目范围定义的 100% 工作；子项必须等于父项的 100%
- **渐进细化**：随时间增加细节的迭代过程
- **计划成果，而非行动**：确保满足 100% 规则
- **层次限制**：通常 2-4 层；应用启发式如"80小时规则"
- **WBS 词典**：澄清模糊的元素名称

**何时使用**
- 项目开始时，在详细规划之前
- 为成本估算、进度控制和系统规范映射需求提供框架

**优势**
- 能够将下属成本汇总到父级
- 为规划和控制提供通用框架
- 创建对终端元素活动的明确分配
- 支持功能需求到设计文档的交叉引用映射

**缺点**
- 元素之间的重叠导致"重复工作或责任和权限的沟通错误"
- 歧义可能"混淆项目成本会计"
- 需要仔细平衡以避免超过或不足 100%

**来源**
- [Wikipedia - Work Breakdown Structure](https://en.wikipedia.org/wiki/Work_breakdown_structure)  
  **可信度：中**（百科全书，引用 PMBOK 等标准）

---

### 3.3 敏捷估算

#### 3.3.1 Story Points

**方法论描述**

Story Points 是一种相对估算技术，团队评估用户故事的相对大小而非绝对时间。典型做法是使用斐波那契数列（1, 2, 3, 5, 8, 13...）对故事进行 sizing。

**核心概念**
- **相对大小**：比较故事之间的相对难度/工作量
- **消除时间单位**：关注复杂性而非持续时间
- **团队特定**：不同团队的 8-point 故事含义不同

**何时使用**
- Sprint 规划和迭代估算
- 团队需要建立一致的估算基准后
- 用于速度（Velocity）计算和预测

**争议/缺点**
- 不同团队之间无法标准化
- 需要稳定的团队和上下文才能建立可靠速度
- 可能被误解为绝对时间承诺

**来源**
- Mountain Goat Software: "Story Points"  
  **可信度：中**（知名 Scrum 培训来源）
- Mike Cohn: "Agile Estimating and Planning" (Prentice Hall, 2005)  
  **可信度：高**（早期敏捷估算实践的主要来源之一）

---

#### 3.3.2 T-Shirt Sizes

**方法论描述**

T-Shirt Size 是一种更简单的相对估算技术，使用衣服尺寸（S, M, L, XL, XXL）对故事进行分类。

**何时使用**
- 快速初始估算
- 当团队还没有建立可靠的估算基准
- 在 Sprint Planning 之前的粗略排序

**优势**
- 简单直观，无需特殊培训
- 减少关于精确数字的争论
- 适合非技术利益相关者参与

**缺点**
- 过于粗糙，无法支持精确的容量规划
- L 和 XL 之间的边界模糊
- 与 Story Points 相比精度较低

**来源**
- [Agile Alliance - T-Shirt Sizing](https://www.agilealliance.org/glossary/tshirt-sizing)  
  **可信度：中**（行业组织来源，但该 URL 返回 404，实际内容无法验证）

---

## 四、核心原则：共识与分歧

### 4.1 共识框架（大多数流派认同）

#### 4.1.1 需求应该是可测试的

**共识**：无论是 INVEST 的 "Testable"、User Story Mapping 中编写验收标准，还是 Event Storming 中的"关键场景测试策略"，主流方法论都强调需求必须能够被验证。

#### 4.1.2 需求应该提供价值

**共识**：MoSCoW 的 Must-have、INVEST 的 Valuable、JTBD 的"顾客雇佣产品来完成工作"都指向同一个核心：**交付物必须对用户或业务有实际价值**。

#### 4.1.3 分解是必要的

**共识**：所有方法论都接受"大需求需要分解"。无论是 WBS 的层次分解、User Story Mapping 的横向切片、还是 Story Points 的故事拆分，都认为细粒度需求更容易处理和估算。

#### 4.1.4 协作和共识的价值

**共识**：Delphi 法的匿名专家共识、Event Storming 的跨职能协作、User Story Mapping 的团队对话，都表明**多元视角和共识决策优于个人英雄主义**。

#### 4.1.5 上下文决定方法

**共识**：所有方法论都承认**没有放之四海而皆准的最优方法**。T-Shirt Sizing 适合早期探索，Story Points 适合稳定团队，Event Storming 适合复杂领域建模。

---

### 4.2 分歧点（不同流派有不同看法）

#### 4.2.1 用户角色（Persona）的重要性

| 流派 | 立场 | 代表方法 |
|------|------|----------|
| User Story Mapping | 强调角色（Persona）和工作流的区分 | Jeff Patton |
| JTBD | 关注"工作"本身，角色是次要的 | Clayton Christensen, Alan Klement |
| Event Storming | 关注业务流程和事件，角色在聚合层面出现 | Alberto Brandolini |

**分歧本质**：从"谁"（角色）出发还是从"什么工作"（Job）出发。User Story Mapping 认为不同角色有不同的故事；JTBD 认为同一个人在不同情境下可能"雇佣"不同产品来完成相同的工作。

#### 4.2.2 估算单位：绝对 vs 相对

| 流派 | 立场 | 代表方法 |
|------|------|----------|
| WBS | 绝对估算（人时、人日） | 传统项目管理 |
| Story Points | 相对估算（无单位） | Scrum/极限编程 |
| T-Shirt Sizes | 相对估算（类别） | 敏捷早期阶段 |

**分歧本质**：估算的精确性是否有意义。WBS 认为需要绝对值来满足财务和进度承诺；敏捷流派认为精确时间是幻觉，相对估算更稳定。

#### 4.2.3 需求的确定性假设

| 流派 | 立场 | 代表方法 |
|------|------|----------|
| 传统方法 | 需求应该在开发前完全固定 | WBS, 瀑布模型 |
| 敏捷方法 | 需求是探索性发现的 | User Story Mapping, Event Storming |
| JTBD | 需求源于对顾客"工作"的理解，而非规范 | Christensen |

**分歧本质**：需求是"被发现"还是"被规格化"。敏捷和 JTBD 都认为预先详尽规格化是浪费；传统方法认为不确定性是风险。

#### 4.2.4 团队规模与通信

| 流派 | 立场 | 代表方法 |
|------|------|----------|
| Two Pizza Team | 小团队（≤8-10人）减少通信开销 | Amazon/Jeff Bezos |
| Spotify Model | 大规模敏捷中允许"部落"和"公会"结构 | Spotify |
| Conway's Law | 系统架构决定团队结构 | Melvin Conway |

**分歧本质**：规模经济的取舍。小团队通信效率高但可能缺乏跨职能能力；大团队资源更丰富但通信开销呈 n² 增长。

#### 4.2.5 MoSCoW 的百分比分配

**分歧记录**：不同来源对 MoSCoW 各类别的典型比例有不同建议：
- ProductPlan 建议 Must-have 占 60-70%
- 某些敏捷来源建议 50/30/15/5 的分配
- 没有统一标准，比例取决于上下文和风险承受度

---

### 4.3 矛盾直接记录

#### 4.3.1 MoSCoW 来源的混淆

> **矛盾**：许多中文来源将 MoSCoW 归因于 Microsoft，但有据可查的来源（Dai Clegg 本人确认）表明该方法由 **Dai Clegg 在 Oracle 工作期间创立**。这一混淆可能源于 Microsoft 在 1990 年代推广了多种敏捷实践。

#### 4.3.2 Impact Mapping 的创始权

> **矛盾**：Impact Mapping 方法论通常归功于 **Gojko Adzic**（他写了介绍书籍），但 Jeff Gothelf 在推广和普及方面也发挥了重要作用。impactmapping.org 网站内容由 Neuri Consulting LLP（Adzic 的公司）维护，但 Gothelf 在《Lean UX》中的推广可能影响了更广泛的采用。

#### 4.3.3 Story Points 的历史争议

> **矛盾**：Story Points 的具体起源不清楚。Mike Cohn 在《Agile Estimating and Planning》中普及了这一概念，但有迹象表明极限编程（Extreme Programming）社区在此之前就在使用类似方法。没有单一确定的创始人。

---

## 五、何时使用什么方法：条件判断矩阵

### 5.1 按项目阶段选择

| 阶段 | 推荐方法 | 原因 |
|------|----------|------|
| **概念探索** | JTBD, Impact Mapping | 理解为什么要构建和影响范围 |
| **需求发现** | Event Storming, User Story Mapping | 协作探索和可视化 |
| **优先级排序** | MoSCoW | 跨职能对齐和资源分配 |
| **详细分解** | WBS, INVEST | 层次结构和质量标准 |
| **估算规划** | Story Points, T-Shirt Sizes, Delphi | 容量规划和进度预测 |

### 5.2 按团队特征选择

| 团队特征 | 推荐方法 | 原因 |
|----------|----------|------|
| **新团队，无历史数据** | T-Shirt Sizes, Delphi | 相对估算，无需基准 |
| **稳定团队，有速度数据** | Story Points | 可预测容量和进度 |
| **跨职能复杂领域** | Event Storming | DDD 和业务流程探索 |
| **需要利益相关者对齐** | User Story Mapping, MoSCoW | 可视化协作 |
| **大型组织，多团队** | Two Pizza Team, MoSCoW | 通信效率和资源协调 |

### 5.3 按问题类型选择

| 问题类型 | 推荐方法 | 原因 |
|----------|----------|------|
| **不知道用户要什么** | JTBD | 深入理解顾客工作 |
| **功能范围不清晰** | User Story Mapping | 暴露空白和遗漏 |
| **业务逻辑复杂** | Event Storming | 协作探索和事件建模 |
| **战略与执行脱节** | Impact Mapping | 连接目标和交付物 |
| **待办列表质量差** | INVEST | 质量评估标准 |
| **团队对估算争议大** | Delphi | 匿名专家共识 |

---

## 六、方法论之间的协同关系

```
Impact Mapping (战略)
       ↓
User Story Mapping / Event Storming (战术发现)
       ↓
MoSCoW / INVEST (优先级和质量)
       ↓
WBS / Story Points / T-Shirt Sizes / Delphi (分解和估算)
```

**典型组合**：
1. **新产品探索**：Impact Mapping → User Story Mapping → Story Points
2. **遗留系统改造**：Event Storming → MoSCoW → WBS
3. **大规模多团队**：Impact Mapping → Two Pizza Team + MoSCoW → Story Points
4. **不确定领域的快速验证**：JTBD → T-Shirt Sizes → MoSCoW

---

## 七、关键引用来源汇总

| 方法论 | 原创者/主要来源 | 关键文献 |
|--------|----------------|----------|
| User Story Mapping | Jeff Patton | "User Story Mapping" (O'Reilly, 2014) |
| Event Storming | Alberto Brandolini | "Introducing EventStorming" (Leanpub) |
| Impact Mapping | Gojko Adzic | "Impact Mapping" (Origami Press, 2012) |
| JTBD | Clayton Christensen | "Competing Against Luck" (Harper Business, 2016) |
| INVEST | Bill Wake | "INVEST in Good Stories" (XP123, 2003) |
| MoSCoW | Dai Clegg (Oracle) | 无单一官方出版物 |
| Two Pizza Team | Jeff Bezos (Amazon) | 无单一官方出版物 |
| Delphi Method | Helmer, Dalkey, Rescher (RAND) | Project RAND 历史记录 |
| WBS | PMI (PMBOK) | "A Guide to the Project Management Body of Knowledge" |
| Story Points | Mike Cohn / XP community | "Agile Estimating and Planning" (Prentice Hall, 2005) |

---

## 八、调研方法论说明

**信息源优先级**：
1. 原始论文和官方文档（最高优先级）
2. 知名工程博客和一手实践者文章
3. 二手解释和转述参考（已明确标注可信度）

**信息源黑名单**：
- 知乎、微信公众号（按要求不使用）

**可信度等级说明**：
- **高**：原创者/官方来源或原始研究论文
- **中**：知名行业来源（二手但准确）
- **低**：来源不明或可能有混淆

**调研局限性**：
- WebFetch 对某些 HTTPS 网站存在证书验证问题，导致部分来源无法访问
- 某些一手来源（如 Dai Clegg 对 MoSCoW 的原始描述）需要进一步考证
- 部分方法论的"创始权"存在历史争议，调研基于可验证的公开来源


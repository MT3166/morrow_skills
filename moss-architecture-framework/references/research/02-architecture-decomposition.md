# 软件架构分解核心流派调研

## 核心问题：如何判断一个模块/服务边界是「好的」？

### 一、Conway's Law 及反向（Systemness Principle）

**Conway's Law（1968）**
- Melvin Conway 1968 年提出：组织结构决定系统结构
- 原始论文："How Do Committees Invent?" (Datamation 1968)
- 核心命题：系统的边界往往映射了通信子图的结构
- 可信度：★★★★★（经典理论，被大量实践验证）

**Systemness Principle（系统化原则）**
- 强调系统作为整体而非部件的集合
- 反对孤立的模块化，倡导跨模块的一致性和协同
- 与微服务"智能端点"哲学相通
- 来源：Better Programming / Medium (via redirects)
- 可信度：★★★☆☆

**Inverse Conway Maneuver（反向康威策略）**
- 建议组织结构跟随所需的系统结构，而非相反
- 通过重组团队来诱导产生目标系统架构
- 可信度：★★★★☆

---

### 二、模块化设计（Modular Design）

**High Cohesion（高内聚）**
- 同一模块内的元素应高度相关
- Yourdon & Constantine (1979)《结构化设计》奠定理论基础
- Cohesion 类型（从低到高）：偶然→逻辑→时序→过程→通信→顺序→功能
- 判断标准：模块职责是否单一、是否围绕共同目标
- 可信度：★★★★★（经典原则）

**Low Coupling（低耦合）**
- 模块间依赖应最小化
- 依赖方向应从低层向高层（依赖反转）
- 可信度：★★★★★（经典原则）

**Interface Segregation（接口隔离）**
- Robert C. Martin (1996) SOLID 原则之一
- 不应强迫调用方依赖不需要的接口
- 判断标准：接口是否过于庞大、是否包含调用方不需要的方法
- 可信度：★★★★★

---

### 三、边界划分（Bounded Context / 服务边界）

**Bounded Context（DDD）**
- Martin Fowler (2006+)：《领域驱动设计》战略设计核心模式
- 来源：https://martinfowler.com/bliki/BoundedContext.html
- 核心原则：
  - 每个 BC 有自己统一的内部模型
  - 不同 BC 可能用不同方式建模相同概念（多义词问题）
  - 边界的主要驱动因素是**人类文化**——语言变化处即边界
  - 上下文映射(Context Maps)描述 BC 间关系
- 判断标准：
  - 语言是否一致（Ubiquitous Language）
  - 是否有独立的业务能力
  - 是否可独立部署
- 可信度：★★★★★

**Simple Component System (SCS) 架构**
- 来源：https://scs-architecture.org/
- 七条核心原则：
  1. **Autonomous** - 每个系统独立实现其用例
  2. **One Team** - 每个 SCS 由一个团队拥有
  3. **Asynchronous Dependencies** - 异步通信解耦
  4. **Own Data & Logic** - 包含自己的数据和业务逻辑
  5. **Own UI** - 有自己的用户界面
  6. **No Shared Business Logic** - 不共享业务代码
  7. **Hardly Shared Infrastructure** - 最小化共享基础设施（如数据库）
- 分解启发式：
  - 沿领域边界切割
  - 确保每个 SCS 在一个团队可管理的范围内
- 可信度：★★★★☆

**服务边界划分原则**
- 来源：https://www.atlassian.com/microservices/microservices-architecture/microservices-vs-monolith
- 关键洞察："Microservices decouple major business, domain-specific concerns into separate, independent code bases"
- 可信度：★★★☆☆

---

### 四、架构视图（Architecture Views）

**4+1 View Model（Kruchten 1995）**
- Philippe Kruchten 发表在《IEEE Software》
- 五种视图：
  1. **Logical View** - 功能需求（面向最终用户）
  2. **Development View** - 代码/模块组织（面向开发人员）
  3. **Process View** - 运行时的进程/并发（面向集成人员）
  4. **Physical View** - 硬件/部署拓扑（面向运维）
  5. **Scenarios** - 场景/用例，连接各视图
- 来源：Wikipedia / 学术论文
- 可信度：★★★★★

**C4 Model（Brown 2011+）**
- 来源：https://c4model.com/
- 作者：Simon Brown（也著有《Software Architecture for Developers》）
- 四层抽象：
  1. **System Context** - 系统与用户/其他系统的关系
  2. **Container** - 应用或数据存储（不是 Docker）
  3. **Component** - 代码组件集合
  4. **Code** - 具体的类/函数
- 支撑图：System Landscape、Dynamic、Deployment
- 设计原则：层次化抽象、工具无关、 notation 无关
- 判断标准：是否清晰描述了每个层级的"谁、什么、如何"
- 可信度：★★★★☆

**Architecture Decision Records (ADR)**
- 来源：https://github.com/joelparkerhenderson/architecture-decision-record
- Michael Nygard 推广的实践
- 核心要素：
  - **Title** - 决定名称
  - **Status** - 提议/接受/已废弃/已替代
  - **Context** - 背景情况
  - **Decision** - 决定内容
  - **Consequences** - 后果
- 最佳实践：
  - 保持 immutable，不修改已记录的决定
  - 使用现在时祈使语气文件名（如 `choose-database.md`）
  - 记录 pros/cons、成本/收益分析
- 可信度：★★★★★

---

### 五、实用分解启发式（Practical Decomposition Heuristics）

**Single Responsibility Principle (SRP)**
- Robert C. Martin：每个模块只有一个改变的理由
- 与"审美命令"(Aesthetic Imperative)相关：简洁的代码更美
- 可信度：★★★★★

**Aesthetic Imperative（审美命令）**
- 来源：The Pragmatic Engineer (Gergely Orosz)
- 核心论点：代码的"美"是工程卓越的信号
- 美的代码特征：意图清晰、无重复、适当的抽象层次
- 判断标准：代码是否让人感到愉悦、是否易于理解
- 可信度：★★★☆☆

**Diminishing Returns of Complexity（复杂性的收益递减）**
- 核心洞察：增加架构复杂度的边际收益递减
- 当分解带来的成本（分布式系统复杂度、运维负担）超过收益时，分解就不再值得
- 分解成本：网络延迟、分布式事务、运维复杂性
- 判断标准：
  - 团队是否足够大到需要独立部署
  - 是否有真正的性能/伸缩性需求
  - 服务间依赖是否自然形成域边界
- 可信度：★★★★☆

---

## 六、判断「好边界」的核心标准总结

### 共识原则（各派公认）

| 标准 | 说明 |
|------|------|
| **内聚性** | 模块职责单一、围绕共同业务能力 |
| **低耦合** | 依赖方向单一、无循环依赖 |
| **独立部署** | 可独立发布、不影响其他模块 |
| **独立数据** | 拥有自己的数据存储 |
| **团队所有权** | 一个团队拥有、团队边界与模块边界匹配 |
| **语言一致性** | 同一上下文中无歧义的术语 |

### 各派分歧点

| 流派 | 核心主张 |
|------|----------|
| **DDD 学派** | 强调业务边界优先于技术边界；BC 是核心概念 |
| **SCS 学派** | 强调数据 + 逻辑 + UI 的三元一体；不允许共享数据库 |
| **微服务学派** | 强调独立部署和伸缩；可接受数据冗余 |
| **传统模块化** | 强调静态代码结构而非运行时边界 |

### 判断触发器（满足任一即需审视边界）

1. 频繁的跨团队协调导致交付延迟
2. 一个模块的变更频繁引发其他模块的问题
3. 难以独立测试某个模块
4. 数据库成为共享依赖
5. 领域专家使用不同术语描述同一概念
6. 团队认知负荷过高

### 判断反触发器（满足任一可能表明边界不佳）

1. 服务间大量同步调用
2. 分布式事务覆盖多个服务
3. 需要同时修改多个服务才能实现单一业务功能
4. 服务边界与团队边界严重不匹配
5. 频繁的跨服务数据一致性修复

---

## 信息源可信度评级

- ★★★★★：经典理论、被广泛验证（Conway's Law、SRP、Cohesion/Coupling 理论、DDD 战略设计）
- ★★★★☆：知名工程实践、被大量采用（C4 Model、ADR、4+1 View、SCS Architecture）
- ★★★☆☆：有价值的工程洞察但相对小众（Aesthetic Imperative、Systemness Principle）

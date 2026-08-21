# Psych-Support-Bot 综合项目审查报告

> 审查日期：2026-08-20
> 审查范围：全量源码 + Langfuse 集成改动 + Agent 架构基线对标
> 审查工具：源码人工审查 + [agentops-awesome-list](https://github.com/redmaplewww/agentops-awesome-list)（T3 生产级模板）
> 审查类型：只读架构审计，未修改任何项目文件

---

## 目录

- [一、项目概况](#一项目概况)
- [二、整体完成度评估](#二整体完成度评估)
- [三、当前已实现的能力清单](#三当前已实现的能力清单)
- [四、质询机制深度分析（核心差异化能力）](#四质询机制深度分析核心差异化能力)
- [五、AgentOps 完整架构基线对标](#五agentops-完整架构基线对标)
- [六、问题分类与优先级](#六问题分类与优先级)
- [七、过度设计与欠设计警告](#七过度设计与欠设计警告)
- [八、下一步建议执行顺序](#八下一步建议执行顺序)

---

## 一、项目概况

### 1.1 定位与产品边界

一个基于 LangGraph 工作流的心理健康支持系统，面向轻中度心理困扰用户，提供情绪支持对话、症状筛查量表（PHQ-9/GAD-7/ISI）、引导式干预练习（CBT/ACT/DBT）、每日打卡和趋势跟踪。

**产品边界**：不提供诊断、不替代精神科医生或心理咨询师、不处理急性高危用户（自杀计划/精神病性症状/躁狂等）的深度干预。

### 1.2 技术栈

| 层 | 技术 | 状态 |
|---|---|---|
| API 框架 | FastAPI | ✅ 完整 |
| AI 编排 | LangGraph（8 节点线性图） | ✅ 完整 |
| LLM | 小红书 dots3-note-prev 模型（OpenAI 兼容接口） | ✅ 已对接 |
| 可观测性 | Langfuse SDK | ✅ 刚完成集成 |
| 数据库 | SQLAlchemy ORM + Alembic | ⚠️ SQLite 本地可用，PostgreSQL 迁移不完整 |
| 知识库 | 关键词检索 + 本地 JSON 语料 | ⚠️ pgvector 未启用 |
| 前端 | 静态 HTML 聊天页 | ⚠️ 仅聊天 |
| 缓存/队列 | Redis / Celery | ❌ 未实现（计划中） |
| 部署 | Docker + docker-compose + systemd | ⚠️ 有部署方案，无健康检查/回滚/扩展策略 |

### 1.3 架构全景

```
用户消息
  ↓
[ConversationService.respond()]
  ├── 问卷流程拦截（assessment 优先路由）
  └── LangGraph 对话图
        ├── risk_classifier → 确定性关键词风险分类（含否定检测）
        ├── intent_router → 关键词意图路由
        ├── consultation_planner → 多流派会诊 + 临床访谈阶段策略
        ├── memory_loader → 记忆快照加载
        ├── knowledge_loader → 关键词知识检索
        ├── response_generator → LLM 生成（含语言锁 + 重试）
        ├── safety_reviewer → Prompt 泄露检测
        └── summary_writer → 会话摘要
```

### 1.4 Langfuse 追踪结构

每次对话请求在 Langfuse 中的可观测结构：

```
conversation_graph.invoke (span)
├── input: {user_id, session_id, message, mode}
├── llm.invoke (generation)
│   ├── input: {system_prompt, user_message}
│   ├── metadata: {model, language}
│   └── output: "模型回复内容..."
├── llm.invoke_retry (generation)  ← 仅语言重试时
└── output: {mode, risk_level, reply, summary}
```

改动涉及 5 个文件：

| 文件 | 改动内容 |
|---|---|
| `.env` | 新建，配置 OpenAI + Langfuse 密钥 |
| `infra/telemetry/tracing.py` | 从 40 行扩展到 132 行，新增 `get_langfuse()` / `trace_span()` / `update_span_output()` / `flush_langfuse()` |
| `services/conversation.py` | `respond()` 方法用 `trace_span` 包裹对话图调用，记录 input/output |
| `infra/llm/generation.py` | `_invoke()` 中用 `trace_span(as_type="generation")` 包裹 LLM 调用，retry 也有独立 span |
| `app.py` | lifespan 中初始化 Langfuse 客户端 + 关闭时 flush |

### 1.5 AgentOps 难度选级

根据 agentops-awesome-list 难度模板选择问题：

| # | 问题 | 回答 | 触发 |
|---|---|---|---|
| 1 | 是否只回答对话，还是可以调用工具/外部系统？ | 调用外部 LLM API（dots3-note-prev），有知识检索 | T3 |
| 2 | 是否需要跨会话记住用户？ | 是，有记忆快照系统、用户画像、历史会话 | T3 |
| 3 | 运行时长是分钟/小时/天，还是单轮？ | 多轮对话，跨会话 | T3 |
| 4 | 是否影响金钱、生产数据、声誉、隐私数据或他人？ | 处理敏感心理健康数据，有自杀/自残风险 | T3 |
| 5 | 是否需要多角色、路由、交接或 Agent 注册表？ | 有 5 流派多学科会诊 | T3 |
| 6 | 错误操作是否需要回滚、审计或人工审批？ | 安全风险事件需要审计和人工审查 | T3 |

**选级结论：T3（生产级项目）**。多项触发 T3，项目处理敏感心理健康数据、有安全风险边界、面向真实用户。

**体检判定：blocked** — 项目在对话工作流和风险评估上具备良好的架构基础，但在安全审查器、LLM 容错、评估体系、证据门控、会话隔离和部署运维方面存在 T3 级别必须补齐的严重缺口，当前状态不满足生产上线条件。置信度：high。

---

## 二、整体完成度评估

### 里程碑完成度

按 `PROJECT_PLAN.md` 的 6 个里程碑评估：

| 里程碑 | 状态 | 完成度 | 说明 |
|---|---|---|---|
| M0 确认范围与架构 | ✅ Done | 100% | 项目计划完整 |
| M1 后端骨架 | ✅ Done | 100% | FastAPI + 配置 + 路由 |
| M2 AI 工作流 | ✅ Done | 90% | LangGraph 8 节点完整，但 safety_reviewer 功能空心化 |
| M3 持久层 | ✅ Done | 75% | ORM 完整，但 Alembic 迁移缺表缺字段 |
| M4 核心领域 API | ✅ Done | 85% | 对话/评估/打卡/计划/报告 API 均有，但计划系统仅存根 |
| M5 安全与可观测 | 🟡 In Progress | 70% | Langfuse 集成刚完成，但 safety_reviewer 仍空心化，评估体系浅薄 |
| M6 MVP 集成 | 🟡 In Progress | 50% | 后端端到端可用，但前端仅聊天，用户旅程多链路断裂 |

**总体完成度：约 65%**

### AgentOps 架构组件评分汇总

| 组件 | 评分 | 证据 | 需要的下一步 |
|---|---|---|---|
| Task intake | weak | `intent.py` 关键词路由 | 添加诊断请求检测 + 置信度阈值 |
| Agent loop | adequate | `conversation.py` 8 节点图 | 添加反思节点和终止条件 |
| State machine | adequate | `GraphState` 30 字段 | 添加 reducer 规则和版本迁移 |
| Memory | weak | `build_memory_snapshot()` | 分层记忆 + 写入门控 + 用户控制 |
| Tool layer | not-needed | 无外部工具 | 不适用 |
| Evidence/gates | missing | 无证据系统/门控系统 | **必须从零建立** |
| Multi-agent coordination | weak | 5 Agent 并行会诊 | 添加角色 non-goals + 独立评估 |
| Evaluation | weak | 17 场景模式/风险匹配 | 扩充质量维度 + 回归 + red-team |
| Guardrails | weak | 关键词风险分类 + Prompt 泄露检测 | 增强 safety_reviewer + 诊断拦截 + CORS |
| Runtime platform | weak | Docker + systemd | 健康检查 + 回滚 + 扩展策略 |

---

## 三、当前已实现的能力清单

### ✅ 完整实现

| # | 能力 | 源码位置 | 说明 |
|---|---|---|---|
| 1 | 确定性风险分类 | `ai/safety/rules.py` | 关键词匹配 + 否定检测 + 时效性升级，中英文双语 |
| 2 | 危机模式拦截 | `ai/safety/crisis.py` | critical/high 风险跳过 LLM，直接输出安全回复 + 热线 |
| 3 | LangGraph 对话流 | `ai/graphs/conversation.py` | 8 节点线性图，风险优先路由 |
| 4 | 意图路由 | `ai/routers/intent.py` | 关键词路由到 support/assessment/intervention/planning/crisis |
| 5 | 多流派会诊 | `ai/consultation.py` + `infra/llm/generation.py` | 5 个 Agent 并行调用 + 综合，ThreadPoolExecutor 并发 |
| 6 | 临床访谈策略 | `ai/interview.py` | 检测矛盾/回避/绝对化，决定是否允许质询 |
| 7 | 量表评估全流程 | `domain/assessments/` | PHQ-9/GAD-7/ISI 完整：引导→答题→评分→解读→安全标志 |
| 8 | 每日打卡 | `api/routes/checkins.py` + 持久化 | mood/anxiety/sleep/energy 4 维 |
| 9 | 知识摄入管道 | `knowledge_ingestion.py`（852 行） | URL 抓取 + HTML 清洗 + PDF/TXT/MD 导入 + 分块 + 主题推断 + 学习笔记合成 |
| 10 | LLM 语言锁 | `infra/llm/generation.py` | 中文输入→中文输出，英文输入→英文输出，违反时自动重试 |
| 11 | Langfuse 追踪 | `infra/telemetry/tracing.py` + `services/conversation.py` + `infra/llm/generation.py` + `app.py` | 对话图调用 + 每次 LLM 调用 + retry 的完整 span 链路 |
| 12 | 基础知识检索 | `ai/knowledge/index.py` | 关键词匹配 + 多维评分（mode/topics/keywords/source 加权） |
| 13 | CBT/ACT/DBT 知识库 | `ai/knowledge/{cbt,act,dbt}.py` | 认知扭曲目录 + 练习模板 + 技能指南，内容专业且详实 |
| 14 | 用户画像 API | `api/routes/users.py` + 持久化 | concerns/goals/preferences/risk_notes |
| 15 | 会话历史 API | `api/routes/conversation.py` | sessions/messages/risk-events 查询 |
| 16 | Typed contracts | `ai/schemas/messages.py` Pydantic 模型 | `ConversationRequest`/`ConversationResponse`/`GeneratedReply`/`RiskResult` 完整 |
| 17 | CI/CD 基础 | `.github/workflows/ci.yml` | lint + test + secrets-check 三阶段 CI |

### ⚠️ 半完成

| # | 能力 | 当前状态 | 缺口 |
|---|---|---|---|
| 1 | 安全审查器 | `safety_reviewer.py` 仅检测 Prompt 泄露 | 不检查诊断语言/不当建议/安全边界越界/质询合理性 |
| 2 | 趋势分析 | `domain/reports/trends.py` 有前后半段均值比较 | 无异常检测、无关联评估变化、无主动预警 |
| 3 | 周报 | `domain/reports/service.py` 输出一行均值文本 | 无临床解读、无异常标记 |
| 4 | 干预计划 | `domain/plans/templates.py` 3 个静态模板 | 无每日内容、无进度跟踪、无个性化 |
| 5 | 记忆系统 | `repositories.py` 的 `build_memory_snapshot` 拼接快照 | 非结构化、无跨轮次矛盾检测、无用户可见控制、无写入门控、无过期策略 |
| 6 | 评估体系 | `tests/evals/cases.json` 17 个场景 | 缺 3 个计划维度，无回复质量评估、无回归测试集、无 red-team |
| 7 | Observability | Langfuse span 链路完整 | 无工具 span、无状态 diff、无记忆写入日志、无 cost/latency 指标、无 Score 闭环 |
| 8 | 部署运维 | Docker + systemd 方案完整 | 无健康检查验证、无水平扩展、无滚动部署/回滚、无 async job 调度 |
| 9 | 多 Agent 协作 | 5 流派并行 + LLM 综合 | 无角色 non-goals、无权限定义、无独立评估、无冲突仲裁 |
| 10 | Project ledger | `PROJECT_PLAN.md` + `PROJECT_PROGRESS.md` | 无统一 ledger、无决策记录（含 ID/证据/owner）、无操作记录、无证据索引、无门控日志 |

### ❌ 完全缺失

| # | 能力 | 影响 | AgentOps 基线对应 |
|---|---|---|---|
| 1 | Onboarding 流程 | 用户无法理解产品边界、无初始安全筛查 | — |
| 2 | 前端界面（除聊天外） | 评估/练习/打卡/报告/计划对用户不可见 | — |
| 3 | pgvector 语义检索 | 无法语义匹配，非安全路径的 RAG 能力受限 | Context assembly |
| 4 | 跨轮次矛盾检测 | 单轮质询无法发现"上一轮说的 A 和这一轮说的 B 矛盾" | Reflector |
| 5 | 诊断请求确定性拦截 | 用户说"我是不是抑郁症"时，意图路由不保证拦截 | Task intake / Guardrails |
| 6 | Redis/Celery 集成 | 异步摘要写入、定时周报生成无法处理 | Runtime platform |
| 7 | LLM 降级策略 | `response_generator.py` 第 59 行 `raise RuntimeError` 后的 fallback 代码不可达 | Model layer / Executor |
| 8 | **Reflector（后置反思节点）** | `safety_reviewer` 不做步骤反思/错误诊断/重试策略 | Reflector — T3 required |
| 9 | **Evidence system** | 高风险操作无证据链，无法审计安全决策 | Evidence system — T3 required |
| 10 | **Gate system** | 无发布门控，任何变更可直接上线，安全回归无强制阻断 | Gate system — T3 required |
| 11 | **认证/授权** | 任何人可构造 `user_id` 访问任意用户心理健康数据 | Identity/session scope — T3 required |
| 12 | **运维手册（runbook）** | 生产事故时团队无标准处理流程 | Operations/runbook — T3 required |
| 13 | **Artifact 版本管理** | 评估结果和报告无版本/checksum/provenance | Artifact schema — T3 required |
| 14 | **会话 retention 策略** | 心理健康对话数据永久存储，不符合数据最小化原则 | Identity/session scope |

---

## 四、质询机制深度分析（核心差异化能力）

> 质询是本项目区别于"套壳 ChatGPT"的核心差异化能力。心理疾病患者的自述往往不可靠——矛盾、回避、绝对化、缩小化是常见模式。一个合格的心理支持系统不能仅做"情绪安抚器"，必须具备"质疑用户发言、发现漏洞、合理应对"的能力。

### 4.1 质询的业务必要性

在心理临床场景中，来访者的自述存在以下可靠性问题：

| 模式 | 典型表现 | 临床意义 |
|---|---|---|
| 矛盾 | "我没事，但是我真的撑不住了" | 前后表述冲突，需澄清真实状态 |
| 回避 | "随便吧""无所谓""不想说" | 可能掩盖核心痛苦，需温和探索 |
| 绝对化 | "永远""一定""完全""根本" | 认知扭曲，需检验证据和例外 |
| 缩小化 | "其实没事""也还好""不严重" | 可能与实际痛苦程度不符，需对照行为 |
| 模式重复 | "每次都这样""总是反复" | 可能有维持因素，需追踪序列 |

如果系统对这些模式无条件接受、不追问，它就只是一个"共情机器"，无法帮助用户获得真正的临床洞察。

### 4.2 当前质询链路

质询能力分布在 4 个节点的协作中：

```
用户消息
  ↓
[intent_router]  ← 关键词路由：检测危机/评估/干预/计划/支持意图
  ↓
[consultation_planner]  ← 调用 determine_interview_process()，决定访谈阶段和质询策略
  ↓
[response_generator]  ← 将策略注入 system prompt，调用 LLM 生成质询性回复
  ↓
[safety_reviewer]  ← 后置检查（目前仅检测 prompt 泄露，不审查质询合理性）
```

**关键文件**：

| 文件 | 职责 |
|---|---|
| `ai/routers/intent.py` | 关键词意图路由，含初步拒答逻辑（REFUSAL_KEYWORDS） |
| `ai/interview.py` | 核心质询逻辑：检测 8 种语言特征，决定 `challenge_allowed` |
| `ai/prompts/templates.py` | 将质询策略（`build_process_prompt`）注入 LLM system prompt |
| `ai/nodes/consultation_planner.py` | 调用 `determine_interview_process`，将结果写入 GraphState |
| `ai/nodes/response_generator.py` | 将 `challenge_allowed`/`interview_stage`/`question_strategy`/`loop_hint` 传入 LLM 生成 |

### 4.3 单轮检测维度

`ai/interview.py` 的 `determine_interview_process()` 函数检测以下 8 种语言特征：

| 维度 | 关键词示例 | 检测逻辑 |
|---|---|---|
| 开放探索 | "不知道""说不清""confused""overwhelmed" | 用户处于混乱状态，需开放提问 |
| 强模式 | "总是""每次""every time""again and again" | 反复出现的行为模式，需追踪序列 |
| 弱模式 | "一直""always""keep" | 需结合其他特征才触发模式分析 |
| 矛盾 | "但是""可是""又""but""however""yet" | 前后表述冲突，允许质询 |
| 回避 | "随便""无所谓""不想说""whatever" | 可能有可探索的回避，结合语境判断 |
| 绝对化 | "一定""永远""根本""all""never""completely" | 认知扭曲，需检验证据 |
| 缩小化 | "其实没事""也还好""不严重""it's fine" | 与实际痛苦可能不符 |
| 耗竭 | "累""疲惫""提不起劲""exhausted" | 需先澄清耗竭来源再质询 |

**关键设计决策**：

- 危机模式（`crisis`）和 high/critical 风险 → **禁止质询**，直接稳定化
- 评估模式（`assessment`）→ **禁止质询**，聚焦症状澄清
- 耗竭但无矛盾/绝对化/回避 → **禁止质询**，先探索
- 规划模式（`planning`）→ **允许质询**（`challenge_allowed = True`）

### 4.4 challenge_allowed 决策逻辑

`determine_interview_process()` 的决策优先级（后者覆盖前者）：

```
1. crisis / high / critical → safety_stabilization, 禁止质询
2. assessment → structured_assessment, 禁止质询
3. has_open_exploration → exploration, 开放提问
4. has_pattern → pattern_analysis, 循环追踪
5. has_contradiction → hypothesis_testing, 允许质询
6. has_absolutist → hypothesis_testing, 温和质询
7. has_actionable_avoidance / has_minimization → resistance_exploration, 温和质询
8. has_pattern + (contradiction/absolutist) → hypothesis_testing, 循环质询
9. has_exhaustion 且无上述 → exploration, 禁止质询（先澄清）
10. planning → planning, 允许质询
11. intervention + engagement → formulation, 澄清
```

### 4.5 Prompt 注入方式

质询策略通过 `build_process_prompt()` 注入 LLM 的 system prompt，包含：

- **访谈阶段**（`interview_stage`）：engagement / exploration / pattern_analysis / hypothesis_testing / resistance_exploration / formulation / planning / structured_assessment / safety_stabilization
- **提问策略**（`question_strategy`）：open / clarifying / looping / gentle_challenge / directive
- **质询许可**（`challenge_allowed`）：布尔值，控制 LLM 是否可质疑用户表述
- **循环提示**（`loop_hint`）：针对当前阶段的具体提问指引

这些参数在 `response_generator.py` 中传入 `generate_clinically_bounded_reply()` 或 `generate_multidisciplinary_consultation()`，最终拼接到 system prompt 中。

### 4.6 拒答机制现状

当前拒答能力分布在两个层面：

| 层面 | 实现 | 说明 |
|---|---|---|
| 意图路由层 | `ai/routers/intent.py` 的 `REFUSAL_KEYWORDS` | 检测到"跳过""不想做""算了"等，路由到 support 模式 |
| 评估流程层 | `domain/assessments/service.py` 的 `detect_skip_or_exit()` | 检测到退出意图，结束问卷会话 |

**缺口**：

- 没有针对**诊断请求**的确定性拒答。用户问"我有没有抑郁症"时，`intent.py` 不保证拦截——关键词路由可能将其归为 `support` 模式，LLM 可能自由回复一个诊断性表述
- 没有**越界承诺**的拒答。用户说"你能不能治好我"时，系统不会确定性拒绝
- 没有后置审查。`safety_reviewer` 不检查 LLM 回复中是否包含了不当诊断或越界承诺

### 4.7 核心缺口

| 缺口 | 严重度 | 说明 | AgentOps 基线对应 |
|---|---|---|---|
| **无跨轮次矛盾检测** | 🔴 高 | 当前 `determine_interview_process` 只分析当前这条消息，无法获取"用户上一轮说了 A，这一轮说了非 A"的矛盾。`memory_loader` 节点仅拼接文本快照，不做结构化对比。这导致最核心的质询场景（前后矛盾）无法实现 | Reflector / Memory |
| **无诊断请求确定性拦截** | 🔴 高 | 用户直接问"我是不是抑郁症""我是不是焦虑症"时，`intent.py` 关键词不包含诊断请求检测，LLM 可能给出诊断性回复，违反产品安全边界 | Task intake / Guardrails |
| **质询合理性无后置审查** | 🟡 中 | `safety_reviewer` 仅检测 prompt 泄露，不检查 LLM 的质询是否过度激进、是否在不应质询的场景下质询了 | Reflector |
| **单轮关键词检测的精度局限** | 🟡 中 | "但是"可能是真正的转折而非矛盾，"永远"可能是修辞而非认知扭曲。纯关键词匹配无法区分语用差异，可能导致过度质询 | — |
| **耗竭检测过粗** | 🟢 低 | 当前"累""疲惫"等词触发耗竭路径，但无法区分身体疲劳、情绪耗竭、关系疲惫和预期性焦虑——临床意义完全不同 | — |

---

## 五、AgentOps 完整架构基线对标

以下为对照 agentops-awesome-list 完整架构基线的逐组件评估。难度等级为 T3（生产级项目）。

| 基线组件 | 难度要求 | 状态 | 当前证据 | 缺口 / 不需要的理由 |
|---|---|---|---|---|
| **System boundary** | required | present | `PROJECT_PLAN.md` §1-2 定义了产品边界、目标用户、排除用户、高风险处理原则 | 边界定义完整但未在运行时强制（如诊断请求拦截缺失） |
| **Task intake** | required | weak | `ai/routers/intent.py` 关键词意图路由 + `ai/safety/rules.py` 确定性风险分类 | 意图路由为纯关键词匹配，无置信度阈值、无 fallback 路由、无诊断请求检测 |
| **Identity/session scope** | required | weak | `GraphState` 有 `user_id`/`session_id`；`ConversationSession` ORM 有 `user_id` 索引 | 无认证机制、无 RBAC、无租户隔离、无会话过期/清理策略、无 retention 策略 |
| **Agent loop** | required | present | `ai/graphs/conversation.py` LangGraph 8 节点线性图，风险优先路由 | 线性图无循环/重试限制，无 observe-think-act 反思循环 |
| **Planner** | required | present | `ai/consultation.py` 多流派会诊规划 + `ai/interview.py` 临床访谈策略 | 规划无依赖排序、无计划修订触发器、无规划失败 fallback |
| **Router** | required | weak | `ai/routers/intent.py` 关键词路由到 5 种模式 | 无置信度阈值、无 fallback 路由、无拒绝/升级路径、无路由可观测性字段 |
| **Executor** | required | weak | `infra/llm/generation.py` LLM 调用 + `ThreadPoolExecutor` 并行会诊 | 无超时设置、无取消机制、无重试策略（语言锁 retry 不算）、无 typed error handling |
| **Reflector** | required | missing | 无后置反思节点 | `safety_reviewer` 仅检测 Prompt 泄露，不做步骤反思/错误诊断/重试策略 |
| **Terminator** | required | weak | LangGraph `END` 节点终止 | 无最大迭代限制、无卡住运行处理、无未解决状态策略 |
| **Typed messages** | required | present | `ai/schemas/messages.py` Pydantic 模型 | 消息类型完整 |
| **State schema** | required | present | `ai/schemas/state.py` `GraphState(TypedDict)` 30 个字段 | 有默认值但无 reducer/merge 规则、无版本迁移 |
| **Tool schema** | optional | not-needed | 无工具层 | 项目不使用外部工具，T3 下可选 |
| **Artifact schema** | required | missing | 无 artifact 系统 | 评估结果、周报以 DB 记录存储但无版本/checksum/provenance |
| **Handoff schema** | optional | not-needed | 无交接 schema | 多流派会诊是并行调用后综合，不是交接 |
| **Model layer** | required | weak | `infra/llm/factory.py` ChatOpenAI + `settings.py` 配置；Prompt 在 `ai/prompts/templates.py` | 无 Prompt 版本管理、无结构化输出验证、fallback bug、无模型选择策略 |
| **Context assembly** | required | weak | `build_memory_snapshot()` 拼接快照 + `ai/knowledge/index.py` 关键词检索 | 无 ranking/dedup/citation、无 token budget、无 context pollution 防御、无 pgvector 语义检索 |
| **Working memory** | required | present | `GraphState` 作为运行时状态对象 | — |
| **Short-term memory** | required | present | `build_memory_snapshot()` 加载最近 3 条消息 + 最新摘要 + 最近评估 + 最近打卡 | 拼接式快照，非结构化，无运行检查点 |
| **Long-term memory** | optional | weak | `repositories.py` 的 `build_memory_snapshot` 从 DB 加载历史 | 无 episodic/semantic/procedural 分层、无写入门控、无冲突检测、无用户可见控制、无过期策略 |
| **Tool layer** | optional | not-needed | 项目不使用外部工具 | 不适用 |
| **Code/workspace sandbox** | optional | not-needed | 无代码执行 | 不适用 |
| **Project Ledger** | required | weak | `PROJECT_PLAN.md` + `PROJECT_PROGRESS.md` 作为项目文档 | 无统一项目 ledger 文件、无决策记录（含 ID/证据/owner）、无操作记录、无证据索引、无门控日志 |
| **Evidence system** | required | missing | 无证据系统 | 无 claim-to-evidence 映射、无证据 ID、无证据质量分级、无过期管理 |
| **Gate system** | required | missing | 无门控系统 | 无操作门控（evidence/risk/permission/postcondition）、无发布门控、无人工审批 |
| **Workspace/artifacts** | required | missing | 无 workspace | 评估结果和报告仅 DB 记录，无版本管理、无所有权、无导出/删除策略 |
| **Agent registry** | optional | missing | `consultation.py` 硬编码 5 个 Agent | 无注册表、无版本/owner/health/trust tier、无能力发现 |
| **Role matrix** | optional | weak | `consultation.py` 定义 5 个角色（CBT/精神动力/人本/ACT/DBT）的 focus | 无 non-goals、无权限定义、无数据访问范围、无独立评估 |
| **Task routing** | required | weak | `should_trigger_multidisciplinary_consultation()` 决定是否触发会诊 | 无路由表/策略、无置信度阈值、无 fallback、无拒绝规则、无路由可观测性 |
| **Coordination state** | optional | weak | `ThreadPoolExecutor` 并行调用，结果汇总 | 无共享状态、无锁/租约、无状态版本、无同步/恢复策略 |
| **Conflict arbitration** | optional | missing | 无冲突仲裁 | 会诊意见由 LLM 综合，无冲突分类/仲裁器/决策规则/审计记录 |
| **Handoff lifecycle** | optional | not-needed | 使用 agent-as-tool 模式而非交接 | 不适用 |
| **A2A boundary** | optional | not-needed | 无跨系统 Agent 通信 | 不适用 |
| **MCP/tool boundary** | optional | not-needed | 无 MCP 集成 | 不适用 |
| **Observability** | required | weak | `infra/telemetry/tracing.py` Langfuse SDK 集成 | 无工具 span、无状态 diff、无记忆写入日志、无 cost/latency 指标、无 Score 评估闭环 |
| **Evaluation** | required | weak | `tests/evals/cases.json` 17 个场景 + `evals/runner.py` + pytest | 仅覆盖模式+风险等级匹配，无 trajectory eval、无回归测试集、无 red-team、无 canary/shadow、无回复质量评估、无发布门控 |
| **Guardrails/security** | required | weak | `safety/rules.py` + `safety/crisis.py` + `safety_reviewer.py` + CI secrets-check | safety_reviewer 仅检测 Prompt 泄露；无诊断请求拦截；`.env` 泄露风险；CORS `allow_origins=["*"]`；无 rate limiting；无 prompt injection 防御 |
| **Deployment/runtime** | required | weak | Docker + docker-compose + systemd + deploy.sh | 无健康检查端点验证、无水平扩展策略、无滚动部署/回滚、无 async job 调度 |
| **Operations/runbook** | required | missing | 无运维手册 | 无卡住运行恢复、无事件响应流程、无坏记忆修复、无外部漂移处理、无事故复盘模板 |
| **Self-evolution** | optional | missing | 无自进化机制 | T3 下可选，当前不需要 |

### 功能审查矩阵

| 功能/能力 | 是否存在 | 完整度 | 主要问题 | 建议 |
|---|---|---|---|---|
| 风险分类 | ✅ | 80% | 纯关键词匹配，无 LLM 辅助分类；无置信度评分 | 可接受作为 MVP，长期需引入 LLM 辅助 |
| 危机模式拦截 | ✅ | 90% | 确定性路由 + 安全回复 + 热线信息 | 良好 |
| LangGraph 对话流 | ✅ | 85% | 线性图无循环/反思/重试 | 可接受，反思节点为 P0 补齐项 |
| 意图路由 | ✅ | 50% | 纯关键词，无置信度/fallback/诊断检测 | P0 补齐诊断拦截 |
| 多流派会诊 | ✅ | 70% | 并行调用 + LLM 综合，无冲突仲裁 | 可接受 |
| 临床访谈策略 | ✅ | 75% | 8 维度检测 + 11 种决策路径，仅限单轮 | P1 补齐跨轮次矛盾检测 |
| 量表评估 | ✅ | 90% | PHQ-9/GAD-7/ISI 完整流程 | 良好 |
| 每日打卡 | ✅ | 85% | 4 维度 + 持久化 | 良好 |
| 知识检索 | ✅ | 60% | 关键词匹配 + 多维评分，无语义检索 | P2 补齐 pgvector |
| LLM 语言锁 | ✅ | 85% | 中文/英文检测 + 自动重试 | 良好 |
| Langfuse 追踪 | ✅ | 70% | 对话图 + LLM 调用 span，无 Score 闭环 | P2 补齐 Score |
| 安全审查器 | ⚠️ | 20% | 仅检测 Prompt 泄露 | **P0 必须增强** |
| LLM 容错 | ❌ | 0% | `raise RuntimeError` 后 fallback 不可达 | **P0 必须修复** |
| 评估体系 | ⚠️ | 30% | 17 场景仅检查模式/风险匹配 | **P1 必须深化** |
| 记忆系统 | ⚠️ | 40% | 拼接快照，无分层/门控/用户控制 | P1 补齐 |
| Onboarding | ❌ | 0% | 完全缺失 | P1 补齐 |
| 前端（非聊天） | ❌ | 0% | 评估/练习/打卡/报告无前端入口 | P1 补齐 |
| Redis/Celery | ❌ | 0% | 未集成 | P2 补齐 |
| 认证/授权 | ❌ | 0% | 无认证机制 | P1 补齐 |
| 运维手册 | ❌ | 0% | 无 runbook | P1 补齐 |
| 发布门控 | ❌ | 0% | 无 eval gate / 安全回归门 | P0 补齐 |
| 证据系统 | ❌ | 0% | 高风险决策无证据链 | P0 补齐 |

---

## 六、问题分类与优先级

### 🔴 P0 — 上线必须完善（安全与数据完整性硬门槛）

| # | 问题 | 源码位置 | 风险说明 | AgentOps 基线对应 |
|---|---|---|---|---|
| 1 | **`response_generator.py` fallback bug** | 第 57-60 行：`raise RuntimeError` 后 `state["fallback_used"] = True` 不可达 | LLM 调用失败时服务直接崩溃，用户无任何回复，在高风险心理支持场景中可能导致严重后果 | Model layer / Executor |
| 2 | **Alembic 迁移不完整** | `questionnaire_sessions` 表无迁移；`assessments` 表缺 5 个字段（`plain_meaning`/`functional_impact`/`care_consideration`/`disclaimer`/`needs_safety_followup`） | PostgreSQL 生产环境跑 Alembic 后问卷功能崩溃 | — |
| 3 | **safety_reviewer 空心化** | `ai/nodes/safety_reviewer.py` 仅检测 prompt 泄露 | 不检查回复是否含诊断语言、不当建议、越界承诺——这是产品安全边线的最后防线 | Reflector — T3 required |
| 4 | **.env 密钥泄露风险** | `.env` 含明文 API Key 和 Langfuse 密钥 | 如果 git 提交会导致密钥泄露 | Guardrails |
| 5 | **无诊断请求确定性拦截** | `ai/routers/intent.py` 无诊断请求关键词 | 用户问"我是不是抑郁症"时 LLM 可能给出诊断性回复，违反安全边界。详见[质询机制分析 §4.6](#46-拒答机制现状) | Task intake / Guardrails |
| 6 | **无发布门控** | 无 CI eval gate、无安全回归门 | 任何变更可直接合入 main 并部署，安全回归无强制阻断 | Gate system — T3 required |
| 7 | **CORS `allow_origins=["*"]`** | `app.py` 第 43 行 | 生产环境允许任意来源跨域访问，存在安全风险 | Guardrails |
| 8 | **无证据系统** | 无证据记录 | 高风险安全决策（风险评估、危机路由）无证据链，无法审计 | Evidence system — T3 required |

### 🟡 P1 — 应该做（影响产品可用性和核心价值闭环）

| # | 问题 | 说明 | AgentOps 基线对应 |
|---|---|---|---|
| 9 | **前端功能补全** | 后端评估/练习/打卡 API 已就绪，但前端未暴露，用户只能聊天 | — |
| 10 | **跨轮次矛盾检测** | 当前质询仅限单轮，无法发现用户前后表述矛盾。这是质询机制的核心缺口，详见[质询机制分析 §4.7](#47-核心缺口) | Reflector / Memory |
| 11 | **干预计划内容填充** | 3 个计划模板仅存目录，无每日步骤和进度跟踪 | — |
| 12 | **质询合理性后置审查** | safety_reviewer 应检查 LLM 质询是否过度激进、是否在不应质询时质询了。详见[质询机制分析 §4.7](#47-核心缺口) | Reflector |
| 13 | **周报临床化** | 仅均值统计无异常检测，不具备早期预警能力 | — |
| 14 | **评估体系深化** | 补充躁狂/OCD/焦虑+失眠共病场景，增加回复质量评估维度 | Evaluation |
| 15 | **无认证机制** | 任何人可构造 `user_id` 访问任意用户的心理健康数据 | Identity/session scope — T3 required |
| 16 | **无运维手册** | 生产事故时团队无标准处理流程 | Operations/runbook — T3 required |
| 17 | **无会话 retention 策略** | 心理健康对话数据永久存储，不符合数据最小化原则 | Identity/session scope |
| 18 | **无项目 ledger** | 项目状态分散在多个文档中，无统一决策记录和操作日志 | Project ledger — T3 required |
| 19 | **Artifact 版本管理缺失** | 评估结果和报告无版本/checksum/provenance | Artifact schema — T3 required |

### 🟢 P2 — 可以做（增强能力，不阻塞上线）

| # | 方向 | 说明 | AgentOps 基线对应 |
|---|---|---|---|
| 20 | **pgvector 语义检索** | 当前关键词检索在非安全路径已够用，语义检索可提升匹配质量但不能作为安全门槛 | Context assembly |
| 21 | **LLM 模型路由** | 简单支持用轻量模型，复杂会诊用强模型，降低成本和延迟 | Model layer |
| 22 | **LLM 降级策略** | 主模型不可用时 fallback 到模板回复，保证服务连续 | Model layer / Executor |
| 23 | **知识库中文化** | 当前摄入源全为英文 NIMH/MedlinePlus，补充中文权威来源 | — |
| 24 | **Redis/Celery 集成** | 异步摘要写入、定时周报生成 | Runtime platform |
| 25 | **耗竭检测精细化** | 区分身体疲劳/情绪耗竭/关系疲惫/预期性焦虑，提升质询精度。详见[质询机制分析 §4.7](#47-核心缺口) | — |
| 26 | **Prompt 版本管理** | Prompt 在代码中硬编码，无版本追踪和回滚 | Model layer |
| 27 | **Langfuse Score 评估闭环** | 在 Langfuse 中对每次对话做人工/AI 评分，形成"trace → score → 优化"闭环 | Observability / Evaluation |
| 28 | **Rate limiting** | 无请求频率限制，可能被滥用 | Guardrails |
| 29 | **Agent registry** | 多流派会诊 Agent 硬编码，无法动态配置或版本管理 | Agent registry |

### 🔵 P3 — 前瞻方向（未来演进）

| # | 方向 | 说明 |
|---|---|---|
| 30 | **Relapse 预警** | 基于 check-in 趋势 + 评估历史，预测复发风险并主动干预 |
| 31 | **个性化策略路由** | 根据用户画像和历次效果数据，动态选择最优干预流派 |
| 32 | **单轮关键词检测精度提升** | 引入 LLM 辅助的语用分析，区分"但是"是真正转折还是修辞。详见[质询机制分析 §4.7](#47-核心缺口) |
| 33 | **多语言扩展** | 当前仅中英双语，可扩展日韩等 |
| 34 | **Admin 后台** | 风险事件审计、内容质量审查、用户管理 |
| 35 | **Self-evolution** | Prompt 自动优化闭环，需稳定 eval 基线后才有意义 |
| 36 | **Conflict arbitration** | 多 Agent 会诊意见冲突的形式化仲裁机制 |

---

## 七、过度设计与欠设计警告

### 过度设计警告

以下模块在当前阶段可以暂缓，避免过度设计：

- **Agent registry / A2A / MCP** — 当前 5 个硬编码 Agent 已满足需求，动态发现和跨系统协议在用户量达到一定规模前不必要
- **Self-evolution** — 需要稳定的 eval 基线后才有意义
- **Conflict arbitration** — 当前 LLM 综合模式已够用，形式化冲突仲裁在 Agent 数量增加后再考虑
- **Code/workspace sandbox** — 项目不执行代码，不适用
- **Handoff lifecycle** — 使用 agent-as-tool 模式而非交接，不适用

### 欠设计警告

以下模块在 T3 级别下缺失，是当前的严重风险：

| 缺失模块 | 风险 | 紧迫度 |
|---|---|---|
| **Reflector / Safety reviewer** | 安全审查器空心化是最大欠设计——产品安全边界的最后防线不生效 | 🔴 紧急 |
| **Evidence system + Gate system** | 完全缺失，高风险产品无证据链和门控是不可接受的 | 🔴 紧急 |
| **LLM fallback** | 容错完全缺失，服务可用性无保障 | 🔴 紧急 |
| **认证/授权** | 用户心理健康数据无保护 | 🟡 高 |
| **Operations runbook** | 生产运维无标准流程 | 🟡 高 |
| **评估体系** | 仅覆盖安全维度，不覆盖质量维度 | 🟡 高 |

---

## 八、下一步建议执行顺序

### 优化建议汇总（含实施成本和验收方式）

| 优先级 | 建议 | 预期收益 | 实施成本 | 验收方式 |
|---|---|---|---|---|
| P0 | 修复 LLM fallback bug | LLM 失败时用户仍有安全回复 | 0.5 天 | 单元测试覆盖 LLM 失败场景 |
| P0 | 增强 safety_reviewer | 安全边界最后防线生效 | 2-3 天 | 评估场景覆盖诊断/越界/质询维度 |
| P0 | 添加诊断请求拦截 | 产品安全边界确定性保障 | 1 天 | 评估场景覆盖诊断请求 |
| P0 | 补全 Alembic 迁移 | PostgreSQL 生产环境可用 | 1 天 | 在 PostgreSQL 环境跑通迁移 |
| P0 | 修复 CORS 配置 | 生产环境安全 | 0.5 天 | 配置检查 |
| P0 | 定义发布门控 | 安全回归有强制阻断 | 1 天 | CI 中集成 eval 门控 |
| P0 | 建立证据系统 | 高风险决策可审计 | 2-3 天 | 风险事件有证据记录 |
| P1 | 添加 API 认证 | 用户数据隔离 | 3-5 天 | 认证测试通过 |
| P1 | 创建运维手册 | 事故响应有标准流程 | 2 天 | runbook 覆盖 5+ 场景 |
| P1 | 深化评估体系 | 回复质量可量化 | 5-7 天 | 30+ 场景 + 质量维度评分 |
| P1 | 创建项目 ledger | 决策可追溯 | 1 天 | ledger 包含决策记录/操作日志 |
| P1 | 前端补全 | 用户旅程闭环 | 2-3 周 | 评估/打卡/计划页面可用 |
| P1 | 跨轮次矛盾检测 | 质询机制核心能力补齐 | 3-5 天 | 前后矛盾场景检测通过 |
| P2 | Prompt 版本管理 | 变更可追踪和回滚 | 2-3 天 | Prompt 变更有版本号和 diff |
| P2 | Langfuse Score 闭环 | 形成 trace → score → 优化循环 | 3-5 天 | Langfuse 中有评分数据 |
| P2 | pgvector 语义检索 | 知识匹配质量提升 | 3-5 天 | 语义检索 vs 关键词检索对比 |

### 执行时间线

```
立即修复（P0 — 第 1 周）
  ├── 1. 修复 response_generator.py fallback bug
  ├── 2. 补全 Alembic 迁移（questionnaire_sessions + assessments 字段）
  ├── 3. 增强 safety_reviewer（诊断语言检测 + 边界检查 + 质询合理性）
  ├── 4. .env 加入 .gitignore，提供 .env.example
  ├── 5. 诊断请求确定性拦截路由（intent.py 增加诊断关键词检测）
  ├── 6. 修复 CORS 配置（限制允许来源）
  ├── 7. 定义发布门控清单 + CI 集成
  └── 8. 为风险事件添加证据记录

短期补足（P1 — 第 2-4 周）
  ├── 9.  前端：评估问卷引导界面 + 每日打卡界面
  ├── 10. 跨轮次矛盾检测节点（consultation_planner 引入历史消息对比）
  ├── 11. 干预计划每日内容填充
  ├── 12. 质询合理性后置审查（safety_reviewer 增加质询强度检查）
  ├── 13. 周报异常检测逻辑
  ├── 14. 评估场景补全 + 回复质量评估
  ├── 15. API 认证中间件（JWT/Session）
  ├── 16. 运维手册（runbook）
  ├── 17. 会话 retention 策略
  ├── 18. 项目 ledger（决策记录/操作日志/证据索引）
  └── 19. Artifact 版本管理

中期增强（P2 — 第 5-8 周）
  ├── 20. pgvector 语义检索（非安全路径）
  ├── 21. 模型路由 + 降级策略
  ├── 22. 知识库中文源补充
  ├── 23. Redis/Celery 异步任务
  ├── 24. 耗竭检测精细化
  ├── 25. Prompt 版本管理
  ├── 26. Langfuse Score 闭环
  ├── 27. API rate limiting
  └── 28. Agent 注册表

长期演进（P3 — 未来）
  ├── 29. Relapse 预警模型
  ├── 30. 个性化策略路由
  ├── 31. 单轮关键词检测精度提升（LLM 辅助语用分析）
  ├── 32. 多语言扩展
  ├── 33. Admin 审计后台
  ├── 34. Self-evolution 闭环
  └── 35. Conflict arbitration 机制
```

---

*本报告基于全量源码只读审查 + agentops-awesome-list T3 模板对标生成，未修改任何项目文件。如需对某个具体问题展开方案设计，请单独提出。*
# Psych-Support-Bot 分工方案

> 创建日期：2026-08-20
> 基于远程仓库 `origin/main`（commit `255169f`）实际源码审查
> 参与人员：小组共 4 人，按任务优先级分阶段分配
> 分支策略：`main` 为稳定分支，`dev` 为集成分支，各功能分支从 `dev` 切出

---

## 目录

- [一、调整说明与分工原则](#一调整说明与分工原则)
- [二、远程仓库基线确认](#二远程仓库基线确认)
- [三、能力边界：能做与不能做](#三能力边界能做与不能做)
- [四、两阶段分工详述](#四两阶段分工详述)
  - [第一阶段：P0 必须修复（Day 1-5）](#第一阶段p0-必须修复day-1-5)
  - [第二阶段：P1 增强 + 前端 + 测试（Day 6-10）](#第二阶段p1-增强--前端--测试day-6-10)
- [五、耦合关系分析](#五耦合关系分析)
- [六、排期与里程碑](#六排期与里程碑)
- [七、提交方案与协作规范](#七提交方案与协作规范)

---

## 一、调整说明与分工原则

### 调整背景

1. **基于远程仓库**：分工方案以 `https://github.com/redmaplewww/psych-support-bot.git` 的 `main` 分支（`255169f`）为基线，不基于本地下载的测试副本
2. **P0 优先集中突破**：先集中火力清零所有 P0 安全/数据完整性硬伤，再分散力量做 P1 逻辑增强、前端补全和测试体系
3. **独立不阻塞项可提前穿插**：C 线前端（练习面板）完全不依赖 P0 修复，可在第一阶段用 1 人并行推进

### 分工原则

1. **P0 优先，集中突破**：Day 1-5 以 P0 修复为主轴，3 人全力投入，1 人并行做 C 线前端
2. **安全优先**：涉及安全边界的改动（风险分类、危机回复、诊断拦截）必须由项目主 review
3. **独立可测**：每条任务产出独立可测的交付物，不阻塞其他任务
4. **知识库冻结**：不新增知识条目，通过代码逻辑和 LLM 自身能力弥补覆盖盲区
5. **文件不冲突**：各任务主要改动文件尽量不重叠（冲突点见 [耦合关系](#五耦合关系分析)）

---

## 二、远程仓库基线确认

> 以下为 `origin/main`（`255169f`）的实际代码状态，与 PROJECT_ANALYSIS.md 中的审查结果逐项对照。

### 2.1 P0 问题在远程仓库中的实际状态

| P0 # | 问题 | 远程仓库实际状态 | 需修复 |
|---|---|---|---|
| #1 | `response_generator.py` fallback bug | ❌ 仍存在：`raise RuntimeError` 后 `state["fallback_used"] = True` 不可达 | ✅ 是 |
| #2 | Alembic 迁移不完整 | ❌ 仍存在：只有 2 个迁移脚本，`questionnaire_sessions` 表未建，`assessments` 缺 5 字段（但 ORM `models.py` 中已定义完整字段） | ✅ 是 |
| #3 | `safety_reviewer.py` 空心化 + 一刀切替换 | ❌ 仍存在：仅检测 prompt 泄露标记，检测到后整条回复被替换为固定兜底句 | ✅ 是 |
| #4 | `.env` 密钥泄露风险 | ✅ **已在远程修复**：`.gitignore` 已包含 `.env` 和 `.env.*` | ❌ 否 |
| #5 | 无诊断请求确定性拦截 | ❌ 仍存在：`intent.py` 无 `DIAGNOSIS_KEYWORDS` | ✅ 是 |
| #6 | High 风险回复硬编码不走 LLM | ❌ 仍存在：`crisis.py` 中 high 和 critical 都走 `build_crisis_reply` 纯模板 | ✅ 是 |
| #7 | 关键词冲突 | ❌ 仍存在：`intent.py` 的 `CRISIS_KEYWORDS` 含 "help me" 但 `rules.py` 的 `HIGH_RISK_KEYWORDS` 不含；两套体系独立维护 | ✅ 是 |
| #16 | Temperature 硬编码 0.0 | ❌ 仍存在：`factory.py` 中 `temperature=0.0` | ✅ 是 |

### 2.2 远程仓库已有资产

| 资产 | 远程路径 | 说明 |
|---|---|---|
| 前端 | `index.html`（根目录）+ `src/psych_support_bot/static/index.html` | 纯聊天 UI，无练习/评估/打卡面板 |
| 测试 | `tests/unit/`（11 个文件）+ `tests/integration/`（6 个文件）+ `tests/evals/`（4 个文件） | 已有基础测试覆盖 |
| CI | ❌ 不存在 | 远程仓库无 `.github/workflows/` 目录 |
| 练习 API | `src/psych_support_bot/api/routes/exercises.py` | ✅ `GET /v1/exercises` + `GET /v1/exercises/{tag}` 已就绪 |
| ORM 模型 | `src/psych_support_bot/infra/db/models.py` | ✅ `QuestionnaireSessionRecord` 和 `AssessmentRecord` 完整字段已定义 |
| Alembic | `migrations/versions/` 只有 2 个迁移 | ❌ ORM 与迁移脚本不一致 |

---

## 三、能力边界：能做与不能做

> **前提**：知识库内容冻结，不新增 `PSYCHOEDUCATION_MODULES`、`CBT_INTERVENTION_GUIDES`、`FOUNDATIONAL_KNOWLEDGE` 等知识条目。

### 3.1 能做（不碰知识库内容）

| 能力 | 对应任务 | 说明 | 依赖 |
|---|---|---|---|
| Fallback bug 修复 | P0-1 | 纯代码逻辑修复 | 无 |
| Alembic 迁移补全 | P0-2 | 数据库 schema 对齐 ORM | 无 |
| Safety reviewer 增强 | P0-3 | 改检测逻辑 + 截断清洗替代全量替换 | P0-5（诊断关键词定义后写检测） |
| Temperature 分温 | P0-16 | 按模式设置不同 temperature | 无 |
| 诊断请求拦截 | P0-5 | 加 `DIAGNOSIS_KEYWORDS` + 注入拒诊断 prompt | 无 |
| High 风险改走 LLM | P0-6 | 仅 critical 保留纯模板 | P0-1（fallback 先修好） |
| 关键词体系统一 | P0-7 | 合并 `intent.py` 和 `rules.py` 关键词 | P0-5（诊断拦截先加） |
| 练习工具面板 | C1 | 调已有 API，纯前端 | 无（不依赖 P0） |
| 评估问卷前端 | C2 | 后端量表逻辑已就绪 | 无 |
| 每日打卡界面 | C3 | 后端 API 已就绪 | 无 |
| 前端整体优化 | C4 | 响应式布局、Tab 导航、Markdown 渲染 | C1-C3 |
| 跨轮次矛盾检测 | B2.1 | 改 `consultation_planner.py` + `state.py` | 无（第二阶段） |
| 跨轮次风险追踪 | B2.2 | 改 `risk_classifier.py` 读 `memory_summary` | 无（第二阶段） |
| 质询合理性后置审查 | B2.3 | 改 `safety_reviewer.py` 增加质询检查 | P0-3 完成 |
| 否定检测语义化 | B4.2 | 改 `rules.py` 增加窗口距离检测 | P0-7 完成 |
| 耗竭检测精细化 | B4.3 | 改 `interview.py` 增加耗竭子分类 | 无 |
| "不专注"降级覆盖 | B1 | 只改 `TOPIC_KEYWORDS` 关键词字典 | 无 |
| 通用心理学指引 | B5 | 改 `templates.py` 中 `build_context_prompt` 一行 | 无 |
| 单元测试补全 | D1 | 测试修复后的行为 | P0 完成 |
| 评估场景补全 | D2 | 加测试用例 | 无 |
| CI 集成 | D3 | GitHub Actions | D1 |

### 3.2 不能做（依赖知识库内容补全）

| 能力 | 原因 | 降级方案 |
|---|---|---|
| `focus` 主题专属干预指南 | 需在 `CBT_INTERVENTION_GUIDES` 新增条目 | 关键词归入 `procrastination`/`motivation` + LLM 自身能力 |
| `focus` 主题专属基础概念 | 需在 `FOUNDATIONAL_KNOWLEDGE` 新增条目 | 同上 |
| 个性化练习推荐（完整版） | 需知识库中练习推荐映射规则 | 可做代码骨架（加字段 + 记录拒达），无推荐算法 |
| 中文心理教育资源 | 需专业中文心理教育内容编写 | 后端已锁定中文输出，LLM 自行翻译 |

---

## 四、两阶段分工详述

### 第一阶段：P0 必须修复（Day 1-5）

> **核心目标**：清零所有 P0 安全/数据完整性硬伤，保障上线安全门槛。
> **人员分配**：3 人投入 P0 修复，1 人并行做 C 线前端（不阻塞 P0，不被 P0 阻塞）。

#### P0 任务清单与分配

| 人员 | 任务 | P0 # | 改动文件 | 验收标准 | 耦合 |
|---|---|---|---|---|---|
| **成员 1** | P0-1: Fallback bug 修复 | #1 | `ai/nodes/response_generator.py` | LLM 调用失败时返回兜底回复，不 500 | 🔴 串行头（B3.3 依赖） |
| **成员 1** | P0-6: High 风险改走 LLM | #6 | `ai/nodes/response_generator.py` + `ai/safety/crisis.py` + `ai/prompts/templates.py` | high 级别走 LLM 生成共情回复，仅 critical 纯模板 | 🔴 串行（依赖 P0-1 先合并） |
| **成员 2** | P0-5: 诊断请求拦截 | #5 | `ai/routers/intent.py` + `ai/prompts/templates.py` | 用户问"我是不是抑郁症"时不给诊断性回复 | 🔴 串行头（P0-7/B3.2 依赖） |
| **成员 2** | P0-7: 关键词体系统一 | #7 | `ai/routers/intent.py` + `ai/safety/rules.py` | "help me" 等关键词在两套体系中分类一致 | 🔴 串行（依赖 P0-5 先合并） |
| **成员 2** | P0-3: Safety reviewer 增强 | #3 | `ai/nodes/safety_reviewer.py` | 诊断语言被拦截清洗，正常回复不被误杀 | 🔴 串行（依赖 P0-5 先合并） |
| **成员 3** | P0-2: Alembic 迁移补全 | #2 | `migrations/versions/` 新增脚本 | `alembic upgrade head` 在空 PostgreSQL 上无报错 | 🟢 独占 |
| **成员 3** | P0-16: Temperature 分温 | #16 | `infra/llm/factory.py` | 相同消息连续 3 轮回复不完全相同 | 🟢 独占 |
| **成员 3** | D2: 评估场景设计 | — | `tests/evals/cases.json` | 补充躁狂筛查/OCD/焦虑+失眠共病场景 | 🟢 独占 |
| **成员 4** | C1: 练习工具面板 | P1 #8 | `src/psych_support_bot/static/index.html` | 面板可见，4 个按钮可点击，调 API 获取练习步骤 | 🟢 独占（不碰 AI 逻辑） |

#### P0 串行依赖链

```
成员 1 的串行链（response_generator.py 同文件同函数）:
  P0-1 (Day 1) → P0-6 (Day 2-3) → [等第二阶段] B3.3 (Day 6+)

成员 2 的串行链（intent.py / safety_reviewer.py / rules.py 同文件）:
  P0-5 (Day 1-2) → P0-7 (Day 3) → P0-3 (Day 4-5) → [等第二阶段] B2.3/B4.2

成员 3 的独立任务:
  P0-2 (Day 1-2) → P0-16 (Day 2-3) → D2 场景设计 (Day 3-5)

成员 4 的独立任务:
  C1 (Day 1-5) → [等第二阶段] C2/C3/C4
```

#### 第一阶段每日进度

```
Day 1:
  成员 1: P0-1 fallback bug 修复 → 提 PR → review → 合并到 dev
  成员 2: P0-5 诊断拦截（加 DIAGNOSIS_KEYWORDS + 拒诊断 prompt）→ 提 PR → review → 合并
  成员 3: P0-2 Alembic 迁移补全（questionnaire_sessions 表 + assessments 5 字段）→ 提 PR
  成员 4: C1.1-C1.2 练习面板 + 按钮调 API → 提 PR

Day 2:
  成员 1: P0-6 High 风险改走 LLM（基于 P0-1 已合并的 dev 重新切分支）
  成员 2: 等 P0-5 合并后 → P0-7 关键词统一（基于 P0-5 已合并的 dev 重新切分支）
  成员 3: P0-16 Temperature 分温 → 提 PR
  成员 4: C1.3-C1.4 练习完成反馈 + 按钮映射

Day 3:
  成员 1: P0-6 继续完成 → 提 PR
  成员 2: 等 P0-7 合并后 → P0-3 safety_reviewer 增强（基于 P0-7 已合并的 dev 切分支）
  成员 3: D2 评估场景设计（补充 cases.json + 测试用例）
  成员 4: C1 收尾测试 → 提 PR

Day 4-5:
  成员 1: 等 P0-6 合并 → 支援成员 2 的 P0-3 或做 D1 单元测试准备
  成员 2: P0-3 完成 → 提 PR → review → 合并 → P0 全部清零
  成员 3: D2 完成 → 支援 D1 单元测试编码（基于 P0 修复行为）
  成员 4: C1 合并 → C1 完成
```

---

### 第二阶段：P1 增强 + 前端 + 测试（Day 6-10）

> **前置条件**：第一阶段 P0 全部清零，`dev` 分支包含所有 P0 修复。
> **人员分配**：4 人分散到 B/C/D 线。

#### 第二阶段任务清单与分配

| 人员 | 任务 | 改动文件 | 验收标准 | 耦合 | 依赖 |
|---|---|---|---|---|---|
| **成员 1** | B2.1 跨轮次矛盾检测 | `ai/nodes/consultation_planner.py` + `ai/schemas/state.py` | 前后轮矛盾时 `loop_hint` 含矛盾提示 | 🟢 独占 | 无 |
| **成员 1** | B2.2 跨轮次风险追踪 | `ai/nodes/risk_classifier.py` | 连续两轮 elevated → 第二轮自动标 high | 🟢 独占 | 无 |
| **成员 1** | B2.3 质询合理性后置审查 | `ai/nodes/safety_reviewer.py` | 不允许质询的场景下质询性回复被标记降级 | 🔴 串行 | P0-3 已合并 |
| **成员 2** | B1 "不专注"关键词降级 | `ai/knowledge/index.py` | `detect_topics("总是走神")` 返回含 `procrastination` | 🟢 独占 | 无 |
| **成员 2** | B5 通用心理学指引 | `ai/prompts/templates.py` `build_context_prompt` 函数 | 无知识命中时 LLM 仍给出有框架的回复 | 🟡 协调 | 与 B4.2 不同函数 |
| **成员 2** | B4.2 否定检测语义化 | `ai/safety/rules.py` | "以前想过自杀但现在不想了"不被直接降为 elevated | 🟡 协调 | P0-7 已合并 |
| **成员 2** | B4.3 耗竭检测精细化 | `ai/interview.py` | 用户说"身体累"和"心累"触发不同策略 | 🟢 独占 | 无 |
| **成员 3** | C2 评估问卷前端 | `static/index.html` 或新增 `static/assessment.html` | 3 个量表入口可见可点击，问卷交互完整 | 🟢 独占 | 无 |
| **成员 3** | C3 每日打卡界面 | 同上 | 4 个滑块可操作，提交后显示成功 + 趋势图 | 🟢 独占 | 无 |
| **成员 3** | C4 前端整体优化 | `static/index.html` | 响应式布局 + Tab 切换 + Markdown 渲染 | 🟢 独占 | C1+C2+C3 |
| **成员 4** | D1 单元测试补全 | `tests/` 新增文件 | P0 修复行为 + B 线增强行为有测试覆盖 | 🟢 独占 | P0 完成 |
| **成员 4** | D3 CI 集成 | `.github/workflows/ci.yml` | PR 提交时自动运行 pytest + ruff + mypy | 🟢 独占 | D1 有测试 |

#### 第二阶段串行依赖链

```
成员 1 的串行链:
  B2.1 (Day 6-7) → B2.2 (Day 7-8) → B2.3 (Day 8-9)
  B2.3 依赖 P0-3 已合并（第一阶段已完成 ✅）

成员 2 的串行链:
  B1 (Day 6, ~1h) → B5 (Day 6, ~30min) → B4.2 (Day 7-8) → B4.3 (Day 8-9)
  B4.2 依赖 P0-7 已合并（第一阶段已完成 ✅）

成员 3 的串行链:
  C2 (Day 6-7) → C3 (Day 8-9) → C4 (Day 9-10)
  C4 依赖 C1+C2+C3（C1 第一阶段已完成 ✅，C2/C3 本阶段完成）

成员 4 的串行链:
  D1 (Day 6-8) → D3 (Day 9-10)
  D1 依赖 P0 完成（第一阶段已完成 ✅）
```

#### B 线可选任务（有余力时做）

| 任务 | 改动文件 | 验收标准 | 依赖 |
|---|---|---|---|
| B3.1 GraphState 加字段 | `ai/schemas/state.py` | `exercise_history` / `refusal_history` 字段可读写 | P0-1 已合并 |
| B3.2 route_intent 拒达记录 | `ai/nodes/intent_router.py` + `ai/routers/intent.py` | 拒达时记录被拒达的练习类型 | B3.1 |
| B3.3 response_generator 注入 | `ai/nodes/response_generator.py` | LLM 不再重复推荐已拒达的同类练习 | B3.2 + P0-1 + P0-6 |
| B3.5 daily_steps 填充 | `domain/plans/templates.py` | 计划模板含 `daily_steps` | 无 |
| B3.6 周报异常检测 | `domain/reports/trends.py` | 周报输出含"需要关注"标记 | 无 |

---

## 五、耦合关系分析

### 5.1 跨线文件耦合矩阵

| 共同文件 | P0 阶段 | P1 阶段 | 耦合类型 | 缓解策略 |
|---|---|---|---|---|
| `ai/nodes/response_generator.py` | P0-1 (fallback) + P0-6 (high 走 LLM) | B3.3 (拒达上下文注入) | **🔴 写写耦合** | P0-1 → P0-6 串行合并；B3.3 等第二阶段 |
| `ai/nodes/safety_reviewer.py` | P0-3 (增强检测) | B2.3 (质询检查) + D1.2 (测试) | **🔴 写写耦合** | P0-3 → B2.3 → D1.2 严格串行 |
| `ai/routers/intent.py` | P0-5 (诊断关键词) + P0-7 (关键词统一) | B3.2 (拒达记录) | **🔴 写写耦合** | P0-5 → P0-7 串行；B3.2 等第二阶段 |
| `ai/safety/rules.py` | P0-7 (关键词统一) | B4.2 (语义否定检测) | **🟡 写写耦合** | P0-7 先合并，B4.2 后合并 rebase |
| `ai/prompts/templates.py` | P0-5 (拒诊断 prompt) + P0-6 (危机 prompt) | B5 (`build_context_prompt` 不同函数) | **🟡 不同函数** | 可并行，后合并方 rebase |
| `ai/schemas/state.py` | — | B2.1 加字段 + B3.1 加字段 | B 线独占 | 无冲突 |
| `ai/nodes/consultation_planner.py` | — | B2.1 改矛盾检测 | B 线独占 | 无冲突 |
| `ai/nodes/risk_classifier.py` | — | B2.2 改跨轮次追踪 | B 线独占 | 无冲突 |
| `ai/interview.py` | — | B4.3 改耗竭子分类 | B 线独占 | 无冲突 |
| `infra/llm/factory.py` | P0-16 (temperature) | — | P0 独占 | 无冲突 |
| `migrations/versions/` | P0-2 新增迁移 | — | P0 独占 | 无冲突 |
| `static/index.html` | C1 (成员 4) | C2/C3/C4 (成员 3) | C 线独占 | 无冲突 |
| `tests/` 目录 | D2 场景设计 | D1 单元测试 | D 线独占 | 无冲突 |
| `ai/knowledge/index.py` | — | B1 改 `TOPIC_KEYWORDS` | B 线独占 | 无冲突 |
| `.github/workflows/` | — | D3 CI 独占 | D 线独占 | 无冲突 |

### 5.2 耦合严重度分级

| 严重度 | 含义 | 涉及文件 | 涉及任务 | 处理方式 |
|---|---|---|---|---|
| 🔴 高 | 同文件同函数改动，必须串行 | `response_generator.py` | P0-1 → P0-6 → B3.3 | 严格按顺序逐个合并 |
| 🔴 高 | 同文件同函数改动，必须串行 | `safety_reviewer.py` | P0-3 → B2.3 → D1.2 | 严格按顺序逐个合并 |
| 🔴 高 | 同文件同函数改动，必须串行 | `intent.py` | P0-5 → P0-7 → B3.2 | 严格按顺序逐个合并 |
| 🟡 中 | 同文件不同函数，可并行但需 rebase | `templates.py` | P0-5/P0-6 + B5 | 不同函数，后合并方 rebase |
| 🟡 中 | 同文件不同逻辑，可并行但需 rebase | `rules.py` | P0-7 + B4.2 | 不同代码段，后合并方 rebase |
| 🟢 低 | 不同文件或只读 | 各线独占文件 | — | 无需协调 |

---

## 六、排期与里程碑

### 6.1 四人分配方案

| 人员 | Day 1-2 | Day 3-5 | Day 6-8 | Day 8-10 |
|---|---|---|---|---|
| **成员 1** | P0-1 (fallback) | P0-6 (high 走 LLM) | B2.1+B2.2 (跨轮次) | B2.3 (质询审查) |
| **成员 2** | P0-5 (诊断拦截) | P0-7 (关键词统一) → P0-3 (safety reviewer) | B1+B5 (focus 降级 + 通用指引) | B4.2+B4.3 (否定检测 + 耗竭) |
| **成员 3** | P0-2 (Alembic) → P0-16 (temperature) | D2 (评估场景设计) | C2 (评估问卷 UI) | C3+C4 (打卡 + 前端优化) |
| **成员 4** | C1.1-C1.2 (练习面板) | C1.3-C1.4 (练习完成反馈) | D1 (单元测试) | D3 (CI 集成) |

### 6.2 并行度分析

```
Day 1-2（第一阶段）: 四线全并行（4/4 人开工）
  成员 1: P0-1 fallback bug           ── 🟢 独立
  成员 2: P0-5 诊断拦截                ── 🟢 独立
  成员 3: P0-2 Alembic + P0-16 temp    ── 🟢 独立
  成员 4: C1 练习面板                   ── 🟢 独立
  耦合: 无跨线耦合

Day 3-5（第一阶段）: 串行依赖启动
  成员 1: P0-6 high 走 LLM             ── 🔴 依赖 P0-1 已合并
  成员 2: P0-7 关键词统一 → P0-3 reviewer ── 🔴 依赖 P0-5 已合并
  成员 3: D2 评估场景设计               ── 🟢 独立
  成员 4: C1 收尾                       ── 🟢 独立
  耦合: 成员 1/2 有串行依赖

Day 6-8（第二阶段）: P0 清零后四线分散
  成员 1: B2.1+B2.2 跨轮次              ── 🟢 独立
  成员 2: B1+B5 focus 降级              ── 🟢 独立
  成员 3: C2 评估问卷 UI                ── 🟢 独立
  成员 4: D1 单元测试                   ── 🟢 独立（依赖 P0 已完成）
  耦合: 无跨线耦合

Day 8-10（第二阶段）: 串行依赖 + 收尾
  成员 1: B2.3 质询审查                 ── 🔴 依赖 P0-3 已合并
  成员 2: B4.2 否定检测 + B4.3 耗竭      ── 🟡 依赖 P0-7 已合并
  成员 3: C3+C4 打卡 + 前端优化          ── 🟢 依赖 C1+C2 完成
  成员 4: D3 CI 集成                    ── 🟢 依赖 D1 完成
```

### 6.3 关键路径

```
关键路径 1（安全线）:
  P0-1 (Day 1) → P0-6 (Day 2-3) → B3.3 (Day 8+, 可选)
  总长: 3 天（B3.3 不计入关键路径）

关键路径 2（拦截线）:
  P0-5 (Day 1) → P0-7 (Day 3) → P0-3 (Day 4-5) → B2.3 (Day 8-9)
  总长: 9 天

关键路径 3（前端线）:
  C1 (Day 1-5) → C2 (Day 6-7) → C3 (Day 8-9) → C4 (Day 9-10)
  总长: 10 天

关键路径 4（测试线）:
  D2 场景设计 (Day 3-5) → D1 单元测试 (Day 6-8) → D3 CI (Day 9-10)
  总长: 8 天

整体关键路径: max(3, 9, 10, 8) = 10 天 → M2 里程碑
```

### 6.4 里程碑

```
M1 (Day 5)  : P0 全部清零 + 练习面板可用
  ├── P0-1 ~ P0-7 全部修复并合并到 dev
  ├── P0-16 Temperature 分温完成
  ├── P0-2 Alembic 迁移补全
  └── C1 练习工具面板可用

M2 (Day 10) : P1 增强 + 前端补全 + 测试 CI
  ├── B1/B5 focus 降级 + 通用指引
  ├── B2.1-B2.3 跨轮次质询
  ├── B4.2/B4.3 否定检测 + 耗竭精细化
  ├── C2/C3/C4 评估问卷 + 打卡 + 前端优化
  ├── D1 单元测试补全
  └── D3 CI 集成

M3 (Day 12) : 端到端验证 → 合并到 main
```

### 6.5 交付物清单

| 里程碑 | 交付物 | 能做/降级 |
|---|---|
| M1 | 安全修复 PR + 练习面板 + Alembic 迁移 + Temperature 分温 | ✅ 全部能做 |
| M2 | 评估问卷 UI + 打卡 + 前端优化 + 跨轮次质询 + focus 降级 + 单元测试 + CI | ✅ 全部能做（focus 为降级版） |
| M3 | 端到端验证 → main | ✅ 能做 |

---

## 七、提交方案与协作规范

### 7.1 分支命名规范

```
fix/p0-<brief>           # P0 修复，如 fix/p0-fallback-bug
feat/<scope>-<brief>     # 新功能，如 feat/exercise-panel
test/<scope>-<brief>     # 测试，如 test/unit-p0
```

### 7.2 提交流程：分级合并策略

> **核心原则**：本项目存在多处同文件同函数的串行依赖，**不能各自独立 PR 独立合并**。

#### 第一档：独立 PR，可直接合并（🟢 低耦合，不同文件）

> 这些任务改的文件和其他线完全不重叠，可以各自建 PR、独立合并到 `dev`，互不影响。

| 任务 | 文件 | 条件 |
|---|---|---|
| P0-2 (Alembic 迁移) | `migrations/versions/` | 独占 |
| P0-16 (temperature) | `infra/llm/factory.py` | 独占 |
| C1-C4 (全部前端) | `static/index.html` | 独占 |
| B1 (focus 关键词) | `ai/knowledge/index.py` | 独占 |
| B2.1 (跨轮次矛盾) | `consultation_planner.py` + `state.py` | 独占 |
| B2.2 (跨轮次风险) | `risk_classifier.py` | 独占 |
| B4.3 (耗竭检测) | `ai/interview.py` | 独占 |
| B5 (通用指引) | `templates.py` 的 `build_context_prompt` 函数 | 独占函数 |
| D2 (评估场景) | `tests/evals/cases.json` | 独占 |
| D3 (CI 集成) | `.github/workflows/` | 独占 |

#### 第二档：串行 PR，按依赖顺序合并（🔴 高耦合，同文件同函数）

> 后一个 PR 必须**从前一个 PR 合并后的 `dev` 重新切分支**。

| 合并顺序 | 任务 | 文件 | 前置条件 |
|---|---|---|---|
| 1️⃣ 先合并 | P0-1 (fallback bug) | `response_generator.py` | 无 |
| 2️⃣ 后合并 | P0-6 (high 走 LLM) | `response_generator.py` | P0-1 已合并 |
| 3️⃣ 最后合并 | B3.3 (拒达上下文注入) | `response_generator.py` | P0-1 + P0-6 已合并 |
| 1️⃣ 先合并 | P0-5 (诊断拦截) | `intent.py` | 无 |
| 2️⃣ 后合并 | P0-7 (关键词统一) | `intent.py` + `rules.py` | P0-5 已合并 |
| 3️⃣ 最后合并 | B3.2 (拒达记录) | `intent.py` | P0-5 + P0-7 已合并 |
| 1️⃣ 先合并 | P0-3 (safety reviewer 增强) | `safety_reviewer.py` | P0-5 已合并 |
| 2️⃣ 后合并 | B2.3 (质询审查) | `safety_reviewer.py` | P0-3 已合并 |
| 1️⃣ 先合并 | P0-7 (关键词统一) | `rules.py` | 无 |
| 2️⃣ 后合并 | B4.2 (否定检测) | `rules.py` | P0-7 已合并 |

#### 第三档：协调 PR，可并行但需 rebase（🟡 中耦合，同文件不同函数）

| 任务对 | 文件 | 协调方式 |
|---|---|---|
| P0-5/P0-6 + B5 | `ai/prompts/templates.py` | P0 改现有函数，B5 改 `build_context_prompt`（不同函数），可并行，后合并方 rebase |
| P0-7 + B4.2 | `ai/safety/rules.py` | P0 统一关键词，B 加语义检测（不同代码段），后合并方 rebase |

#### 具体操作流程

```
第一档独立任务流程（以 P0-2 为例）：

1. git checkout dev
2. git pull origin dev
3. git checkout -b fix/p0-alembic-migrate
4. ...开发...
5. git add migrations/versions/
6. git commit -m "fix(A): add questionnaire_sessions table + assessments missing fields"
7. git push origin fix/p0-alembic-migrate
8. 在 GitHub 上创建 PR: fix/p0-alembic-migrate → dev
9. 等待 review → merge

第二档串行任务流程（以 P0-6 为例，依赖 P0-1 已合并）：

1. 确认 P0-1 的 PR 已合并到 dev
2. git checkout dev
3. git pull origin dev              # 拿到 P0-1 的改动
4. git checkout -b fix/p0-high-risk-llm   # 基于最新 dev 切分支
5. ...开发 P0-6...
6. git push origin fix/p0-high-risk-llm
7. 创建 PR: fix/p0-high-risk-llm → dev
8. PR 标题标注: [depends-on P0-1 merged]
9. 等待 review + 合并
```

### 7.3 PR 规范

- 每个 PR 标注对应工作线（P0/P1/C/D）和报告序号（如 `P0 #1`）
- 涉及安全边界的 PR 必须由项目主或指定安全审查人 review
- 涉及前端界面的 PR 必须附截图
- 涉及 AI 逻辑的 PR 必须附 evals 测试结果
- **第二档串行 PR 必须在描述中标注前置依赖**：`Depends on: P0-1 merged to dev`
- **禁止跨档混合并**：不要在同一个 PR 中混入第一档和第二档的改动

### 7.4 冲突协调原则

1. **P0 优先**：安全修复优先合并，其他线基于 P0 结果继续
2. **不同文件并行**：各任务尽量改不同文件，减少 merge conflict
3. **同文件协调**：同文件改动由后改方负责 rebase 和冲突解决
4. **每日同步**：各成员每日同步进度，及时调整依赖
5. **耦合任务标记**：PR 标题标注 `[blocked-by P0-3]` 等标记，明确等待关系
6. **dev 分支保护**：`dev` 分支设为 protected，禁止直接 push，必须通过 PR 合并
7. **main 分支保护**：`main` 只从 `dev` 合并，且需全员 review 通过

### 7.5 知识库冻结约定

- **不新增**：`PSYCHOEDUCATION_MODULES`、`CBT_INTERVENTION_GUIDES`、`FOUNDATIONAL_KNOWLEDGE`、`ACT_EXERCISES`、`DBT_EXERCISES` 等知识条目
- **可改的**：`TOPIC_KEYWORDS` 关键词字典（只加触发词，不新增知识内容）、`build_context_prompt` 函数逻辑、`templates.py` 中的 prompt 工程文字
- **如未来解冻**：需由具备专业心理学背景的成员审核内容，新增 PR 标注 `[knowledge-content]` 标签

---

*本分工方案基于远程仓库 `origin/main`（`255169f`）实际源码审查制定，P0 优先集中突破，清零后再分散到 P1 增强/前端/测试。如需调整请协商后更新。*
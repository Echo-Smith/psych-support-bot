# 安全发布清单

> 每次发布前必须完整执行本清单。所有门禁必须通过，无例外。

---

## 1. 自动化安全回归（CI 门禁）

### 1.1 A 层 — 确定性正则单元测试

```bash
uv run pytest tests/unit/test_content_quality.py -v --tb=short
```

- **通过标准**：100% 通过（0 失败）
- **覆盖范围**：
  - 红线合规（病理性归因、主观体验否定、过度病理化标签）
  - 语言锁（中文输入→中文输出，英文输入→英文输出）
  - 三段式结构标签（`[Reflection]` / `[Exploration]` / `[Action]`）
  - 危机模式结构豁免（`mode=crisis` 跳过结构检查）
- **失败处理**：阻断发布。定位失败的用例编号，修复后重测。

### 1.2 B 层 — 端到端 LLM 评测

```bash
uv run pytest tests/evals/ -v --tb=short -x
```

- **通过标准**：100% 通过（0 失败）
- **覆盖范围**：22 个用例，覆盖 support / crisis / assessment / intervention 等模式
- **4 维度检查**：
  1. Routing：mode + risk 与期望匹配
  2. Redline：回复不含红线违规模式
  3. Structure：回复含三段式标签（crisis 模式豁免）
  4. Language：回复语言与用户输入语言一致
- **已知非确定性**：LLM 输出可能偶发结构/语言不稳定。若同一用例连续 3 次运行均失败，视为确定性缺陷，阻断发布。

### 1.3 红线正则零违规确认

```bash
uv run python -c "
from psych_support_bot.evals.runner import run_eval_cases
results = run_eval_cases()
violations = [r for r in results if not r['redline_pass']]
print(f'Redline violations: {len(violations)}')
for v in violations:
    print(f'  FAIL: {v[\"name\"]}')
"
```

- **通过标准**：0 违规

---

## 2. 风险评估门禁（人工确认）

### 2.1 危机确定性回复模板

- [ ] `src/psych_support_bot/ai/safety/crisis.py` 中的 `build_crisis_reply()` 未被修改，或修改已经过安全审查
- [ ] crisis 模式下 `risk_level=critical` 时跳过 LLM，直接使用安全模板
- [ ] crisis 模式下 `risk_level=high` 时走 LLM 但注入 `build_crisis_safety_prompt()`

### 2.2 跨轮风险升级（B2.2）

- [ ] `risk_classifier.py` 中 `_has_previous_elevated()` 逻辑未被移除或降级
- [ ] 连续两轮 elevated → 自动升级 high 的路径未被破坏
- [ ] 评测用例中 `zh_cumulative_elevated` 场景验证通过

### 2.3 风险关键词覆盖

- [ ] `src/psych_support_bot/ai/safety/rules.py` 中 `CRISIS_KEYWORDS` 未缩减
- [ ] `ELEVATED_RISK_REGEX_PATTERNS_ZH` 正则组未缩减
- [ ] 中文同义变体覆盖（如"没意思" vs "没意义"）仍然有效

### 2.4 安全审查节点

- [ ] `safety_reviewer.py` 的 `_sanitize_text()` 仍然按行分割、移除违规句、保留非违规部分
- [ ] 截断全空时 fallback 分场景仍然有效（高危→crisis 模板，普通→grounding 短语）
- [ ] `LEAK_MARKERS` 未被清空或缩减

---

## 3. 功能回归门禁

### 3.1 核心 API 可用性

- [ ] `GET /health` 返回 200
- [ ] `GET /system/info` 返回模型名称等信息
- [ ] `POST /v1/conversations/respond` 能正常走完 LangGraph 全流程并返回回复
- [ ] 前端 `static/index.html` 加载后聊天 Tab 可正常发送和接收消息

### 3.2 评估量表 API

- [ ] `GET /v1/assessments/questionnaires` 返回 PHQ-9 / GAD-7 / ISI 量表列表
- [ ] `POST /v1/assessments/sessions` 能创建评估会话
- [ ] `POST /v1/assessments/sessions/{id}/answers` 能提交答案
- [ ] `POST /v1/assessments/sessions/{id}/complete` 能完成并返回结果

### 3.3 每日打卡 API

- [ ] `POST /v1/checkins?user_id=xxx` 能正常提交打卡
- [ ] 同日重复提交被拦截

### 3.4 练习工具 API

- [ ] `GET /v1/exercises/{tag}` 返回练习步骤数据

---

## 4. 可观测性门禁

- [ ] Langfuse 已配置（`LANGFUSE_PUBLIC_KEY` 和 `LANGFUSE_SECRET_KEY` 非 空）
- [ ] `GET /system/info` 的 `tracing.configured` 返回 `true`
- [ ] 发送一条对话后，Langfuse 后台能看到 `conversation_graph.invoke` 根 span
- [ ] 根 span 下能看到 `llm.invoke` 子 span（非 fallback 路径）
- [ ] `flush_langfuse()` 在 app shutdown 时正常执行（无未刷新的 trace 丢失）

---

## 5. 非协商规则确认

以下规则不可违反，违反则阻断发布：

- [ ] **风险分类不可被绕过**：对话流程必须先经过 `risk_classifier` 节点
- [ ] **高危用户不可留在普通模式**：`needs_crisis_mode=True` 时 `mode` 必须设为 `crisis`
- [ ] **不可仅依赖单一非结构化 prompt 做安全决策**：风险分类基于正则+关键词，不依赖 LLM 判断
- [ ] **每个关键 AI 步骤必须有结构化输出**：`GraphState` 各字段有类型约束
- [ ] **任何输出包含病理性归因或主观体验否定应阻止发布**：A 层 + B 层均验证通过
- [ ] **高风险召回优先于对话优雅性**：宁可误判升级，不可漏判降级

---

## 6. 发布流程

1. 执行 §1 自动化测试（全部通过）
2. 执行 §2 人工确认（全部勾选）
3. 执行 §3 功能回归（全部通过）
4. 执行 §4 可观测性确认（全部通过）
5. 确认 §5 非协商规则（无违反）
6. 填写发布记录：
   - 版本号：
   - 发布日期：
   - 变更摘要：
   - 测试执行人：
   - 人工审查人：

---

## 附录：快速执行命令

```bash
# 一键跑完所有自动化测试
uv run pytest tests/unit/test_content_quality.py tests/evals/ -v --tb=short

# 验证 Langfuse 配置
uv run python -c "from psych_support_bot.infra.telemetry.tracing import tracing_config; print(tracing_config())"

# 启动服务做功能回归
uv run uvicorn psych_support_bot.app:app --reload --port 8000
```

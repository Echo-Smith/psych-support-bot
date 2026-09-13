"""K2 LLM 语义提取器：D2/D3/D5 + 语义 D1 的 belief 候选提取。

词锚表（anchors.py）在此兑现召回价值：allowed keys 全部来自锚点表与
主题闭集，双语短语进 prompt 降漏检；最终判定由 LLM 给出，锚点命中
只是召回辅助（知识提炼 §5 消歧规则）。

纪律（全部代码级，不靠 prompt 自觉）：
- allowed keys 闭集：dimension→key 白名单校验，越界即丢；
- distortion.* 永不进 allowed list（与仓储层 ValueError 双保险）；
- 提取产出经 record_claim 落库 → source=extracted 强制 L4（红线不变）；
- 危机轮不调用（高危内容不入画像层，也不花这次 LLM 钱）；
- 节流是 worker 纪律不是成本上限（P2：成本暂不设上限、全量统计）——
  触发条件：练习/测评事件 或 主题命中≥2 或 每 N 轮且有 ≥1 主题命中；
- fail-open 双层兜底：LLM 失败/解析失败只记 error 统计，绝不阻断对话。
"""

from __future__ import annotations

import json
import logging
import time

from sqlalchemy.orm import Session

from psych_support_bot.ai.knowledge.index import TOPIC_KEYWORDS, detect_topics
from psych_support_bot.ai.profile.anchors import all_anchors
from psych_support_bot.ai.profile.display_dict import friendly_label
from psych_support_bot.infra.config.settings import get_settings
from psych_support_bot.infra.db.profile_repositories import (
    list_active_beliefs,
    record_claim,
    record_extraction_stats,
)
from psych_support_bot.infra.llm.generation import generate_profile_extraction

logger = logging.getLogger(__name__)

# dimension → allowed belief keys（闭集）。D3 只收非 distortion 锚
# （identify_only 红线在 allowed list 层就不给入口）。
_ALLOWED_D1: frozenset[str] = frozenset(TOPIC_KEYWORDS)
_ALLOWED_ANCHOR_DIMS = ("D2", "D3", "D5")
ALLOWED_KEYS: dict[str, frozenset[str]] = {
    "D1": _ALLOWED_D1,
    "D2": frozenset(a.key for a in all_anchors() if a.dimension == "D2"),
    "D3": frozenset(a.key for a in all_anchors() if a.dimension == "D3" and not a.identify_only),
    "D5": frozenset(a.key for a in all_anchors() if a.dimension == "D5"),
}

_SYSTEM_PROMPT = (
    "You are the profile-extraction module of a psych-support bot: a quiet, "
    "cautious observer maintaining a belief stream about the user. Output "
    'STRICT JSON only, no prose, no code fences: {"claims": [{"dimension": '
    '"D1"|"D2"|"D3"|"D5", "key": "<from the allowed list>", "claim_zh": '
    '"<one clinical-neutral observation sentence in Chinese>", "confidence": '
    '<0.0-1.0>, "relation": "supports|contradicts"}]}\n'
    "Rules:\n"
    '- At most 3 claims. Output {"claims": []} when nothing is solid — '
    "absence is a valid, often correct answer.\n"
    '- "key" MUST come from the allowed list of that dimension. Never invent keys.\n'
    "- Never output keys starting with 'distortion.', never diagnose, never "
    "label personality, never pathologize normal grief or low motivation.\n"
    "- Mechanism priority: when the user describes HOW the problem keeps going "
    "(avoiding/escaping situations, rehearsing to feel safe, struggling to "
    "eliminate feelings before acting, replaying the past), ALSO consider the "
    "matching D3 mechanism key — a D1 topic and its D3 mechanism may coexist; "
    "do not collapse mechanism evidence into the topic claim alone.\n"
    "  Example: user says 例会我不敢说话，汇报前一晚把每句话排练好多遍，讲到一半找借口溜了 "
    '→ output BOTH {"dimension":"D1","key":"social_anxiety"} AND '
    '{"dimension":"D3","key":"avoidance_maintenance.social"} (confidence ~0.8 each). '
    "If you only output the topic when the user clearly described maintaining "
    "behaviors, you missed the more useful claim.\n"
    "- If the message is a crisis/self-harm context: output empty claims "
    "(the safety channel handles it; profile stores nothing).\n"
    "- If the user is recounting knowledge/methods ('科普说失眠要刺激控制') "
    "rather than describing their own state: empty claims.\n"
    "- Sustain talk ('都试过了，没用') is ambivalence about methods, NOT a "
    "topic statement and NOT resistance — do not invent claims for it.\n"
    "- Emotion words inside assessment context ('焦虑量表没测准') or inside "
    "exercise-completion narration ('做完呼吸后心慌少了') are not topic "
    "statements: no D1 claims for them.\n"
    '- Use "relation": "contradicts" only when this turn genuinely conflicts '
    "with one of the listed current beliefs; otherwise supports.\n"
    "- claim_zh must be an observation ('用户在社交场合常想先躲开'), never an "
    "identity label ('用户是回避型人格')."
)


def _anchor_prompt_lines() -> list[str]:
    lines: list[str] = []
    for key in sorted(_ALLOWED_D1):
        label = friendly_label(key) or ""
        lines.append(f"D1 {key} = {label}")
    for anchor in all_anchors():
        if anchor.dimension not in _ALLOWED_ANCHOR_DIMS:
            continue
        sample = anchor.en_phrases[0] if anchor.en_phrases else (anchor.zh_phrases[0] if anchor.zh_phrases else "")
        lines.append(f"{anchor.dimension} {anchor.key} = {friendly_label(anchor.key) or ''} | e.g. {sample}")
    return lines


def _beliefs_prompt_lines(session: Session, user_id: str) -> list[str]:
    lines: list[str] = []
    for belief in list_active_beliefs(session, user_id):
        try:
            value = json.loads(belief.value_json or "{}")
        except (TypeError, ValueError):
            value = {}
        lines.append(
            f"- {belief.dimension} {belief.key} (layer={belief.layer}, "
            f"confidence={belief.confidence:.2f}, value={json.dumps(value, ensure_ascii=False)})"
        )
    return lines or ["- (none yet)"]


def build_extraction_payload(user_text: str, session: Session, user_id: str) -> str:
    """组装提取 payload：allowed keys + 当前信念 + 本轮用户话术。"""
    return (
        "[Allowed keys]\n"
        + "\n".join(_anchor_prompt_lines())
        + "\n\n[Current beliefs]\n"
        + "\n".join(_beliefs_prompt_lines(session, user_id))
        + "\n\n[User utterance this turn]\n"
        + (user_text or "").strip()
    )


def parse_extraction_json(raw: str) -> list[dict]:
    """解析 LLM 输出 → 校验后的 claim dict 列表；任何畸形输入返回 []。

    校验：dimension/key 闭集、relation 合法、confidence 钳位 [0,1]、
    distortion key 丢弃（与仓储层双保险）、总量 ≤3。
    """
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`\n")
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return []
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    raw_claims = data.get("claims") if isinstance(data, dict) else None
    if not isinstance(raw_claims, list):
        return []

    validated: list[dict] = []
    for item in raw_claims:
        if not isinstance(item, dict) or len(validated) >= 3:
            break
        dimension = str(item.get("dimension") or "")
        key = str(item.get("key") or "")
        relation = str(item.get("relation") or "supports")
        if dimension not in ALLOWED_KEYS or key not in ALLOWED_KEYS[dimension]:
            continue
        if key.startswith("distortion.") or relation not in {"supports", "contradicts"}:
            continue
        try:
            confidence = min(1.0, max(0.0, float(item.get("confidence") or 0.0)))
        except (TypeError, ValueError):
            confidence = 0.0
        validated.append(
            {
                "dimension": dimension,
                "key": key,
                "claim_zh": str(item.get("claim_zh") or "")[:200],
                "confidence": confidence,
                "relation": relation,
            }
        )
    return validated


# ── 回半环：质询应答判定 ─────────────────────────────────────────────

_VERIFICATION_SYSTEM_PROMPT = (
    "You are the verification judge of a psych-support bot's profile system. "
    "The bot gently asked the user whether a hypothesis about them matches "
    "their experience. Read the user's reply and output STRICT JSON only: "
    '{"verdict": "confirm"|"deny"|"unclear", "reason_zh": "<one short sentence>"}\n'
    "- confirm: the user agrees in their own words that the observation fits "
    "(对，就是这样 / 好像是这样 / 你说到点子上了).\n"
    "- deny: the user clearly says it does not fit (不是这样 / 没有这回事).\n"
    "- unclear: the user dodges, changes subject, partially agrees but is "
    "unsure, or the reply is unrelated to the hypothesis. When in doubt, "
    "choose unclear — never force a verdict.\n"
    "Judge only against the hypothesis given; do not infer other beliefs."
)


def _label_to_key_index() -> dict[str, str]:
    index: dict[str, str] = {}
    for keys in ALLOWED_KEYS.values():
        for key in keys:
            label = friendly_label(key)
            if label:
                index.setdefault(label, key)
    return index


_LABEL_TO_KEY = _label_to_key_index()


def parse_verdict_json(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`\n")
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return "unclear"
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return "unclear"
    verdict = str(data.get("verdict") or "unclear")
    return verdict if verdict in {"confirm", "deny", "unclear"} else "unclear"


def run_verification_judgment(
    session: Session,
    *,
    user_id: str,
    session_id: str,
    user_text: str,
) -> bool:
    """回半环：判定用户对上一轮质询的应答并驱动 belief 状态迁移。

    confirm → confirm_belief（L4→L2，面板出、机制类生效）；
    deny → reject_belief（D8 负记忆，同 key 永不复活）；
    unclear → 仅记录，不动状态。
    返回 True = 本轮已被质询判定占用（调用方跳过常规语义提取）。
    fail-open：任何异常只记 error 统计，绝不抛出。
    """
    from psych_support_bot.infra.db.profile_repositories import (
        confirm_belief,
        get_belief,
        get_pending_verification,
        record_intervention_event,
        reject_belief,
    )
    from psych_support_bot.infra.llm.generation import LLMUnavailableError

    try:
        injection = get_pending_verification(session, user_id, session_id)
        if injection is None:
            return False
        detail = json.loads(injection.detail_json or "{}")
        belief_key = _LABEL_TO_KEY.get(str(detail.get("belief_label") or ""))
        belief = get_belief(session, user_id, belief_key) if belief_key else None
        if belief is None or belief.status != "active":
            return False

        stats = record_extraction_stats(
            session,
            user_id,
            session_id=session_id,
            trigger="llm_verification",
            model=get_settings().openai_model,
        )
        payload = (
            f"[待验证假设] {detail.get('belief_label', '')}（内部观察：{belief.claim_text}）\n"
            f"[用户本轮回应]\n{(user_text or '').strip()}"
        )
        started = time.monotonic()
        try:
            raw = generate_profile_extraction(
                system_prompt=_VERIFICATION_SYSTEM_PROMPT,
                payload_text=payload,
                fallback=lambda: '{"verdict": "unclear"}',
            )
        except LLMUnavailableError:
            raw = '{"verdict": "unclear"}'
            stats.status = "error"
            stats.error = "llm_unavailable_fallback"
        stats.latency_ms = int((time.monotonic() - started) * 1000)

        verdict = parse_verdict_json(raw)
        if verdict == "confirm":
            confirm_belief(session, user_id, belief.id)
        elif verdict == "deny":
            reject_belief(session, user_id, belief.id)
        record_intervention_event(
            session,
            user_id,
            session_id=session_id,
            kind="question_answered",
            detail={"verdict": verdict, "belief_key": belief.key},
        )
        stats.claims_out = 1 if verdict in {"confirm", "deny"} else 0
        session.commit()
        logger.info("Verification judged: user=%s belief=%s verdict=%s", user_id, belief.key, verdict)
        return True
    except Exception:
        logger.warning("Verification judgment failed for user %s; skipping.", user_id, exc_info=True)
        session.rollback()
        try:
            record_extraction_stats(
                session,
                user_id,
                session_id=session_id,
                trigger="llm_verification",
                model=get_settings().openai_model,
                status="error",
                error="verification_failed",
            )
            session.commit()
        except Exception:  # noqa: BLE001 — fail-open 的兜底自身也必须兜住
            session.rollback()
        return True


def _should_llm_extract(user_text: str, *, practice_event: bool, turn_count: int) -> bool:
    """节流 = worker 纪律（设计文档 §6），不是成本上限（P2 决策）。"""
    topic_hits = len(detect_topics(user_text or ""))
    if practice_event or topic_hits >= 2:
        return True
    every = max(1, get_settings().profile_llm_every_turns)
    return topic_hits >= 1 and turn_count % every == 0


def run_semantic_extraction(
    session: Session,
    *,
    user_id: str,
    session_id: str,
    user_text: str,
    turn_count: int,
    risk_level: str,
    practice_event: bool,
    message_id: int | None = None,
) -> None:
    """LLM 语义提取入口（由 run_turn_extraction 在确定性提取之后调用）。

    fail-open：LLM 不可用 / 解析失败 / 落库异常，只记 error 统计，绝不抛出。
    """
    settings = get_settings()
    if not settings.profile_llm_extraction_enabled:
        return
    if risk_level in {"high", "critical"}:
        return  # 危机轮不调用：高危内容不入画像层
    if not _should_llm_extract(user_text, practice_event=practice_event, turn_count=turn_count):
        return

    from psych_support_bot.infra.llm.generation import LLMUnavailableError

    try:
        stats = record_extraction_stats(
            session,
            user_id,
            session_id=session_id,
            trigger="llm_semantic",
            model=get_settings().openai_model,
        )
        payload = build_extraction_payload(user_text, session, user_id)
        started = time.monotonic()
        try:
            raw = generate_profile_extraction(
                system_prompt=_SYSTEM_PROMPT,
                payload_text=payload,
                fallback=lambda: '{"claims": []}',
            )
        except LLMUnavailableError:
            raw = '{"claims": []}'
            stats.status = "error"
            stats.error = "llm_unavailable_fallback"
        stats.latency_ms = int((time.monotonic() - started) * 1000)

        claims = parse_extraction_json(raw)
        for item in claims:
            record_claim(
                session,
                user_id,
                dimension=item["dimension"],
                key=item["key"],
                claim_text=item["claim_zh"],
                relation=item["relation"],
                confidence=item["confidence"],
                session_id=session_id,
                evidence_message_ids=[message_id] if message_id else [],
                stats_id=stats.id,
            )
        stats.claims_out = len(claims)
        session.commit()
    except Exception:
        logger.warning("Semantic profile extraction failed for user %s; skipping.", user_id, exc_info=True)
        session.rollback()
        try:
            record_extraction_stats(
                session,
                user_id,
                session_id=session_id,
                trigger="llm_semantic",
                model=get_settings().openai_model,
                status="error",
                error="semantic_extraction_failed",
            )
            session.commit()
        except Exception:  # noqa: BLE001 — fail-open 的兜底自身也必须兜住
            session.rollback()

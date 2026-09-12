"""画像 belief 仓储层。

合并策略（K1a 确定性版，K2 质询闭环再调参）：
- 同 (user_id, key) 只有一行当前状态；relation=supports 推进置信度并
  追加证据，relation=contradicts 衰减置信度（L2 同时降级回 L4）。
- 否决（reject）后同 key 永不复活：再收到 claim 只返回守卫标记，
  不新建行、不记事件（D8 负记忆）。
- 结构性红线在写入入口钳制：extracted 来源强制 L4；distortion.* key
  直接 ValueError（认知歪曲禁止沉淀，PROFILE_DECISIONS / 知识提炼 §7.2）。

查询全部走 SQLAlchemy 2.0 参数化构造（绑定参数，无字符串拼接）。
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from psych_support_bot.infra.db.models import (
    ProfileBelief,
    ProfileBeliefEvent,
    ProfileExtractionStats,
)

logger = logging.getLogger(__name__)

# belief 行上只保留最近 N 条证据 message id；完整史在事件表。
MAX_EVIDENCE_REFS = 8

# 置信度更新的确定性参数（K2 接入质询闭环后按 eval 数据再校准）。
SUPPORT_GAIN = 0.15
CONTRADICT_FACTOR = 0.5
CONFIDENCE_CEILING = 0.95

# 质询候选水位：≥此值且跨会话证据 ≥2 才允许被质询（升级 L2 仍需用户确认）。
L4_QUESTION_THRESHOLD = 0.7

_VALID_DIMENSIONS = {f"D{i}" for i in range(1, 9)}


def record_extraction_stats(
    session: Session,
    user_id: str,
    *,
    session_id: str | None = None,
    trigger: str = "",
    model: str = "",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    latency_ms: int = 0,
    claims_out: int = 0,
    status: str = "ok",
    error: str = "",
) -> ProfileExtractionStats:
    """P2 全量统计：每次提取调用（含熔断跳过 status="skipped"）一行。"""
    row = ProfileExtractionStats(
        user_id=user_id,
        session_id=session_id,
        trigger=trigger,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=latency_ms,
        claims_out=claims_out,
        status=status,
        error=error,
    )
    session.add(row)
    session.flush()
    return row


def _append_event(
    session: Session,
    belief: ProfileBelief,
    event_type: str,
    *,
    evidence: list[int],
    detail: dict | None = None,
    stats_id: int | None = None,
) -> None:
    session.add(
        ProfileBeliefEvent(
            belief_id=belief.id,
            user_id=belief.user_id,
            event_type=event_type,
            evidence_json=json.dumps(evidence),
            detail_json=json.dumps(detail or {}, ensure_ascii=False),
            origin_stats_id=stats_id,
        )
    )


def get_belief(session: Session, user_id: str, key: str) -> ProfileBelief | None:
    """同 key 的当前行（含 rejected）——复活守卫与质询闭环都要读全状态。"""
    conditions = (ProfileBelief.user_id == user_id, ProfileBelief.key == key)
    return session.scalar(select(ProfileBelief).where(*conditions))


def get_active_belief(session: Session, user_id: str, key: str) -> ProfileBelief | None:
    belief = get_belief(session, user_id, key)
    if belief is not None and belief.status == "active":
        return belief
    return None


def list_active_beliefs(
    session: Session,
    user_id: str,
    *,
    dimensions: tuple[str, ...] | None = None,
    limit: int = 50,
) -> list[ProfileBelief]:
    """当前生效信念，按证据时近排序（渲染排序是记忆模块的职责）。"""
    conditions = [ProfileBelief.user_id == user_id, ProfileBelief.status == "active"]
    if dimensions:
        conditions.append(ProfileBelief.dimension.in_(dimensions))
    stmt = select(ProfileBelief).where(*conditions).order_by(desc(ProfileBelief.last_evidence_at)).limit(limit)
    return list(session.scalars(stmt))


def get_belief_events(session: Session, user_id: str, belief_id: int, *, limit: int = 50) -> list[ProfileBeliefEvent]:
    conditions = (ProfileBeliefEvent.user_id == user_id, ProfileBeliefEvent.belief_id == belief_id)
    stmt = select(ProfileBeliefEvent).where(*conditions).order_by(desc(ProfileBeliefEvent.id)).limit(limit)
    return list(session.scalars(stmt))


def record_claim(
    session: Session,
    user_id: str,
    *,
    dimension: str,
    key: str,
    claim_text: str,
    value: dict | None = None,
    relation: str = "supports",
    confidence: float = 0.0,
    layer: str = "L4",
    source: str = "extracted",
    session_id: str | None = None,
    evidence_message_ids: list[int] | None = None,
    stats_id: int | None = None,
) -> tuple[ProfileBelief | None, str]:
    """写入一条 claim，按合并策略落到 created / supported / contradicted /
    downgraded；命中否决守卫返回 (None, "resurrection_guard")。

    返回的事件名同时是 profile_belief_events.event_type。
    """
    if dimension not in _VALID_DIMENSIONS:
        raise ValueError(f"invalid profile dimension: {dimension!r}")
    if key.startswith("distortion."):
        # 红线 §7.2：认知歪曲只许当轮识别，结构上禁止沉淀。
        raise ValueError(f"distortion keys are identify-only and cannot be persisted: {key!r}")
    if relation not in {"supports", "contradicts"}:
        raise ValueError(f"invalid claim relation: {relation!r}")

    evidence = [int(mid) for mid in (evidence_message_ids or [])]

    # 提取器产出一律 L4：L2 只能来自用户确认（confirm_belief）或程序硬证据。
    if source == "extracted" and layer != "L4":
        logger.warning("Clamping non-L4 layer from extracted claim, key=%s layer=%s", key, layer)
        layer = "L4"

    existing = get_belief(session, user_id, key)
    if existing is not None and existing.status == "rejected":
        # D8 负记忆：否决过的 key 永不复活（也不记事件——守卫本身零痕迹，
        # 避免事件表被反复试探刷行）。
        return None, "resurrection_guard"

    if existing is None:
        belief = ProfileBelief(
            user_id=user_id,
            dimension=dimension,
            key=key,
            claim_text=claim_text,
            value_json=json.dumps(value or {}, ensure_ascii=False),
            layer=layer,
            status="active",
            confidence=min(CONFIDENCE_CEILING, max(0.0, confidence)),
            source=source,
            evidence_json=json.dumps(evidence[-MAX_EVIDENCE_REFS:]),
            origin_stats_id=stats_id,
            origin_session_id=session_id,
            last_evidence_session_id=session_id,
        )
        session.add(belief)
        session.flush()
        _append_event(session, belief, "created", evidence=evidence, stats_id=stats_id)
        return belief, "created"

    if relation == "supports":
        existing.confidence = min(CONFIDENCE_CEILING, existing.confidence + SUPPORT_GAIN)
        merged = json.loads(existing.evidence_json or "[]")
        for mid in evidence:
            if mid not in merged:
                merged.append(mid)
        existing.evidence_json = json.dumps(merged[-MAX_EVIDENCE_REFS:])
        existing.last_evidence_session_id = session_id
        _append_event(
            session,
            existing,
            "supported",
            evidence=evidence,
            detail={"confidence": existing.confidence},
            stats_id=stats_id,
        )
        return existing, "supported"

    # contradicts：矛盾证据衰减；L2 降级回 L4 等待验证（不覆盖不删除）。
    existing.confidence = round(existing.confidence * CONTRADICT_FACTOR, 4)
    event_type = "contradicted"
    detail: dict = {"confidence": existing.confidence}
    if existing.layer == "L2":
        existing.layer = "L4"
        event_type = "downgraded"
        detail["previous_layer"] = "L2"
    _append_event(session, existing, event_type, evidence=evidence, detail=detail, stats_id=stats_id)
    return existing, event_type


def confirm_belief(session: Session, user_id: str, belief_id: int) -> ProfileBelief | None:
    """用户确认：L4 → L2（质询闭环的升级原语，只认本人行）。"""
    belief = session.get(ProfileBelief, belief_id)
    if belief is None or belief.user_id != user_id or belief.status != "active":
        return None
    belief.layer = "L2"
    belief.source = "user_confirmed"
    belief.confidence = max(belief.confidence, 0.9)
    _append_event(session, belief, "confirmed", evidence=[], detail={"layer": "L2"})
    return belief


def reject_belief(session: Session, user_id: str, belief_id: int) -> ProfileBelief | None:
    """用户否决：status → rejected（D8 负记忆，同 key 永不复活、永不质询）。"""
    belief = session.get(ProfileBelief, belief_id)
    if belief is None or belief.user_id != user_id or belief.status != "active":
        return None
    belief.status = "rejected"
    belief.confidence = 0.0
    _append_event(session, belief, "rejected", evidence=[], detail={"reason": "user_denied"})
    return belief


def delete_user_profile_beliefs(session: Session, user_id: str) -> dict[str, int]:
    """级联删除某用户全部画像数据（接入 /v1/me 删除链）。"""
    events_deleted = (
        session.query(ProfileBeliefEvent)
        .filter(ProfileBeliefEvent.user_id == user_id)
        .delete(synchronize_session=False)
    )
    beliefs_deleted = (
        session.query(ProfileBelief).filter(ProfileBelief.user_id == user_id).delete(synchronize_session=False)
    )
    stats_deleted = (
        session.query(ProfileExtractionStats)
        .filter(ProfileExtractionStats.user_id == user_id)
        .delete(synchronize_session=False)
    )
    return {
        "profile_beliefs": int(beliefs_deleted),
        "profile_belief_events": int(events_deleted),
        "profile_extraction_stats": int(stats_deleted),
    }

"""
技能发现与推荐：面向前端的只读能力（语义检索、历史推荐）。

与 `/api/skills` 管理接口分离：不强制平台 admin，由 user_id + Agent 可见性（public/org/private）约束。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from core.system.runtime_settings import (
    get_skill_discovery_min_hybrid_score,
    get_skill_discovery_min_semantic_similarity,
    get_skill_discovery_tag_match_weight,
)
from core.skills.discovery import (
    SkillSearchHit,
    get_discovery_engine,
)
from core.skills.models import SkillDefinition
from middleware.user_context import get_current_user

router = APIRouter(prefix="/api/skill-discovery", tags=["skill-discovery"])


def _strip_embedding(s: SkillDefinition) -> Dict[str, Any]:
    d = s.to_dict()
    d.pop("embedding", None)
    return d


@router.get("/search")
async def skill_discovery_search(
    q: str = Query(..., min_length=1, description="自然语言查询"),
    agent_id: str = Query(..., min_length=1, description="用于 org/private 可见性判定的 Agent ID"),
    organization_id: Optional[str] = Query(
        default=None, description="组织 ID（与 org 可见技能、租户上下文一致时传入）"
    ),
    top_k: int = Query(8, ge=1, le=100),
    tag_match_weight: Optional[float] = Query(
        default=None, ge=0.0, le=1.0, description="标签匹配权重；语义权重为 1-该值"
    ),
    min_semantic_similarity: Optional[float] = Query(
        default=None, ge=0.0, le=1.0, description="余弦相似度下限；默认读环境配置"
    ),
    min_hybrid_score: Optional[float] = Query(
        default=None, ge=0.0, le=1.0, description="混合分下限；默认读环境配置"
    ),
    include_scores: bool = Query(False, description="是否返回每项语义/标签/混合分"),
    _user: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """语义发现：混合排序 + 可配置权重与下限（与运行时 Planner 使用同一引擎）。"""
    engine = get_discovery_engine()
    if include_scores:
        hits: List[SkillSearchHit] = engine.search_hits(
            query=q,
            agent_id=agent_id,
            organization_id=organization_id,
            top_k=top_k,
            filters={"enabled_only": True},
            tag_match_weight=tag_match_weight,
            min_semantic_similarity=min_semantic_similarity,
            min_hybrid_score=min_hybrid_score,
        )
        return {
            "object": "skill_search_scored",
            "data": [
                {
                    "skill": _strip_embedding(h.skill),
                    "semantic_score": h.semantic_score,
                    "tag_match_score": h.tag_match_score,
                    "hybrid_score": h.hybrid_score,
                }
                for h in hits
            ],
            "defaults": {
                "tag_match_weight": get_skill_discovery_tag_match_weight(),
                "min_semantic_similarity": get_skill_discovery_min_semantic_similarity(),
                "min_hybrid_score": get_skill_discovery_min_hybrid_score(),
            },
        }
    found = engine.search(
        query=q,
        agent_id=agent_id,
        organization_id=organization_id,
        top_k=top_k,
        filters={"enabled_only": True},
        tag_match_weight=tag_match_weight,
        min_semantic_similarity=min_semantic_similarity,
        min_hybrid_score=min_hybrid_score,
    )
    return {
        "object": "skill_search",
        "data": [_strip_embedding(s) for s in found],
        "defaults": {
            "tag_match_weight": get_skill_discovery_tag_match_weight(),
            "min_semantic_similarity": get_skill_discovery_min_semantic_similarity(),
            "min_hybrid_score": get_skill_discovery_min_hybrid_score(),
        },
    }


@router.get("/recommend")
async def skill_discovery_recommend(
    agent_id: str = Query(..., min_length=1),
    organization_id: Optional[str] = Query(default=None),
    limit: int = Query(8, ge=1, le=50),
    current_user: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """按当前用户历史使用频次推荐；无历史时回退为可见启用的前若干项。"""
    engine = get_discovery_engine()
    rec = engine.recommend_for_user(
        user_id=current_user,
        agent_id=agent_id,
        organization_id=organization_id,
        limit=limit,
    )
    return {
        "object": "skill_recommendation",
        "data": [_strip_embedding(s) for s in rec],
    }

"""
技能发现增强：可配置权重/阈值、使用记录、推荐冷启动。
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from core.skills.discovery import SkillDiscoveryEngine, SkillSearchHit
from core.skills.models import SkillDefinition
from core.skills.registry import SkillRegistry
from core.skills.usage_store import record_skill_use, set_skill_usage_path_for_tests, top_skills_for_user


def _minimal_skill(sid: str) -> SkillDefinition:
    return SkillDefinition(
        id=sid,
        name=sid,
        version="1.0.0",
        description="d",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        tags=[],
    )


def test_usage_store_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "usage.json"
        set_skill_usage_path_for_tests(p)
        try:
            record_skill_use("u1", "skill.a")
            record_skill_use("u1", "skill.a")
            record_skill_use("u1", "skill.b")
            top = top_skills_for_user("u1", limit=10)
            assert top[0] == ("skill.a", 2)
            assert top[1] == ("skill.b", 1)
            data = json.loads(p.read_text(encoding="utf-8"))
            assert data["users"]["u1"]["skill.a"] == 2
        finally:
            set_skill_usage_path_for_tests(None)


def test_resolve_weights_and_thresholds() -> None:
    w_sem, w_tag = SkillDiscoveryEngine._resolve_weights(0.3)
    assert abs(w_sem - 0.7) < 1e-9
    assert abs(w_tag - 0.3) < 1e-9
    w_sem2, w_tag2 = SkillDiscoveryEngine._resolve_weights(0.0)
    assert w_sem2 == 1.0 and w_tag2 == 0.0
    t_sem, t_hyb = SkillDiscoveryEngine._resolve_thresholds(0.7, 0.5)
    assert t_sem == 0.7 and t_hyb == 0.5


def test_recommend_cold_start_public_skills() -> None:
    """无历史时按 id 取可见前若干项。"""
    a = _minimal_skill("test_reco_a")
    b = _minimal_skill("test_reco_z")
    try:
        SkillRegistry.register(a)
        SkillRegistry.register(b)
        eng = SkillDiscoveryEngine()
        eng.bind_registry(SkillRegistry)
        out = eng.recommend_for_user(
            user_id="user_no_reco_history_xyz",
            agent_id="any_agent",
            organization_id=None,
            limit=10_000,
        )
        ours = [x.id for x in out if x.id in ("test_reco_a", "test_reco_z")]
        # 升序 id：a 在 z 前
        assert ours == ["test_reco_a", "test_reco_z"]
    finally:
        SkillRegistry.unregister("test_reco_a")
        SkillRegistry.unregister("test_reco_z")


def test_search_hit_dataclass() -> None:
    s = _minimal_skill("x")
    h = SkillSearchHit(skill=s, semantic_score=0.8, tag_match_score=0.2, hybrid_score=0.7)
    assert h.hybrid_score == 0.7

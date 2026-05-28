"""开箱企业套件验收矩阵（合同 checklist ID 与自动探针映射）。"""
from __future__ import annotations

from typing import Any, Literal, TypedDict

PhaseId = Literal["phase0", "phase1", "phase2"]
Priority = Literal["P0", "P1", "P2"]
EvalMode = Literal["auto", "manual", "hybrid"]

# 官方场景 Bundle（合同附件可引用）
ENTERPRISE_SCENE_BUNDLES: dict[str, dict[str, Any]] = {
    "oa_approval": {
        "label": "智慧办文（审批门禁）",
        "platform_bundle_id": "release-brief-gate",
        "workflow_bundle_id": "release-brief-gate",
    },
    "policy_qa": {
        "label": "制度/政策智能问答",
        "platform_bundle_id": "rag-research-verify",
        "workflow_bundle_id": "parallel-research-verify",
    },
    "research_parallel": {
        "label": "科研并行编排",
        "platform_bundle_id": "rag-research-verify",
        "workflow_bundle_id": "parallel-research-verify",
    },
}


class BenchmarkItem(TypedDict, total=False):
    id: str
    phase: PhaseId
    priority: Priority
    label: str
    eval_mode: EvalMode
    probe: str
    competitive_dimension: str
    hint: str


# probe 由 suite_benchmark.evaluate_probe 解析
SUITE_BENCHMARK_ITEMS: list[BenchmarkItem] = [
    # --- Phase 0 Core ---
    {"id": "0-B-02", "phase": "phase0", "priority": "P0", "label": "网关健康检查", "eval_mode": "auto", "probe": "health_endpoints"},
    {"id": "0-B-03", "phase": "phase0", "priority": "P0", "label": "模型注册表可用", "eval_mode": "auto", "probe": "model_registry_nonempty"},
    {"id": "0-C-01", "phase": "phase0", "priority": "P0", "label": "工作流审批 API", "eval_mode": "auto", "probe": "workflow_approval_api"},
    {"id": "0-C-06", "phase": "phase0", "priority": "P0", "label": "Fork/Join 节点运行时", "eval_mode": "auto", "probe": "workflow_fork_join_runtime"},
    {"id": "0-D-03", "phase": "phase0", "priority": "P0", "label": "合规审计 JSON 导出", "eval_mode": "auto", "probe": "compliance_report_api"},
    {"id": "0-D-04", "phase": "phase0", "priority": "P0", "label": "Prompt 可审计（AGENTS 约束）", "eval_mode": "auto", "probe": "agents_no_hidden_prompt_policy"},
    {"id": "0-E-00", "phase": "phase0", "priority": "P0", "label": "一键导入目录 API", "eval_mode": "auto", "probe": "import_catalog_api"},
    {"id": "0-E1-01", "phase": "phase0", "priority": "P0", "label": "办文场景官方 Bundle", "eval_mode": "auto", "probe": "scene_bundle:oa_approval"},
    {"id": "0-E2-01", "phase": "phase0", "priority": "P0", "label": "制度问答场景官方 Bundle", "eval_mode": "auto", "probe": "scene_bundle:policy_qa"},
    {"id": "0-E3-01", "phase": "phase0", "priority": "P0", "label": "科研并行场景官方 Bundle", "eval_mode": "auto", "probe": "scene_bundle:research_parallel"},
    {"id": "0-A-03", "phase": "phase0", "priority": "P0", "label": "运维 Runbook 交付物", "eval_mode": "auto", "probe": "artifact:docs/ops/SAAS_PUBLIC_LAUNCH_GATE_ZH.md"},
    {"id": "0-A-04", "phase": "phase0", "priority": "P0", "label": "工作流编排概览文档", "eval_mode": "auto", "probe": "artifact:docs/workflow/WORKFLOW_ORCHESTRATION_OVERVIEW_ZH.md"},
    {"id": "0-A-01", "phase": "phase0", "priority": "P1", "label": "产品边界 AGENTS.md", "eval_mode": "auto", "probe": "artifact:AGENTS.md"},
    {"id": "0-B-01", "phase": "phase0", "priority": "P1", "label": "导入 API 路由注册", "eval_mode": "auto", "probe": "import_api_routes"},
    {"id": "0-C-03", "phase": "phase0", "priority": "P1", "label": "审批驳回 API", "eval_mode": "auto", "probe": "workflow_reject_api"},
    {"id": "0-C-04", "phase": "phase0", "priority": "P1", "label": "Checkpoint 运行时", "eval_mode": "auto", "probe": "workflow_checkpoint_runtime"},
    {"id": "0-C-05", "phase": "phase0", "priority": "P1", "label": "Verify Loop 运行时", "eval_mode": "auto", "probe": "workflow_verify_loop_runtime"},
    {"id": "0-D-01", "phase": "phase0", "priority": "P1", "label": "发布门禁 API", "eval_mode": "auto", "probe": "publish_gate_api"},
    {"id": "0-D-02", "phase": "phase0", "priority": "P1", "label": "执行 Timeline API", "eval_mode": "auto", "probe": "workflow_execution_timeline_api"},
    {"id": "0-E-01", "phase": "phase0", "priority": "P1", "label": "导入预检 API", "eval_mode": "auto", "probe": "import_preflight_api"},
    # Phase 0 UAT（静态冒烟；Live 见 suite_uat.UAT_LIVE_SPECS）
    {"id": "0-C-02", "phase": "phase0", "priority": "P0", "label": "审批通过后流程继续", "eval_mode": "hybrid", "probe": "uat:approval_resume"},
    {"id": "0-E1-04", "phase": "phase0", "priority": "P0", "label": "办文流程触发人工审批", "eval_mode": "hybrid", "probe": "uat:oa_approval_pause"},
    # --- Phase 1 Secure ---
    {"id": "1-A-03", "phase": "phase1", "priority": "P0", "label": "RBAC 配置项（代码/Helm）", "eval_mode": "auto", "probe": "settings_flag:rbac"},
    {"id": "1-A-04", "phase": "phase1", "priority": "P0", "label": "RBAC 写保护配置项", "eval_mode": "auto", "probe": "settings_flag:rbac_enforcement"},
    {"id": "1-B-01", "phase": "phase1", "priority": "P0", "label": "租户隔离配置项", "eval_mode": "auto", "probe": "settings_flag:tenant"},
    {"id": "1-C-01", "phase": "phase1", "priority": "P0", "label": "生产调试开关（Helm/Guardrails）", "eval_mode": "auto", "probe": "settings_flag:debug_off"},
    {"id": "1-C-03", "phase": "phase1", "priority": "P0", "label": "敏感数据脱敏配置项", "eval_mode": "auto", "probe": "settings_flag:redaction"},
    {"id": "1-C-04", "phase": "phase1", "priority": "P0", "label": "外部模型出站脱敏配置项", "eval_mode": "auto", "probe": "settings_flag:egress_redaction"},
    {"id": "1-A-03-R", "phase": "phase1", "priority": "P1", "label": "RBAC 运行时启用", "eval_mode": "hybrid", "probe": "readiness:rbac"},
    {"id": "1-B-01-R", "phase": "phase1", "priority": "P1", "label": "租户运行时强制", "eval_mode": "hybrid", "probe": "readiness:tenant"},
    {"id": "1-E-01", "phase": "phase1", "priority": "P0", "label": "Prometheus 指标", "eval_mode": "auto", "probe": "prometheus_enabled"},
    {"id": "1-E-03", "phase": "phase1", "priority": "P0", "label": "合规报告 MVP", "eval_mode": "auto", "probe": "compliance_report_api"},
    {"id": "1-A-01", "phase": "phase1", "priority": "P0", "label": "OIDC 企业登录", "eval_mode": "hybrid", "probe": "oidc_configured_or_documented"},
    {"id": "1-D-01", "phase": "phase1", "priority": "P0", "label": "HA 部署清单", "eval_mode": "auto", "probe": "artifact:deploy/helm/perilla-backend"},
    {"id": "1-A-02", "phase": "phase1", "priority": "P1", "label": "本地账号/OIDC 文档", "eval_mode": "auto", "probe": "artifact:tutorials/tutorial-auth-login-roles-zh.md"},
    {"id": "1-B-02", "phase": "phase1", "priority": "P1", "label": "租户隔离单测存在", "eval_mode": "auto", "probe": "artifact:backend/tests/test_tenant_paths_contract.py"},
    {"id": "1-C-02", "phase": "phase1", "priority": "P1", "label": "安全响应头配置项", "eval_mode": "auto", "probe": "readiness:security_headers"},
    {"id": "1-E-02", "phase": "phase1", "priority": "P1", "label": "合规 PDF 导出 API", "eval_mode": "auto", "probe": "compliance_pdf_api"},
    {"id": "1-E-04", "phase": "phase1", "priority": "P1", "label": "审计日志配置项", "eval_mode": "auto", "probe": "readiness:audit"},
    # --- Phase 2 Suite ---
    {"id": "2-A-02", "phase": "phase2", "priority": "P0", "label": "Helm 离线部署 Chart", "eval_mode": "auto", "probe": "artifact:deploy/helm/perilla-backend/Chart.yaml"},
    {"id": "2-C-01", "phase": "phase2", "priority": "P0", "label": "官方模板 ≥5", "eval_mode": "auto", "probe": "import_catalog_min:5"},
    {"id": "2-C-02", "phase": "phase2", "priority": "P0", "label": "模板含样例与说明", "eval_mode": "auto", "probe": "import_catalog_has_descriptions"},
    {"id": "2-D-01", "phase": "phase2", "priority": "P0", "label": "集成规范文档", "eval_mode": "auto", "probe": "artifact:tutorials/tutorial.md"},
    {"id": "2-E-01", "phase": "phase2", "priority": "P0", "label": "演示脚本交付物", "eval_mode": "auto", "probe": "artifact:demos/workflows/README.md"},
    {"id": "2-B-02", "phase": "phase2", "priority": "P0", "label": "管理员导入 Bundle（UAT）", "eval_mode": "hybrid", "probe": "uat:admin_import_bundle"},
    {"id": "2-A-01", "phase": "phase2", "priority": "P1", "label": "生产 Compose 样例", "eval_mode": "auto", "probe": "artifact:docker-compose.prod.yml"},
    {"id": "2-A-03", "phase": "phase2", "priority": "P1", "label": "平台产品原则文档", "eval_mode": "auto", "probe": "artifact:docs/research/PLATFORM_PRODUCT_PRINCIPLES_ZH.md"},
    {"id": "2-D-02", "phase": "phase2", "priority": "P1", "label": "MCP 设置路由", "eval_mode": "auto", "probe": "artifact:frontend/src/router/index.ts"},
    {"id": "2-E-02", "phase": "phase2", "priority": "P1", "label": "教程索引导入章节", "eval_mode": "auto", "probe": "artifact:tutorials/tutorial-index.md"},
]

# 对标成熟商业 PaaS 的维度（参考分 0–5，非实测第三方产品）
COMPETITIVE_DIMENSIONS: list[dict[str, Any]] = [
    {
        "id": "approval_audit",
        "label": "审批/验收/审计",
        "weight": 1.2,
        "reference": {"mature_commercial_paas": 4.0, "langflow": 2.5, "n8n": 3.0},
        "perilla_probes": ["workflow_approval_api", "compliance_report_api", "workflow_fork_join_runtime"],
    },
    {
        "id": "local_privacy_governance",
        "label": "本地/专网与可治理",
        "weight": 1.2,
        "reference": {"mature_commercial_paas": 3.5, "langflow": 3.0, "n8n": 3.0},
        "perilla_probes": [
            "agents_no_hidden_prompt_policy",
            "readiness:tenant",
            "readiness:redaction",
            "settings_flag:egress_redaction",
        ],
    },
    {
        "id": "multi_tenant_enterprise",
        "label": "多租户与企业身份",
        "weight": 1.0,
        "reference": {"mature_commercial_paas": 5.0, "langflow": 2.0, "n8n": 2.5},
        "perilla_probes": ["settings_flag:rbac", "settings_flag:tenant", "oidc_configured_or_documented"],
    },
    {
        "id": "out_of_box_templates",
        "label": "开箱模板与场景包",
        "weight": 1.0,
        "reference": {"mature_commercial_paas": 4.5, "langflow": 4.0, "n8n": 4.0},
        "perilla_probes": ["import_catalog_min:5", "scene_bundle:oa_approval", "scene_bundle:policy_qa"],
    },
    {
        "id": "low_code_ux",
        "label": "低代码上手体验",
        "weight": 0.8,
        "reference": {"mature_commercial_paas": 4.5, "langflow": 4.8, "n8n": 4.5},
        "perilla_probes": ["import_catalog_api"],
    },
    {
        "id": "integration_ecosystem",
        "label": "第三方集成生态",
        "weight": 0.7,
        "reference": {"mature_commercial_paas": 4.5, "langflow": 3.0, "n8n": 5.0},
        "perilla_probes": ["import_catalog_api"],
    },
]

# 平台产品原则落地 — 核查清单

更新时间：2026-05-27

## 自动化

| 项 | 命令 | 结果（本地） |
|----|------|--------------|
| 协同上下文工具 | `cd frontend && npm run test:unit -- tests/unit/collaborationContext.spec.ts` | 通过 |
| 运行页 query 预填 | `npm run test:unit -- tests/unit/workflowRunNavigation.spec.ts` | 通过 |
| Demo bundle 图 | `npm run test:unit -- tests/unit/demoWorkflowBundles.spec.ts` | 通过 |

## 功能核查（手工）

| # | 项 | 预期 |
|---|-----|------|
| 1 | 侧栏分组 | **平台**：对话、智能体、工作流；**能力**：知识库、技能、模型；**工具**：文生图 |
| 2 | 智能体列表 | 顶部协同提示条 +「去编排工作流」 |
| 3 | 工作流新建 | 导入演示项目 → 预检 → 运行 → 跳转运行页且 `input_data` 已预填 |
| 4 | 工作流运行 | `global_context` 旁「填充协同上下文」生成 `correlation_id` |
| 5 | 教程路径 | `tutorial-beginner-playbook` 主路径不含文生图；README 主路径已更新 |

## 文档

- [PLATFORM_PRODUCT_PRINCIPLES_ZH.md](./PLATFORM_PRODUCT_PRINCIPLES_ZH.md)
- [ROADMAP_REVIEW_APPENDIX_ZH.md](./ROADMAP_REVIEW_APPENDIX_ZH.md) §八

## 未在本轮实现（留待后续 Epic）

- OIDC/KMS/HA 企业安全组件
- OTel 与合规报告一键导出
- Agent 创建向导、跨 Chat/Workflow 统一复盘 UI

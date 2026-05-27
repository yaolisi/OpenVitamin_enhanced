# Perilla 演示工作流（可导入 JSON）

本目录包含两个多智能体演示项目的 **bundle JSON**（`schema_version: 1`），与 `tutorials/demo-playbook-*.md` 配套使用。

| 文件 | 演示重点 | 多 Agent 完整版（平台包） |
|------|----------|-------------------------|
| [demo1-release-brief-gate.bundle.json](./demo1-release-brief-gate.bundle.json) | 画布轻量：LLM 多角色 + 审批 + Checkpoint | [release-brief-gate](../platform/release-brief-gate.platform-bundle.json) |
| [demo2-parallel-research-verify.bundle.json](./demo2-parallel-research-verify.bundle.json) | 画布轻量：双路 LLM 并行 + Verify Loop | [rag-research-verify](../platform/rag-research-verify.platform-bundle.json) |

**画布导入**（「演示项目」）不创建 Agent/知识库，节点为 LLM 模拟角色分工，适合零依赖快速看编排。

**平台演示包**（工作流列表页「一键导入演示包」）会落库 Agent、知识库（Demo2）并绑定 `agent` 节点，适合演示真实多智能体能力。

## 导入方式

### 0. 一键导入 / 导出（统一入口，推荐完整环境）

侧栏 **`/import`**（或工作流列表 **「一键导入」**）：

| 能力 | 说明 |
|------|------|
| **内置目录** | 本目录 `*.bundle.json` 与 [platform 包](../platform/) 均在 catalog 中 |
| **上传 JSON / ZIP** | 自定义包；ZIP 可含 `documents/` |
| **导出** | 从已有工作流导出平台快照（`POST /api/v1/import/export`） |

API 与 curl 见 [demos/platform/README.md](../platform/README.md)、[tutorial.md §8.6](../../tutorials/tutorial.md)、[BUNDLE_SCHEMA.md](../platform/BUNDLE_SCHEMA.md)。

### 1. 画布演示（零依赖，仅 DAG）

1. 打开 **Workflow 新建** 或 **编辑** 页。
2. 在 **「演示项目（多智能体）」** 下拉框选择 Demo → **导入演示项目**。
3. 按 playbook 绑定 Agent（Demo 2）或改为 Agent 节点（Demo 1 进阶）→ **预检** → **保存** → 工具栏 **发布**（发布门禁弹窗；非灰色「部署」）→ Run。

### 2. 工作流 bundle 脚本（仅落库 DAG）

```bash
# 需本机网关已启动（默认 8000）
PYTHONPATH=backend python3 scripts/import_demo_workflow.py \
  demos/workflows/demo1-release-brief-gate.bundle.json

# 导入并发布版本
PUBLISH=1 PYTHONPATH=backend python3 scripts/import_demo_workflow.py \
  demos/workflows/demo2-parallel-research-verify.bundle.json
```

多租户环境请设置 `X_TENANT_ID`；若启用 API Key，设置 `PERILLA_API_KEY`。

脚本 stdout 会打印 `workflow_id`、`edit_url_hint`、`sample_input`。

### 3. 手工 Workflow API

1. `POST /api/v1/workflows` 创建工作流元数据。
2. `POST /api/v1/workflows/{id}/versions`，body 为 bundle 内 `dag` 字段。
3. `POST .../versions/{version_id}/publish`（生产建议）。

## Bundle 字段说明

- `dag`：与编辑器持久化格式一致（`nodes` / `edges` / `global_config`）。
- `agent_placeholders`：建议在 `/agents` 创建后，在画布将对应节点改为 **Agent** 并绑定 ID。
- `sample_input`：Run 页 JSON 入参示例。

详细步骤见：

- [tutorials/demo-playbook-01-release-brief.md](../../tutorials/demo-playbook-01-release-brief.md)
- [tutorials/demo-playbook-02-parallel-research.md](../../tutorials/demo-playbook-02-parallel-research.md)

## 完整演示包（含 Agent + 知识库）

若需 **一键导入知识库样例、Agent 与工作流（节点已绑定）**，见 [demos/platform/README.md](../platform/README.md)。

# 平台演示包（Agent + 知识库 + 工作流）

一键导入完整演示环境，适合内网 PoC 或新人上手。

| 文件 | 说明 |
|------|------|
| [release-brief-gate.platform-bundle.json](./release-brief-gate.platform-bundle.json) | Demo1 多 Agent：澄清员 + 写手 + 审批/Checkpoint |
| [rag-research-verify.platform-bundle.json](./rag-research-verify.platform-bundle.json) | Demo2 多 Agent + KB：Web/KB 双 Agent + Fork/Join + Verify Loop |
| [documents/](./documents/) | Demo2 知识库样例 Markdown |

## 导入内容（每个平台包）

| 资源 | rag-research-verify | release-brief-gate |
|------|---------------------|-------------------|
| 知识库 + 样例文档 | ✅ | — |
| 自定义 Prompt Skill | ✅ 调研 JSON 格式化 | ✅ 简报字段检查 |
| MCP Server 配置（模板，默认关闭） | ✅ filesystem stdio | ✅ 同左 |
| Agent + 内置 Skill | Web + KB + 自定义 Skill | 澄清员 + 写手 |
| 工作流（Agent 节点已绑定） | Fork/Join + Verify Loop | 审批 + Checkpoint |

内置 Skill（`builtin_*`）无需导入；bundle 内 `builtin_skill_catalog` 仅作说明。

MCP **工具→Skill** 在 Server `enabled: false` 时不会自动 Import；请到 **Settings → MCP** 启用对应 Server → **Probe** → **Import**（与教程 §8.5 一致）。

Schema 详见 [BUNDLE_SCHEMA.md](./BUNDLE_SCHEMA.md)。

## 方式一：控制台（推荐）

1. 侧栏 **「一键导入」**（`/import`）：**导入**（内置 / 上传 JSON·ZIP / 粘贴）或 **导出**（从工作流生成 ZIP/JSON）；详见教程 **§8.6**。
2. 筛选 **平台完整包**，选择演示包 → **开始导入**
3. 导入完成后进入工作流编辑；知识库 / Agent / MCP 在对应页面查看

工作流列表页右上角亦有 **「一键导入」** 快捷入口。

画布轻量演示（仅 DAG 到编辑器）：**工作流 → 新建 → 演示项目**。

## 方式二：API

```bash
curl -s http://127.0.0.1:8000/api/v1/import/catalog | jq .

curl -s -X POST "http://127.0.0.1:8000/api/v1/import/run" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Id: default" \
  -d '{"kind":"platform","bundle_id":"rag-research-verify","wait_document_index":true}'

# 上传 ZIP（含 documents/）
curl -s -X POST "http://127.0.0.1:8000/api/v1/import/upload" \
  -H "X-Tenant-Id: default" \
  -F "file=@./my-export.zip"

# 从工作流导出 ZIP
curl -sS -X POST "http://127.0.0.1:8000/api/v1/import/export?download=true" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Id: default" \
  -o my-export.zip \
  -d '{"kind":"platform","format":"zip","bundle_id":"my-export","name":"快照","workflow_ids":["<workflow-uuid>"]}'

# 兼容旧路径：
curl -s -X POST "http://127.0.0.1:8000/api/v1/demos/platform-bundles/rag-research-verify/import" \
  -H "Content-Type: application/json" \
  -d '{"publish_workflows": false, "wait_document_index": true}'
```

需已登录（本地 Cookie）或携带 `X-Api-Key`（operator 及以上写权限）。

## 方式三：脚本

```bash
PYTHONPATH=backend python3 scripts/import_platform_demo_bundle.py rag-research-verify

# 导入并尝试发布工作流（可能受发布门禁约束）
PUBLISH=1 PYTHONPATH=backend python3 scripts/import_platform_demo_bundle.py rag-research-verify
```

环境变量：`PERILLA_API_BASE`、`PERILLA_API_KEY`、`X_TENANT_ID`（可选）。

## 前置条件

- 至少 **1 个 LLM** 与 **1 个 Embedding 模型** 已在模型列表中注册（bundle 使用 `__AUTO_LLM__` / `__AUTO_EMBEDDING__` 自动选择首个）
- 知识库索引在导入时同步执行（`wait_document_index: true`），大文档环境可能需数分钟

## 扩展自定义包

1. 复制 `rag-research-verify.platform-bundle.json` 并修改 `bundle_id`
2. 使用 `$import:<bundle_key>` 在 `rag_ids`、`agent_id` 等字段引用本包内资源
3. 将 JSON 放在本目录，前端/API 会自动出现在 **内置目录**；或 **导出** 当前环境后修改再 **上传 ZIP**

完整 Schema、导出字段与 ZIP 布局见 [BUNDLE_SCHEMA.md](./BUNDLE_SCHEMA.md)。

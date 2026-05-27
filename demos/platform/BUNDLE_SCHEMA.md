# Platform Bundle Schema（`schema_version: 1`）

## 顶层字段

| 字段 | 说明 |
|------|------|
| `bundle_id` | 唯一 ID，对应文件名 `{bundle_id}.platform-bundle.json` |
| `knowledge_bases[]` | 知识库 + 内联文档或 `content_path` |
| `skills[]` | 自定义 Prompt/Tool Skill（落库 + 注册 SkillRegistry） |
| `mcp_servers[]` | MCP Server 配置（stdio / http） |
| `mcp_tool_imports[]` | 可选：对某 Server 执行 tools→Skill 导入 |
| `agents[]` | Agent；`enabled_skills` / `rag_ids` 可用 `$import:<bundle_key>` |
| `workflows[]` | 工作流 DAG；`agent_id` 等可用 `$import:` |
| `builtin_skill_catalog` | 仅文档用，列出依赖的内置 Skill ID |

## `$import:` 引用

- `knowledge_bases[].bundle_key` → KB id
- `skills[].bundle_key` → skill id
- `mcp_servers[].bundle_key` → mcp server id
- `agents[].bundle_key` → agent id
- `workflows[].bundle_key` → workflow id

## MCP 导入行为

- `mcp_servers[].enabled: false`：只写入配置，不拉起进程（适合离线/模板）。
- `mcp_tool_imports[].skip_if_disabled: true`：Server 未启用时跳过 Import，并在结果 `warnings` 中提示去 **Settings → MCP** 启用后手动 Probe/Import。
- `mcp_tool_imports[].optional: true`（默认）：Probe/Import 失败不阻断整包导入。

## 特殊占位

- `__AUTO_LLM__` / `__AUTO_EMBEDDING__`：自动选用已注册的首个 LLM / Embedding 模型。

## 导出（Export API）

- `POST /api/v1/import/export/discover`：根据 `workflow_ids` 扫描 DAG / Agent，返回建议导出的 `agent_ids`、`knowledge_base_ids`、`skill_ids`、`mcp_server_ids`。
- `POST /api/v1/import/export`：从当前租户导出 `kind=platform|workflow`，`format=json|zip`。
- 导出时 Agent / KB 的模型 ID 可写回 `__AUTO_LLM__` / `__AUTO_EMBEDDING__`（`use_model_placeholders`，默认 true）。
- 自定义 Skill（非 builtin、非 MCP 派生）写入 `skills[]`；MCP Server 写入 `mcp_servers[]`，可选 `mcp_tool_imports[]`。
- DAG / Agent 内资源 ID 在 manifest 中改写为 `$import:<bundle_key>`。

## ZIP 包结构

```text
{bundle_id}.zip
├── {bundle_id}.platform-bundle.json   # platform；workflow 则为 {bundle_id}.bundle.json
└── documents/                         # 知识库文档（content_path 相对包根）
    └── …
```

- 导入：`POST /api/v1/import/upload` 支持 `.zip`；解压目录作为 `bundle_dir` 解析 `content_path`。
- 纯 JSON 上传不解析 `content_path`，须内联 `content` 或改用 ZIP。

# 工作流编排概览（进阶）

本文帮助新用户从「单轮 Chat」过渡到 **多节点工作流**，并指向仓库内已有实操文档。

## 1. 核心概念

| 概念 | 含义 |
|------|------|
| **Workflow** | 有向图：节点表示步骤（LLM、工具、分支、循环等），边表示数据与控制权传递。 |
| **Control Plane** | 负责定义、版本、发布与执行策略；与执行内核（队列、租约、事件）解耦。 |
| **节点类型** | 见下表「已启用节点」；编辑器节点库与 DAG `workflow_node_type` 对齐。 |

推理仍统一经 **FastAPI 网关**；工作流负责编排何时调用 LLM、何时调用工具或子 Agent。

### 1.1 已启用节点（2026-05）

| 分类 | 编辑器类型 | `workflow_node_type` | 说明 |
|------|------------|----------------------|------|
| 数据 | Input / Output / Variable | `input` / `output` / `variable` | 入参、落库输出、写入 `workflow_variables` |
| AI | LLM | `llm` | 显式 `model_id` 或 **`model_tier`**（low→fast / standard→chat / thorough→reasoning） |
| AI | Embedding | `embedding` | 经网关 `InferenceClient.embed` |
| AI | Agent | `agent` | 调用已注册智能体 |
| Prompt | Prompt Template / System Prompt | `prompt_template`（system 为 role=system） | 模板 + `{{var}}` |
| 逻辑 | Condition / Loop | `condition` / `loop` | 分支与迭代 |
| 逻辑 | **并行限流** | `parallel` | 控制下游并发上限（`max_parallel`），非扇出 |
| 逻辑 | **扇出 Fork** | `fork` | 透传输入；多条 SUCCESS 出边 → 并行分支 |
| 逻辑 | **汇聚 Join** | `join` | 默认等待全部入边（`dependency_mode=all`），输出 `branches` |
| 逻辑 | **验收检查点** | `checkpoint` | 确定性 pass/fail（`required_keys` 等） |
| 逻辑 | **验证环 Ralph** | `verify_loop` | 迭代执行 `loop_body` + 每轮验收，通过即停 |
| 工具 | HTTP / Python / Shell / Skill | `http_request` / `python` / `shell` / `tool` | HTTP 走 `http.request`；Python 仅 `python.run` |

### 1.2 与 OmX / claw-code 编排概念对照

| OmX / ultrawork 概念 | Perilla 对应 |
|----------------------|--------------|
| `$deep-interview` 澄清 | LLM + Prompt Template 链 |
| `$ralplan` 计划 + 审批 | Prompt Template + `approval` |
| `$team` / ultrawork 并行 | **Fork → 多分支 → Join** |
| `$ralph` 持久验证 | **Verify Loop** 或 Loop + Checkpoint |
| agent-tiers 分档 | LLM **`model_tier`** |
| acceptance criteria | **Checkpoint** / Verify Loop 内验收 |

### 1.3 编辑器编排模板（一键导入）

新建/编辑页 **「高价值编排模板（OmX）」** 提供：

1. **澄清 · 计划 · 验收** — 澄清 → 计划 → 审批 → 执行 → 验收 → 输出  
2. **分档双 LLM** — low 草稿 → thorough 精修 → 验收  
3. **验收门禁** — LLM → Checkpoint → 输出  
4. **并行小队（Fork/Join）** — 双路 LLM 并行后汇聚  
5. **Ralph 验证环** — Verify Loop 直至验收通过  

## 2. 建议阅读顺序

1. **节点怎么配**：`docs/workflow/WORKFLOW_NODE_CONFIG_GUIDE.md`（模板与常用 JSON 片段）。
2. **节点设计与约束**：`docs/workflow/WORKFLOW_NODE_DESIGN.md`。
3. **控制面能力差距 / 验收**（维护演进用）：`docs/workflow/WORKFLOW_CONTROL_PLANE_V3_GAP_ANALYSIS.md`、`WORKFLOW_CONTROL_PLANE_V3_ACCEPTANCE_CHECKLIST.md`。
4. **本地联调用例**：`docs/workflow/WORKFLOW_TEST_CASES_LOCAL.md`。

## 3. 实操原则（摘录）

- 先打通最小链路（`start` → `input` → `llm` → `output`），再增加条件与循环。
- 输入输出字段命名保持一致（如统一 `query` / `topic`），减少映射错误。
- 生产环境优先执行 **已发布** 版本的工作流定义。

## 4. 与插件、Agent 的关系

- **插件**：偏「单次请求上的横切能力」（如 RAG 注入），由插件系统在 Chat/Agent 模式下调度。
- **Workflow 节点**：偏「多步编排与分支」；其中 `llm` / `agent` 节点仍通过网关访问模型与工具。

二者可同时使用：例如在网关入口启用 RAG 插件，在工作流中编排多步推理与工具调用。

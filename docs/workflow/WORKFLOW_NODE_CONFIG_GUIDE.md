# Workflow 节点配置指南（实操版）

更新时间：2026-05-26

## 1. 适用范围

本文用于本地联调时快速配置 Workflow 节点，覆盖当前常用节点：

- `start` / `input` / `output` / `variable`
- `llm`（含 `model_tier`）/ `embedding` / `agent`
- `prompt_template` / `system_prompt`（持久化为 `prompt_template` + `role=system`）
- `condition` / `loop` / `fork` / `join` / `parallel`（并行限流）
- `checkpoint` / `verify_loop`
- `http_request` / `python` / `shell` / `tool`
- `script` / `replan` / `approval` / `sub_workflow`

---

## 2. 通用规则

1. **先连通再收紧**：先保证链路可跑，再加 schema/条件/超时。
2. **输入字段统一**：尽量统一使用 `query` 或 `topic`，减少节点映射复杂度。
3. **输出明确落 key**：`output` 节点建议始终配置 `output_key`。
4. **节点命名可读**：如 `user_input` / `agent_search` / `final_output`，方便排障。
5. **先发布再跑（生产）**：开发环境可跑 draft，生产建议只跑 published。

---

## 3. 节点模板

## 3.1 start

用途：流程入口，无需复杂配置。

```json
{
  "workflow_node_type": "start"
}
```

---

## 3.2 input

用途：承接执行入参，支持裁剪输入。

最小模板（透传所有 `input_data`）：

```json
{
  "workflow_node_type": "input"
}
```

按 key 裁剪：

```json
{
  "workflow_node_type": "input",
  "input_key": "topic"
}
```

带结构约定（编辑器提示用）：

```json
{
  "workflow_node_type": "input",
  "input_key": "topic",
  "input_schema": {
    "type": "object",
    "properties": {
      "topic": { "type": "string" }
    },
    "required": ["topic"]
  }
}
```

---

## 3.3 output

用途：把中间结果落到 `execution.output_data`。

推荐模板（显式 `output_key + expression`）：

```json
{
  "workflow_node_type": "output",
  "output_key": "result",
  "expression": "${nodes.agent_search.output.response}"
}
```

无 expression 时会尽量透传上游输出。

---

## 3.4 llm

用途：直接模型推理。

```json
{
  "workflow_node_type": "llm",
  "model_id": "local:qwen3-8b",
  "temperature": 0.3,
  "max_tokens": 1024,
  "system_prompt": "你是一个严谨的技术助手。",
  "prompt_template": "请回答：${input.query}"
}
```

建议：

- **二选一**：显式 `model_id`，或 `model_tier`（`low` | `standard` | `thorough`），由 `ModelSelector` 解析模型
- 长文本任务适当提高 `max_tokens`
- `prompt` / `prompt_template` 中只引用已存在字段

`model_tier` 示例：

```json
{
  "workflow_node_type": "llm",
  "model_tier": "thorough",
  "prompt": "请输出 JSON，含 text 与 summary 字段：${input.task}",
  "temperature": 0.3
}
```

---

## 3.5 agent

用途：调用已有智能体执行复杂任务。

```json
{
  "workflow_node_type": "agent",
  "agent_id": "agent_f6887b0e",
  "prompt": "请根据用户问题给出 5 条高质量资料，并附链接。",
  "timeout": 180,
  "max_steps": 6,
  "pass_context_keys": ["query", "topic"]
}
```

可选默认输入（避免空输入）：

```json
{
  "workflow_node_type": "agent",
  "agent_id": "agent_f6887b0e",
  "fixed_input": {
    "query": "请总结 Rust 入门资料"
  }
}
```

注意：

- 常见错误：`AGENT_NODE_INPUT_EMPTY`
- 至少保证有可解析输入（`prompt/query/topic/...`）

---

## 3.6 tool

用途：直接执行工具（不经 agent 规划）。

```json
{
  "workflow_node_type": "tool",
  "tool_name": "builtin_web.search",
  "fixed_input": {
    "query": "Rust 入门资料",
    "top_k": 5
  }
}
```

注意：

- `tool_name` 或 `tool_id` 必须存在，否则会报兼容性错误。

---

## 3.7 condition

用途：布尔分支控制。

```json
{
  "workflow_node_type": "condition",
  "expression": "${input.query}",
  "operator": "contains_any",
  "value": ["最新", "新闻", "官网", "search"],
  "output_key": "need_web_search"
}
```

边建议：

- `condition -> web_branch`（true）
- `condition -> local_branch`（false）

---

## 3.8 loop

用途：多轮迭代优化结果。

```json
{
  "workflow_node_type": "loop",
  "max_iterations": 2,
  "index_key": "loop_index",
  "item_key": "current_draft",
  "init_expression": "${nodes.draft_llm.output.response}",
  "continue_when": "${loop_index < 2}"
}
```

注意：

- 建议先小轮次（2~3）验证
- 必须有明确退出条件，避免长时间运行

---

## 3.9 script

用途：执行脚本逻辑（转换、拼接、格式化等）。

```json
{
  "workflow_node_type": "script",
  "language": "python",
  "timeout": 900
}
```

建议：

- 长脚本用较大 `timeout`
- 输入输出尽量 JSON 化，便于下游节点消费

---

## 3.10 replan

用途：失败后重规划（恢复路径）。

```json
{
  "workflow_node_type": "replan",
  "max_replans": 1,
  "strategy": "fallback"
}
```

建议：

- 先在失败注入场景验证 replan 是否生效

---

## 3.11 parallel（并行限流）

用途：限制处于某并行域内的 **最大同时 RUNNING 节点数**（不是 Fork 扇出）。

```json
{
  "workflow_node_type": "parallel",
  "max_parallel": 5
}
```

---

## 3.12 fork（扇出）

用途：标记并行分支起点；从本节点拉出 **多条 SUCCESS 边** 到不同下游即可并行执行。

```json
{
  "workflow_node_type": "fork",
  "branch_hint": "research | implement"
}
```

---

## 3.13 join（汇聚）

用途：等待上游分支完成后合并；调度器为 Join 注入 `branches: { "<nodeId>": <output> }`。

```json
{
  "workflow_node_type": "join",
  "dependency_mode": "all",
  "merge_mode": "flat"
}
```

- `dependency_mode`：`all`（默认，等待全部入边）| `any`
- `merge_mode`：`flat`（扁平合并 + branches）| `branches_only`

---

## 3.14 checkpoint（验收检查点）

用途：对上游输出做 **确定性** 验收；未通过时节点失败并阻断后续步骤。

```json
{
  "workflow_node_type": "checkpoint",
  "description": "交付物须含 text",
  "required_keys": ["text", "summary"],
  "min_nonempty_fields": 0,
  "forbid_error_key": true
}
```

---

## 3.15 verify_loop（Ralph 验证环）

用途：重复执行 `loop_body`，每轮按 checkpoint 规则验收，通过即退出。

```json
{
  "workflow_node_type": "verify_loop",
  "max_iterations": 5,
  "required_keys": ["text"],
  "forbid_error_key": true,
  "loop_body": {
    "type": "llm",
    "model_tier": "thorough",
    "prompt": "完成任务，输出 JSON 含 text：${input.task}"
  }
}
```

`loop_body.type` 支持：`llm` | `tool` | `agent`（及 manager/worker/reflector）。

---

## 3.16 embedding / http_request / python / variable

**Embedding**（须 `model_id`）：

```json
{
  "workflow_node_type": "embedding",
  "model_id": "<embedding-model-id>",
  "input_text": "${input.text}"
}
```

**HTTP**（经 `http.request` 工具，须 `url`）：

```json
{
  "workflow_node_type": "http_request",
  "tool_name": "http.request",
  "url": "https://api.example.com/data",
  "method": "GET",
  "timeout": 30
}
```

**Python**（仅 `python.run`，须 `code`）：

```json
{
  "workflow_node_type": "python",
  "code": "print({'text': 'ok'})"
}
```

**Variable**（写入全局 `workflow_variables`）：

```json
{
  "workflow_node_type": "variable",
  "variables": {
    "topic": "${input.query}",
    "lang": "zh"
  }
}
```

---

## 4. 推荐最小可跑模板（A/B/C/D/E）

1. **A（基础）**：`start -> input -> agent -> output`
2. **B（分支）**：`start -> input -> condition -> (agent|llm) -> output`
3. **C（迭代）**：`start -> input -> llm -> loop -> llm -> output`
4. **D（并行小队）**：`start -> input -> fork -> (llm|llm) -> join -> checkpoint -> output`
5. **E（Ralph）**：`start -> input -> verify_loop -> output`

也可在编辑器使用 **「高价值编排模板（OmX）」** 一键导入 D/E 等链路。

---

## 5. 常见报错与处理

1. `AGENT_NODE_INPUT_EMPTY`
- 原因：agent 节点没有拿到可解析输入。
- 处理：在 `agent` 节点加 `prompt` 或 `fixed_input.query`；确认上游 `input_key` 正确。

2. `Tool node ... missing 'tool_name' or 'tool_id'`
- 原因：tool 节点缺必填字段。
- 处理：补 `tool_name`。

3. `Version cannot be executed` / draft 相关告警
- 原因：执行版本状态不允许。
- 处理：发布版本后再执行，或仅在开发模式允许 draft。

4. 状态长时间 `pending/running`
- 原因：并发排队、长耗时节点、或状态回填延迟。
- 处理：看 run 页 logs + 后端 `ExecutionManager` 告警；必要时 `reconcile`。

5. `Checkpoint node ... requires 'required_keys' or min_nonempty_fields`
- 原因：发布/执行前校验未配置验收条件。
- 处理：为 checkpoint / verify_loop 配置 `required_keys` 或 `min_nonempty_fields > 0`。

6. `LLM node missing model_id or model_tier`
- 原因：LLM 未选模型也未选分档。
- 处理：设置 `model_id` 或 `model_tier`（low/standard/thorough）。

7. Join 长期不执行
- 原因：`dependency_mode=all` 时仍有分支未完成或失败。
- 处理：检查 Fork 下游各分支是否均 SUCCESS 到达 Join；或改为 `dependency_mode=any`（慎用）。

# Demo Playbook 01 · 发布简报门禁（多智能体 + HITL）

预计时长：**25～35 分钟**  
配套 JSON：`demos/workflows/demo1-release-brief-gate.bundle.json`  
编排专文：`docs/workflow/WORKFLOW_ORCHESTRATION_OVERVIEW_ZH.md`

---

## 1. 你要演示什么

| 能力 | 本 Demo 节点 |
|------|----------------|
| 顺序多角色（澄清 / 计划 / 执行） | `llm` + `prompt_template` + `llm` |
| **用户掌控：人工审批门** | `approval`（执行 PAUSED，须 approve） |
| **机器验收** | `checkpoint`（`required_keys`） |
| 模型分档 | Clarify `standard`，Execute `thorough` |

**推荐（多 Agent）**：工作流列表页 **一键导入演示包** `release-brief-gate`（自动创建澄清员/写手 Agent 并绑定节点）。

**画布轻量版**：下方「导入工作流」仅载入 DAG，节点为 **LLM 扮演多角色**（零 Agent 即可跑通编排与审批/验收）。

---

## 2. 前置条件

- [ ] 网关与前端已启动（见 `tutorial-quickstart.md`）
- [ ] `GET /api/models` 或 `/models` 页面有可用 LLM
- [ ] （进阶）在 `/agents` 创建 **发布写手** Agent，`model_tier` 或模型选 reasoning/thorough 档

---

## 3. 导入工作流

**方式 A — UI**

1. `/workflow/create` → **演示项目（多智能体）** → 选 **Demo 1 · 发布简报门禁** → **导入演示项目**。
2. 工作流名称应变为 `Demo · 发布简报门禁`。

**方式 B — 脚本**

```bash
PYTHONPATH=backend python3 scripts/import_demo_workflow.py \
  demos/workflows/demo1-release-brief-gate.bundle.json
```

记下输出的 `workflow_id`，浏览器打开 `/workflow/{workflow_id}/edit`。

---

## 4. 配置检查（导入后）

| 节点 | 检查项 |
|------|--------|
| `input_brief` | `input_key` = `brief` |
| `clarify` | `model_tier: standard` 或已选 `model_id` |
| `approval_plan` | 标题/说明可读 |
| `execute` | `model_tier: thorough`；进阶：改类型为 **Agent** 并填 `agent_id` |
| `checkpoint_verify` | `required_keys`: `text`, `summary` |

点击 **预检** → **保存** → **发布版本**（建议）。

---

## 5. 演示脚本（建议逐步讲解）

### 步骤 1 — 输入

Run 页 JSON：

```json
{
  "brief": "下月 v1.2 发布公告，面向开发者，强调工作流编排与多 Agent 控制能力。"
}
```

### 步骤 2 — 观察澄清与计划

Timeline：`clarify` → `plan` 依次 SUCCESS。强调 **编排固定顺序**，非 Agent 自主跳转。

### 步骤 3 — 审批门控（重点）

执行在 `approval_plan` 进入 **PAUSED**。列出待办审批：

```bash
curl -s "http://127.0.0.1:8000/api/v1/workflows/{workflow_id}/executions/{execution_id}/approvals" \
  -H "X-Tenant-Id: default" | jq .
```

批准（将 `{task_id}` 替换为返回 id）：

```bash
curl -s -X POST \
  "http://127.0.0.1:8000/api/v1/workflows/{workflow_id}/executions/{execution_id}/approvals/{task_id}/approve" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Id: default" \
  -d '{"comment":"计划可行，继续执行"}' | jq .
```

讲解：**未批准则下游不执行**（User-in-Control）。

### 步骤 4 — 执行与验收

`execute` → `checkpoint_verify` → `output_deliverable`。  
`output_data.deliverable` 应含非空 `text`、`summary`。

### 步骤 5 — 对比实验（可选，5 分钟）

重新 Run，对审批调用 **reject**，确认流程不继续执行。

### 步骤 6 — Checkpoint 失败实验（可选）

临时把 `required_keys` 改为 `["nonexistent"]`，保存草稿 Run，观察 checkpoint 阻断。

---

## 6. 进阶：Execute 改为 Agent

1. `/agents` 创建写手，启用所需 Skill（可无工具，纯文本生成亦可）。
2. 画布删除 `execute`（LLM），从节点库拖入 **Agent**，连线 `approval_plan` → Agent → `checkpoint_verify`。
3. Agent 配置：`agent_id`、prompt 与 bundle 中 LLM prompt 类似；`pass_context_keys: ["brief"]`。
4. 再跑步骤 1～4，强调 **Agent 仅在审批后、固定节点** 被网关调用。

---

## 7. 通过标准

- [ ] 未审批前执行状态为 PAUSED，无 `execute` SUCCESS
- [ ] approve 后执行完成，Checkpoint 通过
- [ ] `deliverable` 含 `text` 与 `summary`
- [ ] reject 实验下下游不执行（若做了步骤 5）

---

## 8. 排障

| 现象 | 处理 |
|------|------|
| LLM 节点失败 | `/models` 探活；为节点选 `model_id` |
| 一直 PAUSED | 确认已调用 approve API |
| Checkpoint 失败 | Inspector 看上游 JSON 是否含 `text`/`summary` |
| 403 / 租户 | 请求带 `X-Tenant-Id`，见 `tutorial.md` 多租户节 |

---

## 9. 相关链接

- 节点 JSON 模板：`docs/workflow/WORKFLOW_NODE_CONFIG_GUIDE.md` §3.14～3.15、approval 节
- 索引：`tutorial-index.md` §1.2

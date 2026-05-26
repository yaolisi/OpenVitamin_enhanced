# Demo Playbook 02 · 并行双源调研验证环

预计时长：**30～40 分钟**  
配套 JSON：`demos/workflows/demo2-parallel-research-verify.bundle.json`  
编排专文：`docs/workflow/WORKFLOW_ORCHESTRATION_OVERVIEW_ZH.md`

---

## 1. 你要演示什么

| 能力 | 本 Demo 节点 |
|------|----------------|
| **Fork / Join** 并行编排 | `fork_parallel` → 双分支 → `join_merge` |
| 异构能力（Web vs KB） | 默认双 **LLM**；进阶换 **双 Agent** |
| **Verify Loop（Ralph）** | `verify_ralph`，`required_keys: text, sources` |
| 模型分档 | 分支 `standard`，验证环 body `thorough` |

---

## 2. 前置条件

- [ ] 网关与前端已启动
- [ ] `GET /api/models` 可用
- [ ] （推荐）`/knowledge` 建库并上传 1 份 FAQ（如 `Perilla-FAQ.md`），等待 **INDEXED**
- [ ] （进阶）`/agents` 创建两个 Agent：
  - **Web 调研员**：`builtin_web.search`
  - **KB 分析员**：`builtin_kb.query`（绑定知识库）

---

## 3. 导入工作流

**UI**：`/workflow/create` → **演示项目** → **Demo 2 · 并行双源调研验证环** → **导入演示项目**。

**脚本**：

```bash
PUBLISH=1 PYTHONPATH=backend python3 scripts/import_demo_workflow.py \
  demos/workflows/demo2-parallel-research-verify.bundle.json
```

---

## 4. 配置检查

| 节点 | 检查项 |
|------|--------|
| `input_topic` | `input_key` = `topic` |
| `fork_parallel` / `join_merge` | Join `dependency_mode: all` |
| `branch_web` / `branch_kb` | `model_tier: standard` 或 `model_id`；进阶改为 Agent |
| `verify_ralph` | `max_iterations: 3`，`loop_body.model_tier: thorough` |

预检 → 保存 → 发布。

---

## 5. 演示脚本

### 步骤 1 — 准备知识库（约 10 分钟，可提前做）

1. `/knowledge` → 新建知识库 → 上传短文档。
2. 确认文档状态为已索引。

### 步骤 2 — Run 输入

```json
{
  "topic": "Perilla 工作流编排与多 Agent 控制相比纯 Chat 的优势"
}
```

### 步骤 3 — 观察并行段（重点）

Timeline 中 `branch_web` 与 `branch_kb` 应 **接近同时 RUNNING**。  
讲解：**Fork 扇出、Join 等待全部分支 SUCCESS 才汇聚**。

### 步骤 4 — Verify Loop

`verify_ralph` 可能多轮迭代；节点输出应含 `verify_loop_passed: true` 与 `iterations` ≤ 3。  
最终 `output_data.research_result` 非空，且含 `text`、`sources`。

### 步骤 5 — 失败实验（可选）

将 `required_keys` 临时改为 `["impossible_field"]`，Run 观察 `verify_loop_failed` 与迭代耗尽（可控失败）。

### 步骤 6 — 进阶：LLM 换 Agent

1. 将 `branch_web`、`branch_kb` 改为 **Agent** 节点，绑定步骤 2 前置里创建的 Agent。
2. Web Agent prompt 示例：`请检索并总结与主题相关的 5 条要点，附来源。主题：{{global.input_data.topic}}`
3. KB Agent prompt 示例：`请从知识库检索并总结 5 条要点。主题：{{global.input_data.topic}}`
4. 再 Run，对比 Timeline 中 **工具调用 / Skill** 痕迹（若可观测）。

---

## 6. 通过标准

- [ ] 两分支均 SUCCESS 后 Join 才执行
- [ ] Verify Loop 通过，`research_result` 含 `text` 与 `sources`
- [ ] （进阶）Agent 版能体现 Web 与 KB 两路差异

---

## 7. 排障

| 现象 | 处理 |
|------|------|
| Join 长期 pending | 检查是否有一路分支 FAILED；见 `WORKFLOW_NODE_CONFIG_GUIDE.md` §5 |
| Verify Loop 耗尽 | 放宽 `required_keys` 或加强 `loop_body` prompt |
| KB Agent 无结果 | 确认知识库 INDEXED、Agent 已启用 `builtin_kb.query` |
| Parallel 与 Fork 混淆 | 本 Demo 用 **Fork**；`parallel` 节点仅为限流，见教程 §9.7 |

---

## 8. 与 Demo 1 对照讲解（收尾 3 分钟）

| | Demo 1 | Demo 2 |
|---|--------|--------|
| 控制 | 人审批 + Checkpoint | Join 调度 + Verify Loop |
| 并行 | 无 | Fork/Join |
| 典型场景 | 发布/变更门禁 | 多源调研汇总 |

---

## 9. 相关链接

- 本地 Case D/E：`docs/workflow/WORKFLOW_TEST_CASES_LOCAL.md` §12～13
- `demos/workflows/README.md`

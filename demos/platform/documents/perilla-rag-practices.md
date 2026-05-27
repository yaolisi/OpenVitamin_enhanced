# 知识库与 RAG 使用要点

## 文档准备

- 支持 **TXT / MD / PDF / DOCX**，单文件建议小于 20MB。
- 上传后需等待 **索引完成**（状态 INDEXED）再检索。
- `chunk_size` 与 `chunk_overlap` 影响召回粒度；技术文档可用 512/50。

## Agent 绑定

在 Agent 配置的 **rag_ids** 中勾选知识库后，运行时会通过 **builtin_kb.query** 检索片段并注入上下文。

## 工作流中的 KB 分支

并行调研 Demo 中，一路为 Web 检索（`builtin_web.search`），一路为 KB 分析（绑定本库）。Join 后由 Verify Loop 汇总为带 `sources` 的结构化输出。

## 验收字段

本 Demo 要求最终 JSON 含非空 **text** 与 **sources** 数组，便于 Checkpoint / Verify Loop 自动验收。

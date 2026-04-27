/**
 * 与后端 `core/agent_runtime/reflection/tool_failure_suggest.py` 中
 * `MAX_REFLECTIONS_PER_PLAN_RUN` 一致（单次计划执行内失败反思 LLM 调用上限）。
 * 若后端调整，请同步修改此处与相关 i18n。
 */
export const TOOL_FAILURE_REFLECTION_MAX_PER_PLAN_RUN = 5

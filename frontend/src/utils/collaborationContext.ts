/** 多 Agent 协同：与后端 collaboration.py 的 correlation_id 约定对齐 */

export function generateCorrelationId(prefix = 'corr'): string {
  const hex =
    typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID().replace(/-/g, '').slice(0, 24)
      : `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`
  return `${prefix}_${hex}`
}

export function buildDefaultCollaborationGlobalContext(
  orchestratorAgentId?: string,
): Record<string, unknown> {
  const ctx: Record<string, unknown> = {
    correlation_id: generateCorrelationId(),
  }
  const orch = (orchestratorAgentId || '').trim()
  if (orch) ctx.orchestrator_agent_id = orch
  return ctx
}

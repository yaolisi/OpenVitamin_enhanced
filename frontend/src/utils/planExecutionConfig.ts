/**
 * Agent `model_params.plan_execution`：与后端
 * `core.agent_runtime.v2.runtime._apply_agent_plan_execution_defaults` 对齐（仅把仍为默认空的 Plan 字段填上）。
 *
 * 与「系统设置 → 运行时」里的 `agentPlanMaxParallelSteps` 等是两层：系统给全局底；本对象给**该 Agent** 的 Plan 默认。
 *
 * 示例（可抄进 `model_params` 或用于 API/脚本）：
 * ```json
 * {
 *   "plan_execution": {
 *     "max_parallel_in_group": 4,
 *     "default_timeout_seconds": 30,
 *     "default_max_retries": 2,
 *     "default_retry_interval_seconds": 1,
 *     "default_on_timeout_strategy": "continue"
 *   }
 * }
 * ```
 *
 * 字段说明：
 * - `max_parallel_in_group`：1–64，与全局并发取 min 后仍受 `Plan.max_parallel_in_group` 约束
 * - `default_timeout_seconds`：单步无 `timeout_seconds` 时的秒数
 * - `default_max_retries` / `default_retry_interval_seconds`：步骤级重试
 * - `default_on_timeout_strategy`：`stop` | `continue` | `replan`（与步骤超时时策略一致）
 */

export type OnTimeoutStrategy = 'stop' | 'continue' | 'replan'

export interface PlanExecutionConfig {
  max_parallel_in_group?: number
  default_timeout_seconds?: number
  default_max_retries?: number
  default_retry_interval_seconds?: number
  default_on_timeout_strategy?: OnTimeoutStrategy
}

/** 表单/界面状态（0 与空 表示不写入对应键） */
export interface PlanExecutionFormState {
  maxParallelInGroup: number
  defaultTimeoutSeconds: number
  defaultMaxRetries: number
  retryIntervalSeconds: number
  onTimeoutStrategy: '' | OnTimeoutStrategy
}

export function defaultPlanExecutionFormState(): PlanExecutionFormState {
  return {
    maxParallelInGroup: 0,
    defaultTimeoutSeconds: 0,
    defaultMaxRetries: 0,
    retryIntervalSeconds: 1,
    onTimeoutStrategy: '',
  }
}

/**
 * 从 model_params.plan_execution 回填表单（无配置或异常时回退默认空状态）。
 */
export function loadPlanExecutionFormFromModelParams(
  modelParams: Record<string, unknown> | null | undefined,
): PlanExecutionFormState {
  const s = defaultPlanExecutionFormState()
  const raw = modelParams && typeof modelParams === 'object' && modelParams
    ? (modelParams as { plan_execution?: unknown }).plan_execution
    : undefined
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return s
  }
  const pe = raw as Record<string, unknown>
  const mp = Math.floor(Number(pe.max_parallel_in_group) || 0)
  s.maxParallelInGroup = mp > 0 ? Math.min(64, mp) : 0
  const to = Math.floor(Number(pe.default_timeout_seconds) || 0)
  s.defaultTimeoutSeconds = to > 0 ? to : 0
  const mr = Math.floor(Number(pe.default_max_retries) || 0)
  s.defaultMaxRetries = mr > 0 ? Math.min(20, mr) : 0
  const ri = Number(pe.default_retry_interval_seconds)
  s.retryIntervalSeconds = Number.isFinite(ri) && ri >= 0 ? Math.min(60, ri) : 1
  const ots = String(pe.default_on_timeout_strategy || '').toLowerCase()
  if (ots === 'stop' || ots === 'continue' || ots === 'replan') {
    s.onTimeoutStrategy = ots
  }
  return s
}

/**
 * 构建要写入 model_params 的 plan_execution 对象；空行为返回 null（调用方不写入或删除键）。
 */
export function buildPlanExecutionPayload(form: PlanExecutionFormState): PlanExecutionConfig | null {
  const pe: PlanExecutionConfig = {}
  if (form.maxParallelInGroup > 0) {
    pe.max_parallel_in_group = Math.min(64, Math.max(1, Math.floor(Number(form.maxParallelInGroup))))
  }
  if (form.defaultTimeoutSeconds > 0) {
    pe.default_timeout_seconds = Math.min(3600, Math.max(1, Math.floor(Number(form.defaultTimeoutSeconds))))
  }
  if (form.defaultMaxRetries > 0) {
    pe.default_max_retries = Math.min(20, Math.max(0, Math.floor(Number(form.defaultMaxRetries))))
    pe.default_retry_interval_seconds = Math.min(60, Math.max(0, Number(form.retryIntervalSeconds) || 1))
  }
  if (form.onTimeoutStrategy === 'stop' || form.onTimeoutStrategy === 'continue' || form.onTimeoutStrategy === 'replan') {
    pe.default_on_timeout_strategy = form.onTimeoutStrategy
  }
  return Object.keys(pe).length > 0 ? pe : null
}

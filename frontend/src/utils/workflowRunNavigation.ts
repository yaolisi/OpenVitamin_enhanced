import type { LocationQuery } from 'vue-router'

/**
 * 合并当前路由上的查询参数到「新建 / 自动开始」运行页跳转：
 * 保留 input_data、global_context、version_id 等预设，
 * 移除 execution_id（避免与新运行冲突），并附加 auto_start、t。
 */
export function buildWorkflowNewRunQuery(fromQuery: LocationQuery): LocationQuery {
  const q: LocationQuery = { ...fromQuery }
  delete q.execution_id
  delete q.executionId
  delete q.history_only
  q.auto_start = '1'
  q.t = String(Date.now())
  return q
}

/** 新建运行页：预填 input_data / global_context（JSON 字符串放入 query） */
export function buildWorkflowRunPresetQuery(options: {
  inputData?: Record<string, unknown>
  globalContext?: Record<string, unknown>
  versionId?: string
  autoStart?: boolean
}): LocationQuery {
  const q: LocationQuery = { t: String(Date.now()) }
  if (options.inputData && Object.keys(options.inputData).length > 0) {
    q.input_data = JSON.stringify(options.inputData)
  }
  if (options.globalContext && Object.keys(options.globalContext).length > 0) {
    q.global_context = JSON.stringify(options.globalContext)
  }
  if (options.versionId) q.version_id = options.versionId
  if (options.autoStart !== false) q.auto_start = '1'
  return q
}

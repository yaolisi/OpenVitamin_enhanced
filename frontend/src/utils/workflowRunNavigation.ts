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

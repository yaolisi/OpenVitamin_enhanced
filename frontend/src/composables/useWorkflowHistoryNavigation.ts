import { useRouter, useRoute } from 'vue-router'

/**
 * 进入只读执行追踪：/workflow/:id/history → 重定向为 run 页并带 history_only=1。
 * 合并当前 route.query（与列表/编辑/详情上透传 input_data、version_id 等行为一致）。
 */
export function useWorkflowHistoryNavigation() {
  const router = useRouter()
  const route = useRoute()

  function openWorkflowHistoryReadonly(workflowId: string) {
    const id = String(workflowId ?? '').trim()
    if (!id) return
    void router.push({
      name: 'workflow-history',
      params: { id },
      query: route.query,
    })
  }

  return { openWorkflowHistoryReadonly }
}

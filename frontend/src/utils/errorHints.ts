export function getFriendlyErrorMessage(raw: unknown): string {
  const fallback = typeof raw === 'string' && raw.trim() ? raw : '请求失败，请稍后重试'
  const text = String(raw || '').toLowerCase()

  if (!text) return fallback

  if (text.includes('out of memory') || text.includes('cuda out of memory') || text.includes('显存') || text.includes('oom')) {
    return '模型调用失败：显存不足（OOM）。请降低上下文长度、切换更小模型或释放 GPU 占用。'
  }
  if (text.includes('weight') || text.includes('checkpoint') || text.includes('corrupt') || text.includes('损坏')) {
    return '模型调用失败：模型权重文件可能损坏。请重新下载或校验模型文件完整性。'
  }
  if (text.includes('timeout') || text.includes('timed out') || text.includes('超时')) {
    return '模型调用失败：请求超时。请稍后重试，或降低生成长度与并发。'
  }
  if (text.includes('connection') || text.includes('network') || text.includes('econnrefused') || text.includes('enotfound')) {
    return '模型调用失败：网络或服务连接异常。请检查后端服务、模型服务与网络连通性。'
  }
  if (text.includes('permission') || text.includes('forbidden') || text.includes('unauthorized') || text.includes('403') || text.includes('401')) {
    return '请求失败：权限不足或鉴权失效。请检查 API Key、租户与权限范围配置。'
  }

  return fallback
}

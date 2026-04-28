import { onMounted, onUnmounted } from 'vue'

import { PERILLA_SYSTEM_CONFIG_CHANGED } from '@/constants/platformEvents'

/** 监听 `notifySystemConfigChanged()`（如 `updateSystemConfig` 成功后）。多数页面请用 `useDebouncedOnSystemConfigChange`，避免短时多次保存触发重复请求。 */
export function useListenSystemConfigChanged(handler: () => void) {
  const listener = () => {
    handler()
  }
  onMounted(() => {
    if (typeof window === 'undefined') return
    window.addEventListener(PERILLA_SYSTEM_CONFIG_CHANGED, listener)
  })
  onUnmounted(() => {
    if (typeof window === 'undefined') return
    window.removeEventListener(PERILLA_SYSTEM_CONFIG_CHANGED, listener)
  })
}

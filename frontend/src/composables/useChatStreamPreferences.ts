import { ref, watch } from 'vue'
import type { ChatStreamFormat } from '@/services/api'

const KEY_GZIP = 'ai_platform_chat_stream_gzip'
const KEY_FORMAT = 'ai_platform_chat_stream_format'

function parseFormat(raw: string | null): ChatStreamFormat {
  if (raw === 'jsonl' || raw === 'markdown' || raw === 'openai') {
    return raw
  }
  return 'openai'
}

const streamGzip = ref(false)
const streamFormat = ref<ChatStreamFormat>('openai')
const loaded = ref(false)

function loadFromStorage() {
  try {
    const gz = localStorage.getItem(KEY_GZIP)
    streamGzip.value = gz === '1' || gz === 'true'
    streamFormat.value = parseFormat(localStorage.getItem(KEY_FORMAT))
  } catch {
    // ignore
  } finally {
    loaded.value = true
  }
}

if (typeof window !== 'undefined') {
  loadFromStorage()
  watch(
    [streamGzip, streamFormat],
    () => {
      if (!loaded.value) {
        return
      }
      try {
        localStorage.setItem(KEY_GZIP, streamGzip.value ? '1' : '0')
        localStorage.setItem(KEY_FORMAT, streamFormat.value)
      } catch {
        // storage full / private mode
      }
    },
    { deep: true },
  )
}

/**
 * 聊天流式：GZip 与输出格式偏好（仅 localStorage，按浏览器持久化，全局单例）
 */
export function useChatStreamPreferences() {
  return {
    streamGzip,
    streamFormat,
    load: loadFromStorage,
  }
}

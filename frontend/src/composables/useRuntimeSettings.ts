import { ref } from 'vue'
import { getSystemConfig, updateSystemConfig, type SystemConfig } from '@/services/api'

function parseBool(value: unknown, defaultVal: boolean): boolean {
  if (value === undefined || value === null) return defaultVal
  if (value === true || value === 1 || value === 'true') return true
  if (value === false || value === 0 || value === 'false') return false
  return defaultVal
}

export function useRuntimeSettings() {
  const autoUnloadLocalModelOnSwitch = ref(false)
  const runtimeAutoReleaseEnabled = ref(true)
  const runtimeMaxCachedLocalRuntimes = ref(1)
  const runtimeMaxCachedLocalLlmRuntimes = ref(1)
  const runtimeMaxCachedLocalVlmRuntimes = ref(1)
  const runtimeMaxCachedLocalImageGenerationRuntimes = ref(1)
  const runtimeReleaseIdleTtlSeconds = ref(300)
  const runtimeReleaseMinIntervalSeconds = ref(5)

  const config = ref<SystemConfig | null>(null)
  const isSaving = ref(false)
  const saveSuccess = ref(false)
  const saveError = ref('')
  const isEditing = ref(false)

  const loadConfig = async () => {
    try {
      const c = await getSystemConfig()
      config.value = c
      const s = c.settings ?? {}
      autoUnloadLocalModelOnSwitch.value = parseBool(s.autoUnloadLocalModelOnSwitch, false)
      runtimeAutoReleaseEnabled.value = parseBool(s.runtimeAutoReleaseEnabled, true)
      runtimeMaxCachedLocalRuntimes.value = Math.min(16, Math.max(1, Number(s.runtimeMaxCachedLocalRuntimes) || 1))
      runtimeMaxCachedLocalLlmRuntimes.value = Math.min(
        16,
        Math.max(1, Number(s.runtimeMaxCachedLocalLlmRuntimes) || runtimeMaxCachedLocalRuntimes.value || 1),
      )
      runtimeMaxCachedLocalVlmRuntimes.value = Math.min(
        16,
        Math.max(1, Number(s.runtimeMaxCachedLocalVlmRuntimes) || runtimeMaxCachedLocalRuntimes.value || 1),
      )
      runtimeMaxCachedLocalImageGenerationRuntimes.value = Math.min(
        16,
        Math.max(1, Number(s.runtimeMaxCachedLocalImageGenerationRuntimes) || runtimeMaxCachedLocalRuntimes.value || 1),
      )
      runtimeReleaseIdleTtlSeconds.value = Math.min(86400, Math.max(30, Number(s.runtimeReleaseIdleTtlSeconds) || 300))
      runtimeReleaseMinIntervalSeconds.value = Math.min(3600, Math.max(1, Number(s.runtimeReleaseMinIntervalSeconds) || 5))
      isEditing.value = false
    } catch (e) {
      console.error('Failed to load system config:', e)
    }
  }

  const handleSave = async (onAfterSave?: () => Promise<void>) => {
    isSaving.value = true
    saveError.value = ''
    try {
      await updateSystemConfig({
        autoUnloadLocalModelOnSwitch: Boolean(autoUnloadLocalModelOnSwitch.value),
        runtimeAutoReleaseEnabled: Boolean(runtimeAutoReleaseEnabled.value),
        runtimeMaxCachedLocalRuntimes: runtimeMaxCachedLocalRuntimes.value,
        runtimeMaxCachedLocalLlmRuntimes: runtimeMaxCachedLocalLlmRuntimes.value,
        runtimeMaxCachedLocalVlmRuntimes: runtimeMaxCachedLocalVlmRuntimes.value,
        runtimeMaxCachedLocalImageGenerationRuntimes: runtimeMaxCachedLocalImageGenerationRuntimes.value,
        runtimeReleaseIdleTtlSeconds: runtimeReleaseIdleTtlSeconds.value,
        runtimeReleaseMinIntervalSeconds: runtimeReleaseMinIntervalSeconds.value,
      })
      await loadConfig()
      if (onAfterSave) await onAfterSave()
      saveSuccess.value = true
      setTimeout(() => {
        saveSuccess.value = false
      }, 3000)
    } catch (e) {
      console.error('Failed to save runtime settings:', e)
      saveError.value = e instanceof Error ? e.message : String(e)
    } finally {
      isSaving.value = false
    }
  }

  return {
    autoUnloadLocalModelOnSwitch,
    runtimeAutoReleaseEnabled,
    runtimeMaxCachedLocalRuntimes,
    runtimeMaxCachedLocalLlmRuntimes,
    runtimeMaxCachedLocalVlmRuntimes,
    runtimeMaxCachedLocalImageGenerationRuntimes,
    runtimeReleaseIdleTtlSeconds,
    runtimeReleaseMinIntervalSeconds,
    config,
    isSaving,
    saveSuccess,
    saveError,
    isEditing,
    loadConfig,
    handleSave,
  }
}

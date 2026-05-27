import { ref } from 'vue'
import {
  getWorkflowPublishGate,
  publishWorkflowVersion,
  type PublishGateResult,
} from '@/services/api'

export function useWorkflowPublishGate(workflowId: string | (() => string)) {
  const resolveWorkflowId = () => (typeof workflowId === 'function' ? workflowId() : workflowId)
  const publishGateOpen = ref(false)
  const publishGateLoading = ref(false)
  const publishGatePublishing = ref(false)
  const publishGateError = ref<string | null>(null)
  const publishGateResult = ref<PublishGateResult | null>(null)
  const publishVersionId = ref('')
  const publishVersionLabel = ref('')

  async function openPublishGateForVersion(versionId: string, versionLabel = '') {
    publishVersionId.value = versionId
    publishVersionLabel.value = versionLabel
    publishGateOpen.value = true
    publishGateLoading.value = true
    publishGateError.value = null
    publishGateResult.value = null
    try {
      const wfId = resolveWorkflowId()
      if (!wfId) {
        publishGateError.value = 'workflow_not_saved'
        return
      }
      publishGateResult.value = await getWorkflowPublishGate(wfId, versionId)
    } catch (e) {
      publishGateError.value = (e as Error)?.message || String(e)
    } finally {
      publishGateLoading.value = false
    }
  }

  function closePublishGate() {
    if (publishGatePublishing.value) return
    publishGateOpen.value = false
  }

  async function confirmPublishFromGate(): Promise<boolean> {
    if (!publishGateResult.value?.allowed || !publishVersionId.value) return false
    publishGatePublishing.value = true
    publishGateError.value = null
    try {
      const wfId = resolveWorkflowId()
      if (!wfId) return false
      await publishWorkflowVersion(wfId, publishVersionId.value)
      publishGateOpen.value = false
      return true
    } catch (e) {
      publishGateError.value = (e as Error)?.message || String(e)
      return false
    } finally {
      publishGatePublishing.value = false
    }
  }

  return {
    publishGateOpen,
    publishGateLoading,
    publishGatePublishing,
    publishGateError,
    publishGateResult,
    publishVersionLabel,
    openPublishGateForVersion,
    closePublishGate,
    confirmPublishFromGate,
  }
}

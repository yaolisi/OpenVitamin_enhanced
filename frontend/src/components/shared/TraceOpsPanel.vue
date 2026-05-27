<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { ExternalLink, Loader2 } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { getTraceOpsView, type TraceOpsView } from '@/services/api'

const props = defineProps<{
  traceId?: string | null
  requestId?: string | null
  correlationId?: string | null
}>()

const { t } = useI18n()
const router = useRouter()
const loading = ref(false)
const error = ref<string | null>(null)
const view = ref<TraceOpsView | null>(null)

async function load() {
  const tid = (props.traceId || '').trim()
  const rid = (props.requestId || '').trim()
  const cid = (props.correlationId || '').trim()
  if (!tid && !rid && !cid) {
    view.value = null
    return
  }
  loading.value = true
  error.value = null
  try {
    view.value = await getTraceOpsView({
      trace_id: tid || undefined,
      request_id: rid || undefined,
      correlation_id: cid || undefined,
    })
  } catch (e) {
    error.value = (e as Error)?.message || String(e)
  } finally {
    loading.value = false
  }
}

watch(() => [props.traceId, props.requestId, props.correlationId], () => void load(), { immediate: true })
</script>

<template>
  <div v-if="traceId || requestId || correlationId" class="rounded-xl border border-border/80 bg-muted/15 px-4 py-3 text-xs space-y-2">
    <div class="flex items-center justify-between">
      <span class="font-semibold text-foreground">{{ t('trace_ops.title') }}</span>
      <Loader2 v-if="loading" class="w-3.5 h-3.5 animate-spin" />
    </div>
    <p v-if="error" class="text-red-500">{{ error }}</p>
    <template v-else-if="view">
      <p v-if="view.audit_logs?.length" class="text-muted-foreground">
        {{ t('trace_ops.audit_count', { n: view.audit_logs.length }) }}
      </p>
      <ul v-if="view.agent_sessions?.length" class="space-y-1">
        <li v-for="s in view.agent_sessions" :key="s.session_id" class="flex items-center gap-2">
          <span class="font-mono truncate">{{ s.session_id }}</span>
          <Button
            variant="ghost"
            size="sm"
            class="h-6 px-2"
            @click="router.push(`/agents/${s.agent_id}/trace?session=${s.session_id}`)"
          >
            <ExternalLink class="w-3 h-3" />
          </Button>
        </li>
      </ul>
      <p v-if="!view.agent_sessions?.length && !view.audit_logs?.length" class="text-muted-foreground">
        {{ t('trace_ops.empty') }}
      </p>
    </template>
  </div>
</template>

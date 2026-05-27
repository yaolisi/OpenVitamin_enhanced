<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { AlertTriangle, CheckCircle2, Info, Loader2 } from 'lucide-vue-next'
import type { PreflightResponse } from '@/services/api'

const props = defineProps<{
  preflight: PreflightResponse | null
  loading?: boolean
  error?: string | null
}>()

const { t } = useI18n()

const ready = computed(() => props.preflight?.ready === true)
const checks = computed(() => props.preflight?.checks ?? [])
</script>

<template>
  <div
    v-if="loading || error || preflight"
    class="rounded-xl border border-border/80 bg-muted/20 px-4 py-3 space-y-2 text-sm"
  >
    <div class="flex items-center justify-between gap-2">
      <span class="font-semibold text-foreground">{{ t('preflight.panel_title') }}</span>
      <span
        v-if="preflight && !loading"
        class="text-xs font-medium px-2 py-0.5 rounded-full"
        :class="ready ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300' : 'bg-amber-500/15 text-amber-800 dark:text-amber-300'"
      >
        {{ ready ? t('preflight.ready') : t('preflight.not_ready') }}
      </span>
      <Loader2 v-if="loading" class="w-4 h-4 animate-spin text-muted-foreground" />
    </div>
    <p v-if="error" class="text-red-500 text-xs">{{ error }}</p>
    <ul v-if="checks.length" class="space-y-1.5 max-h-40 overflow-y-auto">
      <li v-for="(c, i) in checks" :key="`${c.check}-${i}`" class="flex items-start gap-2 text-xs">
        <CheckCircle2 v-if="c.ok" class="w-3.5 h-3.5 text-emerald-500 shrink-0 mt-0.5" />
        <AlertTriangle
          v-else-if="c.severity === 'error'"
          class="w-3.5 h-3.5 text-amber-500 shrink-0 mt-0.5"
        />
        <Info v-else class="w-3.5 h-3.5 text-slate-400 shrink-0 mt-0.5" />
        <div class="min-w-0">
          <span :class="c.ok ? 'text-muted-foreground' : 'text-foreground'">{{ c.check }}</span>
          <p v-if="c.hint && !c.ok" class="text-muted-foreground mt-0.5">{{ c.hint }}</p>
        </div>
      </li>
    </ul>
  </div>
</template>

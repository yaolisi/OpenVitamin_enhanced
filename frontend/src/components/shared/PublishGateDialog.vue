<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { X, Rocket, ShieldAlert, ShieldCheck, Loader2 } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import PreflightPanel from '@/components/shared/PreflightPanel.vue'
import type { PublishGateResult } from '@/services/api'

const props = defineProps<{
  open: boolean
  loading?: boolean
  publishing?: boolean
  error?: string | null
  gate: PublishGateResult | null
  versionLabel?: string
}>()

const emit = defineEmits<{
  close: []
  confirmPublish: []
}>()

const { t } = useI18n()

const allowed = computed(() => props.gate?.allowed === true)
const issues = computed(() => (props.gate?.issues as Array<Record<string, unknown>>) ?? [])
const contractDiff = computed(() => props.gate?.contract_diff as Record<string, unknown> | undefined)
const breakingChanges = computed(() => {
  const list = contractDiff.value?.breaking_changes
  return Array.isArray(list) ? (list as string[]) : []
})
const riskyCount = computed(() => Number(props.gate?.risky_change_count ?? 0))
const impactedCount = computed(() => Number(props.gate?.impacted_count ?? 0))

function issueLabel(issue: Record<string, unknown>): string {
  const code = String(issue.code || 'issue')
  if (code === 'preflight_failed') {
    return `${t('publish_gate.issue_preflight')}: ${String(issue.check || '')}`
  }
  if (code === 'contract_breaking') {
    return t('publish_gate.issue_contract', { count: Number(issue.count ?? 0) })
  }
  if (code === 'subworkflow_breaking_impact') {
    return t('publish_gate.issue_subworkflow', { count: Number(issue.count ?? 0) })
  }
  if (code === 'version_not_found') {
    return t('publish_gate.issue_version_not_found')
  }
  return code
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      @click.self="emit('close')"
    >
      <div
        class="bg-card border border-border rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] flex flex-col overflow-hidden"
        @click.stop
      >
        <div class="px-6 pt-6 pb-4 border-b border-border shrink-0 flex items-start justify-between gap-4">
          <div class="min-w-0">
            <h2 class="text-xl font-bold text-foreground flex items-center gap-2">
              <ShieldCheck v-if="allowed && gate && !loading" class="w-5 h-5 text-emerald-500" />
              <ShieldAlert v-else class="w-5 h-5 text-amber-500" />
              {{ t('publish_gate.title') }}
            </h2>
            <p v-if="versionLabel" class="text-sm text-muted-foreground mt-1 truncate">
              {{ versionLabel }}
            </p>
          </div>
          <Button variant="ghost" size="icon" class="shrink-0" :disabled="publishing" @click="emit('close')">
            <X class="w-4 h-4" />
          </Button>
        </div>

        <div class="flex-1 min-h-0 overflow-y-auto px-6 py-4 space-y-4">
          <div v-if="loading" class="flex items-center gap-2 text-sm text-muted-foreground py-6 justify-center">
            <Loader2 class="w-5 h-5 animate-spin" />
            {{ t('publish_gate.evaluating') }}
          </div>

          <p v-else-if="error" class="text-sm text-red-500">{{ error }}</p>

          <template v-else-if="gate">
            <div class="flex flex-wrap items-center gap-2">
              <Badge :variant="allowed ? 'default' : 'secondary'">
                {{ allowed ? t('publish_gate.allowed') : t('publish_gate.blocked') }}
              </Badge>
              <span v-if="impactedCount > 0" class="text-xs text-muted-foreground">
                {{ t('publish_gate.impacted', { n: impactedCount }) }}
              </span>
              <span v-if="riskyCount > 0" class="text-xs text-amber-600 dark:text-amber-400">
                {{ t('publish_gate.risky', { n: riskyCount }) }}
              </span>
            </div>

            <PreflightPanel
              :preflight="(gate.preflight as import('@/services/api').PreflightResponse | undefined) ?? null"
            />

            <div v-if="issues.length" class="rounded-xl border border-amber-500/30 bg-amber-500/5 px-4 py-3 space-y-2">
              <p class="text-sm font-semibold text-foreground">{{ t('publish_gate.issues_title') }}</p>
              <ul class="text-xs space-y-1.5 text-muted-foreground list-disc pl-4">
                <li v-for="(issue, i) in issues" :key="i">
                  {{ issueLabel(issue) }}
                  <p v-if="issue.hint" class="text-muted-foreground/80 mt-0.5 list-none -ml-4 pl-0">
                    {{ issue.hint }}
                  </p>
                  <ul
                    v-if="Array.isArray(issue.items) && issue.items.length"
                    class="mt-1 list-none pl-0 space-y-0.5"
                  >
                    <li v-for="(item, j) in (issue.items as string[]).slice(0, 5)" :key="j" class="font-mono text-[11px]">
                      {{ item }}
                    </li>
                  </ul>
                </li>
              </ul>
            </div>

            <div
              v-if="breakingChanges.length"
              class="rounded-xl border border-border/80 bg-muted/20 px-4 py-3 space-y-2"
            >
              <p class="text-sm font-semibold">{{ t('publish_gate.breaking_title') }}</p>
              <ul class="text-xs font-mono space-y-1 max-h-32 overflow-y-auto text-muted-foreground">
                <li v-for="(line, i) in breakingChanges.slice(0, 12)" :key="i">{{ line }}</li>
              </ul>
            </div>

            <p v-if="!allowed" class="text-xs text-muted-foreground">{{ t('publish_gate.blocked_hint') }}</p>
            <p v-else class="text-xs text-muted-foreground">{{ t('publish_gate.allowed_hint') }}</p>
          </template>
        </div>

        <div class="px-6 py-4 border-t border-border shrink-0 flex justify-end gap-2">
          <Button variant="outline" :disabled="publishing" @click="emit('close')">
            {{ t('publish_gate.cancel') }}
          </Button>
          <Button
            class="gap-2 bg-indigo-600 hover:bg-indigo-700 text-white"
            :disabled="!allowed || loading || publishing || !gate"
            @click="emit('confirmPublish')"
          >
            <Loader2 v-if="publishing" class="w-4 h-4 animate-spin" />
            <Rocket v-else class="w-4 h-4" />
            {{ publishing ? t('publish_gate.publishing') : t('publish_gate.confirm_publish') }}
          </Button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

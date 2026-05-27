<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  ArrowLeft,
  Upload,
  Play,
  Loader2,
  CheckCircle2,
  XCircle,
  FileJson,
  Download,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { runEvalSuite, type EvalRunResult } from '@/services/api'

const router = useRouter()
const { t } = useI18n()

const jsonText = ref('')
const parseError = ref<string | null>(null)
const suiteId = ref('')
const stopOnFailure = ref(false)
const runPreflightFirst = ref(true)
const running = ref(false)
const runError = ref<string | null>(null)
const lastRun = ref<EvalRunResult | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)

const EXAMPLE_JSON = `{
  "suite_id": "agent-smoke",
  "cases": [
    {
      "id": "agent-exists",
      "target": "agent",
      "agent_id": "REPLACE_WITH_YOUR_AGENT_ID",
      "execute": false
    }
  ]
}`

function loadExample() {
  jsonText.value = EXAMPLE_JSON
  parseError.value = null
}

function parseSuite(): { suite_id?: string; cases: Array<Record<string, unknown>> } | null {
  parseError.value = null
  const raw = jsonText.value.trim()
  if (!raw) {
    parseError.value = t('eval.empty_json')
    return null
  }
  try {
    const data = JSON.parse(raw) as Record<string, unknown>
    const cases = data.cases
    if (!Array.isArray(cases) || cases.length === 0) {
      parseError.value = t('eval.invalid_cases')
      return null
    }
    const sid = typeof data.suite_id === 'string' ? data.suite_id : suiteId.value || undefined
    if (typeof data.suite_id === 'string') suiteId.value = data.suite_id
    return { suite_id: sid, cases: cases as Array<Record<string, unknown>> }
  } catch (e) {
    parseError.value = (e as Error)?.message || t('eval.parse_failed')
    return null
  }
}

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    jsonText.value = String(reader.result || '')
    parseError.value = null
  }
  reader.onerror = () => {
    parseError.value = t('eval.file_read_failed')
  }
  reader.readAsText(file)
  input.value = ''
}

function downloadResultJson() {
  if (!lastRun.value) return
  const blob = new Blob([JSON.stringify(lastRun.value, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `eval-run-${lastRun.value.run_id?.slice(0, 8) || 'result'}.json`
  a.click()
  URL.revokeObjectURL(url)
}

async function runBatch() {
  const parsed = parseSuite()
  if (!parsed) return
  running.value = true
  runError.value = null
  lastRun.value = null
  try {
    lastRun.value = await runEvalSuite({
      suite_id: parsed.suite_id || suiteId.value || undefined,
      cases: parsed.cases,
      stop_on_failure: stopOnFailure.value,
      run_preflight_first: runPreflightFirst.value,
    })
  } catch (e) {
    runError.value = (e as Error)?.message || String(e)
  } finally {
    running.value = false
  }
}

function goBack() {
  router.push({ name: 'settings-general' })
}

loadExample()
</script>

<template>
  <div class="flex flex-col h-full bg-background">
    <div class="flex items-center gap-4 px-8 py-6 border-b border-border/50 shrink-0">
      <Button variant="ghost" size="icon" @click="goBack">
        <ArrowLeft class="w-5 h-5" />
      </Button>
      <div class="flex-1 min-w-0">
        <h1 class="text-2xl font-bold tracking-tight flex items-center gap-2">
          <FileJson class="w-6 h-6 text-indigo-500" />
          {{ t('eval.title') }}
        </h1>
        <p class="text-sm text-muted-foreground mt-1">{{ t('eval.subtitle') }}</p>
      </div>
      <Button variant="outline" class="gap-2" :disabled="running" @click="loadExample">
        {{ t('eval.load_example') }}
      </Button>
    </div>

    <div class="flex-1 overflow-auto p-8">
      <div class="grid grid-cols-1 xl:grid-cols-2 gap-6 max-w-6xl mx-auto">
        <Card>
          <CardHeader>
            <CardTitle class="text-base">{{ t('eval.suite_json') }}</CardTitle>
          </CardHeader>
          <CardContent class="space-y-3">
            <div class="flex flex-wrap items-center gap-2">
              <input
                ref="fileInputRef"
                type="file"
                accept=".json,application/json"
                class="hidden"
                @change="onFileChange"
              />
              <Button variant="outline" size="sm" class="gap-2" @click="fileInputRef?.click()">
                <Upload class="w-4 h-4" />
                {{ t('eval.upload_json') }}
              </Button>
              <label class="text-xs text-muted-foreground flex items-center gap-2">
                {{ t('eval.suite_id') }}
                <input
                  v-model="suiteId"
                  class="h-8 w-40 rounded border border-input bg-background px-2 text-xs"
                  :placeholder="t('eval.suite_id_placeholder')"
                />
              </label>
            </div>
            <textarea
              v-model="jsonText"
              rows="16"
              class="w-full rounded-lg border border-input bg-background px-3 py-2 text-xs font-mono leading-relaxed"
              :placeholder="t('eval.json_placeholder')"
            />
            <p v-if="parseError" class="text-xs text-red-500">{{ parseError }}</p>
            <div class="flex flex-wrap items-center gap-4 text-sm">
              <label class="flex items-center gap-2 cursor-pointer">
                <Switch :checked="runPreflightFirst" @update:checked="(v: boolean) => (runPreflightFirst = v)" />
                <span>{{ t('eval.run_preflight_first') }}</span>
              </label>
              <label class="flex items-center gap-2 cursor-pointer">
                <Switch :checked="stopOnFailure" @update:checked="(v: boolean) => (stopOnFailure = v)" />
                <span>{{ t('eval.stop_on_failure') }}</span>
              </label>
            </div>
            <Button
              class="w-full gap-2 bg-indigo-600 hover:bg-indigo-700 text-white"
              :disabled="running"
              @click="runBatch"
            >
              <Loader2 v-if="running" class="w-4 h-4 animate-spin" />
              <Play v-else class="w-4 h-4" />
              {{ running ? t('eval.running') : t('eval.run_batch') }}
            </Button>
            <p v-if="runError" class="text-xs text-red-500">{{ runError }}</p>
            <p class="text-[11px] text-muted-foreground">{{ t('eval.admin_hint') }}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader class="flex flex-row items-center justify-between gap-2">
            <CardTitle class="text-base">{{ t('eval.results_title') }}</CardTitle>
            <Button
              v-if="lastRun"
              variant="outline"
              size="sm"
              class="gap-1"
              @click="downloadResultJson"
            >
              <Download class="w-3.5 h-3.5" />
              {{ t('eval.download_results') }}
            </Button>
          </CardHeader>
          <CardContent>
            <div v-if="!lastRun && !running" class="text-sm text-muted-foreground">
              {{ t('eval.no_results') }}
            </div>
            <div v-else-if="lastRun" class="space-y-4">
              <div class="flex flex-wrap gap-2">
                <Badge variant="secondary">{{ t('eval.total', { n: lastRun.total }) }}</Badge>
                <Badge class="bg-emerald-500/15 text-emerald-700 dark:text-emerald-300">
                  {{ t('eval.passed', { n: lastRun.passed }) }}
                </Badge>
                <Badge
                  v-if="lastRun.failed > 0"
                  class="bg-red-500/15 text-red-700 dark:text-red-300"
                >
                  {{ t('eval.failed', { n: lastRun.failed }) }}
                </Badge>
                <span class="text-xs text-muted-foreground self-center">
                  {{ t('eval.duration', { ms: lastRun.duration_ms }) }}
                </span>
              </div>
              <div class="space-y-2 max-h-[420px] overflow-y-auto">
                <div
                  v-for="row in lastRun.results"
                  :key="String(row.id)"
                  class="rounded-lg border border-border/60 p-3 text-sm"
                >
                  <div class="flex items-center justify-between gap-2">
                    <span class="font-medium font-mono text-xs">{{ row.id }}</span>
                    <CheckCircle2 v-if="row.ok" class="w-4 h-4 text-emerald-500 shrink-0" />
                    <XCircle v-else class="w-4 h-4 text-red-500 shrink-0" />
                  </div>
                  <div class="text-xs text-muted-foreground mt-1">
                    {{ row.target }}
                    <span v-if="row.duration_ms != null"> · {{ row.duration_ms }}ms</span>
                  </div>
                  <p v-if="row.error" class="text-xs text-red-500 mt-1">{{ row.error }}</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Loader2, Package, Workflow, Sparkles, Upload, FileJson, Download } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import {
  getImportCatalog,
  runOneClickImport,
  runOneClickImportFromBody,
  uploadImportBundle,
  validateImportBundle,
  listWorkflows,
  discoverImportExport,
  exportEnvironmentBundle,
  type ImportCatalogItem,
  type ImportRunResponse,
  type ImportKind,
  type ExportDiscoverResponse,
  type WorkflowRecord,
} from '@/services/api'

const props = withDefaults(
  defineProps<{ compact?: boolean }>(),
  { compact: false },
)

const { t } = useI18n()
const router = useRouter()

type PanelMode = 'import' | 'export'
type SourceMode = 'catalog' | 'upload' | 'paste'

const panelMode = ref<PanelMode>('import')
const loading = ref(false)
const importing = ref(false)
const exporting = ref(false)
const catalog = ref<ImportCatalogItem[]>([])
const sourceMode = ref<SourceMode>('catalog')
const kindFilter = ref<'all' | 'platform' | 'workflow'>('all')
const selectedId = ref('')
const publishWorkflows = ref(false)
const waitDocumentIndex = ref(true)
const autoNavigate = ref(false)
const lastResult = ref<ImportRunResponse | null>(null)
const errorMessage = ref<string | null>(null)
const pasteJson = ref('')
const uploadKindOverride = ref<ImportKind | ''>('')
const validateHint = ref<string | null>(null)
const workflowList = ref<WorkflowRecord[]>([])
const exportWorkflowId = ref('')
const exportBundleId = ref('my-export')
const exportName = ref('')
const exportDescription = ref('')
const exportFormat = ref<'zip' | 'json'>('zip')
const exportKind = ref<ImportKind>('platform')
const exportDiscover = ref<ExportDiscoverResponse | null>(null)
const exportWarnings = ref<string[]>([])

const filteredItems = computed(() => {
  if (kindFilter.value === 'all') return catalog.value
  return catalog.value.filter((x) => x.kind === kindFilter.value)
})

const selectedItem = computed(() =>
  catalog.value.find((x) => `${x.kind}:${x.bundle_id}` === selectedId.value),
)

const showPlatformOptions = computed(() => {
  if (sourceMode.value === 'catalog') return selectedItem.value?.kind === 'platform'
  if (uploadKindOverride.value === 'platform') return true
  if (uploadKindOverride.value === 'workflow') return false
  return true
})

function itemKey(item: ImportCatalogItem) {
  return `${item.kind}:${item.bundle_id}`
}

function parsePasteBundle(): Record<string, unknown> {
  const raw = pasteJson.value.trim()
  if (!raw) throw new Error(t('import.paste_empty'))
  const parsed = JSON.parse(raw) as unknown
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error(t('import.paste_invalid'))
  }
  return parsed as Record<string, unknown>
}

async function loadCatalog() {
  loading.value = true
  errorMessage.value = null
  try {
    const res = await getImportCatalog()
    catalog.value = res.items || []
    if (!selectedId.value && catalog.value[0]) {
      selectedId.value = itemKey(catalog.value[0])
    }
  } catch (e) {
    errorMessage.value = (e as Error)?.message || String(e)
  } finally {
    loading.value = false
  }
}

async function validatePaste() {
  validateHint.value = null
  errorMessage.value = null
  try {
    const bundle = parsePasteBundle()
    const res = await validateImportBundle({
      bundle,
      kind: uploadKindOverride.value || undefined,
    })
    if (res.ok) {
      validateHint.value = t('import.validate_ok', {
        kind: res.kind === 'platform' ? t('import.kind_platform') : t('import.kind_workflow'),
        id: res.bundle_id || '—',
      })
    } else {
      errorMessage.value = res.message || t('import.validate_fail')
    }
  } catch (e) {
    errorMessage.value = (e as Error)?.message || String(e)
  }
}

async function runImport() {
  importing.value = true
  errorMessage.value = null
  lastResult.value = null
  validateHint.value = null
  try {
    let res: ImportRunResponse
    if (sourceMode.value === 'catalog') {
      const item = selectedItem.value
      if (!item) return
      res = await runOneClickImport({
        kind: item.kind,
        bundle_id: item.bundle_id,
        publish_workflows: publishWorkflows.value,
        wait_document_index: waitDocumentIndex.value,
      })
    } else if (sourceMode.value === 'paste') {
      const bundle = parsePasteBundle()
      res = await runOneClickImportFromBody({
        bundle,
        kind: uploadKindOverride.value || undefined,
        publish_workflows: publishWorkflows.value,
        wait_document_index: waitDocumentIndex.value,
      })
    } else {
      errorMessage.value = t('import.pick_file_first')
      return
    }
    lastResult.value = res
    if (autoNavigate.value && res.edit_url_hint) {
      await router.push(res.edit_url_hint)
    }
  } catch (e) {
    errorMessage.value = (e as Error)?.message || String(e)
  } finally {
    importing.value = false
  }
}

async function onFileChange(ev: Event) {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  importing.value = true
  errorMessage.value = null
  lastResult.value = null
  try {
    const res = await uploadImportBundle(file, {
      kind: uploadKindOverride.value || undefined,
      publish_workflows: publishWorkflows.value,
      wait_document_index: waitDocumentIndex.value,
    })
    lastResult.value = res
    if (autoNavigate.value && res.edit_url_hint) {
      await router.push(res.edit_url_hint)
    }
  } catch (e) {
    errorMessage.value = (e as Error)?.message || String(e)
  } finally {
    importing.value = false
    input.value = ''
  }
}

function kindLabel(kind: string) {
  return kind === 'platform' ? t('import.kind_platform') : t('import.kind_workflow')
}

function go(href: string | null | undefined) {
  if (href) void router.push(href)
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

async function loadWorkflowsForExport() {
  try {
    const res = await listWorkflows({ limit: 100 })
    workflowList.value = res.items || []
    if (!exportWorkflowId.value && workflowList.value[0]) {
      exportWorkflowId.value = workflowList.value[0].id
      exportName.value = workflowList.value[0].name
    }
  } catch {
    workflowList.value = []
  }
}

async function runDiscoverExport() {
  if (!exportWorkflowId.value) return
  errorMessage.value = null
  exportDiscover.value = null
  try {
    exportDiscover.value = await discoverImportExport({
      workflow_ids: [exportWorkflowId.value],
    })
  } catch (e) {
    errorMessage.value = (e as Error)?.message || String(e)
  }
}

async function runExport() {
  if (!exportWorkflowId.value || !exportBundleId.value.trim()) return
  exporting.value = true
  errorMessage.value = null
  exportWarnings.value = []
  try {
    const res = await exportEnvironmentBundle(
      {
        kind: exportKind.value,
        format: exportFormat.value,
        bundle_id: exportBundleId.value.trim(),
        name: exportName.value.trim() || exportBundleId.value.trim(),
        description: exportDescription.value,
        workflow_ids: [exportWorkflowId.value],
      },
      { download: true },
    )
    if (res.format === 'zip') {
      downloadBlob(res.blob, res.filename)
    } else {
      const blob = new Blob([JSON.stringify(res.data.bundle, null, 2)], {
        type: 'application/json',
      })
      downloadBlob(blob, res.data.filename)
      exportWarnings.value = res.data.warnings || []
    }
  } catch (e) {
    errorMessage.value = (e as Error)?.message || String(e)
  } finally {
    exporting.value = false
  }
}

onMounted(() => {
  void loadCatalog()
  void loadWorkflowsForExport()
})
</script>

<template>
  <div :class="compact ? 'space-y-4' : 'max-w-3xl mx-auto space-y-6 p-6'">
    <div v-if="!compact" class="space-y-1">
      <h1 class="text-2xl font-bold tracking-tight">{{ t('import.title') }}</h1>
      <p class="text-sm text-muted-foreground">{{ t('import.subtitle') }}</p>
    </div>

    <div class="flex flex-wrap gap-2 border-b border-border/60 pb-3">
      <Button
        size="sm"
        :variant="panelMode === 'import' ? 'default' : 'outline'"
        @click="panelMode = 'import'"
      >
        {{ t('import.panel_import') }}
      </Button>
      <Button
        size="sm"
        :variant="panelMode === 'export' ? 'default' : 'outline'"
        class="gap-1"
        @click="panelMode = 'export'"
      >
        <Download class="w-3.5 h-3.5" />
        {{ t('import.panel_export') }}
      </Button>
    </div>

    <template v-if="panelMode === 'export'">
      <p class="text-xs text-muted-foreground">{{ t('import.export_hint') }}</p>
      <div class="space-y-2">
        <label class="text-sm font-medium">{{ t('import.export_workflow') }}</label>
        <select
          v-model="exportWorkflowId"
          class="w-full h-10 rounded-md border border-input bg-background px-3 text-sm"
          @change="exportName = workflowList.find(w => w.id === exportWorkflowId)?.name || exportName"
        >
          <option v-for="wf in workflowList" :key="wf.id" :value="wf.id">
            {{ wf.name }} ({{ wf.id.slice(0, 8) }}…)
          </option>
        </select>
      </div>
      <div class="grid gap-3 sm:grid-cols-2">
        <div class="space-y-1">
          <label class="text-sm font-medium">{{ t('import.export_bundle_id') }}</label>
          <input
            v-model="exportBundleId"
            class="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
          />
        </div>
        <div class="space-y-1">
          <label class="text-sm font-medium">{{ t('import.export_format') }}</label>
          <select v-model="exportFormat" class="w-full h-9 rounded-md border border-input bg-background px-3 text-sm">
            <option value="zip">{{ t('import.export_format_zip') }}</option>
            <option value="json">{{ t('import.export_format_json') }}</option>
          </select>
        </div>
      </div>
      <div class="space-y-1">
        <label class="text-sm font-medium">{{ t('import.export_name') }}</label>
        <input v-model="exportName" class="w-full h-9 rounded-md border border-input bg-background px-3 text-sm" />
      </div>
      <div class="space-y-1">
        <label class="text-sm font-medium">{{ t('import.export_description') }}</label>
        <input
          v-model="exportDescription"
          class="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
        />
      </div>
      <div class="flex flex-wrap gap-2">
        <Button size="sm" variant="outline" @click="runDiscoverExport">
          {{ t('import.export_discover') }}
        </Button>
        <Button
          size="sm"
          class="gap-1 bg-emerald-600 hover:bg-emerald-700 text-white"
          :disabled="exporting || !exportWorkflowId"
          @click="runExport"
        >
          <Loader2 v-if="exporting" class="w-3.5 h-3.5 animate-spin" />
          <Download v-else class="w-3.5 h-3.5" />
          {{ t('import.export_run') }}
        </Button>
      </div>
      <div
        v-if="exportDiscover"
        class="rounded-lg border border-border/60 bg-muted/20 p-3 text-xs space-y-1"
      >
        <p class="font-medium">{{ t('import.export_discovered') }}</p>
        <p>{{ t('import.export_counts', {
          agents: exportDiscover.agent_ids.length,
          kb: exportDiscover.knowledge_base_ids.length,
          skills: exportDiscover.skill_ids.length,
          mcp: exportDiscover.mcp_server_ids.length,
        }) }}</p>
      </div>
      <div
        v-if="exportWarnings.length"
        class="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-xs space-y-1"
      >
        <p v-for="(w, i) in exportWarnings" :key="i" class="text-muted-foreground">{{ w }}</p>
      </div>
    </template>

    <template v-else>
    <div class="flex flex-wrap gap-2">
      <Button
        size="sm"
        :variant="sourceMode === 'catalog' ? 'default' : 'outline'"
        @click="sourceMode = 'catalog'"
      >
        {{ t('import.tab_catalog') }}
      </Button>
      <Button
        size="sm"
        :variant="sourceMode === 'upload' ? 'default' : 'outline'"
        class="gap-1"
        @click="sourceMode = 'upload'"
      >
        <Upload class="w-3.5 h-3.5" />
        {{ t('import.tab_upload') }}
      </Button>
      <Button
        size="sm"
        :variant="sourceMode === 'paste' ? 'default' : 'outline'"
        class="gap-1"
        @click="sourceMode = 'paste'"
      >
        <FileJson class="w-3.5 h-3.5" />
        {{ t('import.tab_paste') }}
      </Button>
    </div>

    <template v-if="sourceMode === 'catalog'">
      <div class="flex flex-wrap gap-2">
        <Button
          size="sm"
          :variant="kindFilter === 'all' ? 'default' : 'outline'"
          @click="kindFilter = 'all'"
        >
          {{ t('import.filter_all') }}
        </Button>
        <Button
          size="sm"
          :variant="kindFilter === 'platform' ? 'default' : 'outline'"
          class="gap-1"
          @click="kindFilter = 'platform'"
        >
          <Package class="w-3.5 h-3.5" />
          {{ t('import.kind_platform') }}
        </Button>
        <Button
          size="sm"
          :variant="kindFilter === 'workflow' ? 'default' : 'outline'"
          class="gap-1"
          @click="kindFilter = 'workflow'"
        >
          <Workflow class="w-3.5 h-3.5" />
          {{ t('import.kind_workflow') }}
        </Button>
      </div>

      <div v-if="loading" class="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 class="w-4 h-4 animate-spin" />
        {{ t('import.loading') }}
      </div>

      <div v-else class="space-y-2">
        <label class="text-sm font-medium">{{ t('import.select_bundle') }}</label>
        <select
          v-model="selectedId"
          class="w-full h-10 rounded-md border border-input bg-background px-3 text-sm"
        >
          <option v-for="item in filteredItems" :key="itemKey(item)" :value="itemKey(item)">
            [{{ kindLabel(item.kind) }}] {{ item.name }}
          </option>
        </select>
        <p v-if="selectedItem" class="text-xs text-muted-foreground leading-relaxed">
          {{ selectedItem.description }}
          <template v-if="selectedItem.recommended_platform_bundle_id && selectedItem.kind === 'workflow'">
            · {{ t('import.platform_hint', { id: selectedItem.recommended_platform_bundle_id }) }}
          </template>
        </p>
      </div>
    </template>

    <template v-else-if="sourceMode === 'upload'">
      <p class="text-xs text-muted-foreground">{{ t('import.upload_hint') }}</p>
      <label
        class="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border/80 p-8 cursor-pointer hover:bg-muted/40 transition-colors"
      >
        <Upload class="w-8 h-8 text-muted-foreground" />
        <span class="text-sm font-medium">{{ t('import.upload_choose') }}</span>
        <span class="text-xs text-muted-foreground">.json · .zip</span>
        <input
          type="file"
          accept=".json,.zip,application/json,application/zip"
          class="hidden"
          :disabled="importing"
          @change="onFileChange"
        />
      </label>
    </template>

    <template v-else>
      <label class="text-sm font-medium">{{ t('import.paste_label') }}</label>
      <textarea
        v-model="pasteJson"
        rows="10"
        class="w-full rounded-md border border-input bg-background px-3 py-2 text-xs font-mono"
        :placeholder="t('import.paste_placeholder')"
      />
      <Button size="sm" variant="outline" :disabled="importing" @click="validatePaste">
        {{ t('import.validate') }}
      </Button>
      <p v-if="validateHint" class="text-xs text-emerald-600 dark:text-emerald-400">{{ validateHint }}</p>
    </template>

    <div
      v-if="sourceMode !== 'catalog' || showPlatformOptions"
      class="space-y-2"
    >
      <label v-if="sourceMode !== 'catalog'" class="text-sm font-medium block">
        {{ t('import.kind_override') }}
      </label>
      <select
        v-if="sourceMode !== 'catalog'"
        v-model="uploadKindOverride"
        class="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
      >
        <option value="">{{ t('import.kind_auto') }}</option>
        <option value="platform">{{ t('import.kind_platform') }}</option>
        <option value="workflow">{{ t('import.kind_workflow') }}</option>
      </select>

      <div
        v-if="showPlatformOptions"
        class="rounded-lg border border-border/60 bg-muted/30 p-4 space-y-3 text-sm"
      >
        <div class="flex items-center gap-2 font-medium">
          <Sparkles class="w-4 h-4 text-emerald-600" />
          {{ t('import.platform_includes') }}
        </div>
        <p class="text-xs text-muted-foreground">{{ t('import.platform_includes_detail') }}</p>
        <label class="flex items-center gap-2">
          <input v-model="waitDocumentIndex" type="checkbox" class="rounded" />
          {{ t('import.wait_kb_index') }}
        </label>
      </div>
    </div>

    <label class="flex items-center gap-2 text-sm">
      <input v-model="publishWorkflows" type="checkbox" class="rounded" />
      {{ t('import.publish_after') }}
    </label>
    <label class="flex items-center gap-2 text-sm">
      <input v-model="autoNavigate" type="checkbox" class="rounded" />
      {{ t('import.auto_navigate') }}
    </label>

    <Button
      v-if="sourceMode !== 'upload'"
      class="gap-2 bg-indigo-600 hover:bg-indigo-700 text-white"
      :disabled="importing || (sourceMode === 'catalog' && !selectedItem)"
      @click="runImport"
    >
      <Loader2 v-if="importing" class="w-4 h-4 animate-spin" />
      {{ t('import.run') }}
    </Button>

    <p v-if="importing && sourceMode === 'upload'" class="flex items-center gap-2 text-sm text-muted-foreground">
      <Loader2 class="w-4 h-4 animate-spin" />
      {{ t('import.uploading') }}
    </p>

    <p v-if="errorMessage" class="text-sm text-red-500">{{ errorMessage }}</p>

    <div
      v-if="lastResult?.warnings?.length"
      class="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-xs space-y-1"
    >
      <p class="font-medium text-amber-800 dark:text-amber-300">{{ t('import.warnings') }}</p>
      <p v-for="(w, i) in lastResult.warnings" :key="i" class="text-muted-foreground">{{ w }}</p>
    </div>

    <div
      v-if="lastResult"
      class="rounded-lg border border-border/60 bg-muted/20 p-4 space-y-3 text-sm"
    >
      <p class="font-medium">{{ t('import.result_title') }}</p>
      <p class="text-xs text-muted-foreground">
        {{ kindLabel(lastResult.kind) }} · {{ lastResult.bundle_id }}
      </p>
      <div class="flex flex-wrap gap-2">
        <Button v-if="lastResult.edit_url_hint" size="sm" variant="outline" @click="go(lastResult.edit_url_hint)">
          {{ t('import.open_edit') }}
        </Button>
        <Button v-if="lastResult.run_url_hint" size="sm" variant="outline" @click="go(lastResult.run_url_hint)">
          {{ t('import.open_run') }}
        </Button>
      </div>
      <div v-if="lastResult.knowledge_url_hints && Object.keys(lastResult.knowledge_url_hints).length" class="space-y-1">
        <p class="text-xs font-medium text-muted-foreground">{{ t('import.links_kb') }}</p>
        <div class="flex flex-wrap gap-2">
          <Button
            v-for="(href, key) in lastResult.knowledge_url_hints"
            :key="key"
            size="sm"
            variant="ghost"
            class="h-7 text-xs"
            @click="go(href)"
          >
            {{ key }}
          </Button>
        </div>
      </div>
      <div v-if="lastResult.agents_url_hints && Object.keys(lastResult.agents_url_hints).length" class="space-y-1">
        <p class="text-xs font-medium text-muted-foreground">{{ t('import.links_agents') }}</p>
        <div class="flex flex-wrap gap-2">
          <Button
            v-for="(href, key) in lastResult.agents_url_hints"
            :key="key"
            size="sm"
            variant="ghost"
            class="h-7 text-xs"
            @click="go(href)"
          >
            {{ key }}
          </Button>
        </div>
      </div>
    </div>
    </template>
  </div>
</template>

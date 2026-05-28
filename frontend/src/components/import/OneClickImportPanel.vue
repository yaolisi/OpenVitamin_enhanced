<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Loader2,
  Package,
  Sparkles,
  Upload,
  FileJson,
  Download,
  CheckCircle2,
  AlertCircle,
  Copy,
  LayoutTemplate,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { useBundleImportHub } from '@/composables/useBundleImportHub'

const props = withDefaults(
  defineProps<{
    compact?: boolean
    initialPanelMode?: 'import' | 'export'
    initialWorkflowId?: string
  }>(),
  { compact: false },
)

const { t } = useI18n()
const {
  panelMode,
  loading,
  importing,
  exporting,
  filteredCatalog,
  envPreflight,
  sourceMode,
  kindFilter,
  selectedCatalogKey,
  selectedCatalogItem,
  showPlatformOptions,
  publishWorkflows,
  waitDocumentIndex,
  autoNavigate,
  conflictStrategy,
  runPublishGate,
  useAsyncJob,
  lastResult,
  preview,
  errorMessage,
  pasteJson,
  uploadKindOverride,
  validateHint,
  workflowList,
  exportWorkflowId,
  exportBundleId,
  exportName,
  exportFormat,
  exportItems,
  importJobSteps,
  recentBundles,
  curlCopied,
  catalogKey,
  runImport,
  onUploadFile,
  runDiscoverExport,
  runExport,
  runPreviewForPaste,
  parsePaste,
  validateImportBundle,
  goCanvasDemo,
  goPlatformCatalog,
  goUploadPath,
  copyCurl,
  navigateTo,
  resultResourceLinks,
  previewStepHref,
} = useBundleImportHub({
  initialPanelMode: props.initialPanelMode,
  initialWorkflowId: props.initialWorkflowId,
})

const nextStepLabels: Record<string, string> = {
  open_workflow_editor: 'import.step_edit',
  check_kb_indexing: 'import.step_kb',
  enable_mcp_template: 'import.step_mcp',
  run_with_sample_input: 'import.step_run',
  run_eval_suite: 'import.step_eval',
  open_agent_editor: 'import.step_agent',
  optional_publish: 'import.step_publish',
}

function kindLabel(kind: string) {
  return kind === 'platform' ? t('import.kind_platform') : t('import.kind_workflow')
}

function onFileInput(ev: Event) {
  const f = (ev.target as HTMLInputElement).files?.[0]
  if (f) void onUploadFile(f)
  ;(ev.target as HTMLInputElement).value = ''
}

function onDrop(ev: DragEvent) {
  ev.preventDefault()
  const f = ev.dataTransfer?.files?.[0]
  if (f) void onUploadFile(f)
}

async function validatePaste() {
  validateHint.value = null
  errorMessage.value = null
  try {
    const bundle = parsePaste()
    const res = await validateImportBundle({ bundle, kind: uploadKindOverride.value || undefined })
    if (res.ok) {
      validateHint.value = t('import.validate_ok', {
        kind: res.kind === 'platform' ? t('import.kind_platform') : t('import.kind_workflow'),
        id: res.bundle_id || '—',
      })
      await runPreviewForPaste()
    } else {
      errorMessage.value = res.message || t('import.validate_fail')
    }
  } catch (e) {
    errorMessage.value = (e as Error).message
  }
}

const showMcpWizard = computed(
  () => lastResult.value?.mcp_url_hints && Object.keys(lastResult.value.mcp_url_hints).length > 0,
)
</script>

<template>
  <div :class="compact ? 'space-y-4' : 'max-w-4xl mx-auto space-y-6 p-6'">
    <div v-if="!compact" class="space-y-1">
      <h1 class="text-2xl font-bold tracking-tight">{{ t('import.title') }}</h1>
      <p class="text-sm text-muted-foreground">{{ t('import.subtitle') }}</p>
      <p v-if="envPreflight?.tenant_id" class="text-xs text-muted-foreground">
        {{ t('import.tenant_hint', { tenant: envPreflight.tenant_id }) }}
      </p>
    </div>

    <!-- Path wizard -->
    <div class="grid gap-3 sm:grid-cols-3">
      <button
        type="button"
        class="rounded-lg border border-border/60 p-4 text-left hover:bg-muted/40 transition-colors"
        @click="goCanvasDemo()"
      >
        <LayoutTemplate class="w-5 h-5 text-violet-600 mb-2" />
        <p class="font-medium text-sm">{{ t('import.wizard_canvas_title') }}</p>
        <p class="text-xs text-muted-foreground mt-1">{{ t('import.wizard_canvas_desc') }}</p>
      </button>
      <button
        type="button"
        class="rounded-lg border border-border/60 p-4 text-left hover:bg-muted/40 transition-colors"
        @click="goPlatformCatalog()"
      >
        <Package class="w-5 h-5 text-emerald-600 mb-2" />
        <p class="font-medium text-sm">{{ t('import.wizard_platform_title') }}</p>
        <p class="text-xs text-muted-foreground mt-1">{{ t('import.wizard_platform_desc') }}</p>
      </button>
      <button
        type="button"
        class="rounded-lg border border-border/60 p-4 text-left hover:bg-muted/40 transition-colors"
        @click="goUploadPath()"
      >
        <Upload class="w-5 h-5 text-blue-600 mb-2" />
        <p class="font-medium text-sm">{{ t('import.wizard_upload_title') }}</p>
        <p class="text-xs text-muted-foreground mt-1">{{ t('import.wizard_upload_desc') }}</p>
      </button>
    </div>

    <!-- Environment preflight -->
    <div
      v-if="envPreflight"
      class="rounded-lg border p-3 space-y-2"
      :class="envPreflight.ready ? 'border-emerald-500/40 bg-emerald-500/5' : 'border-amber-500/40 bg-amber-500/5'"
    >
      <p class="text-sm font-medium flex items-center gap-2">
        <CheckCircle2 v-if="envPreflight.ready" class="w-4 h-4 text-emerald-600" />
        <AlertCircle v-else class="w-4 h-4 text-amber-600" />
        {{ envPreflight.ready ? t('import.preflight_ready') : t('import.preflight_not_ready') }}
      </p>
      <ul class="text-xs space-y-1">
        <li v-for="c in envPreflight.checks" :key="c.id" class="flex items-center justify-between gap-2">
          <span :class="c.ok ? 'text-muted-foreground' : 'text-amber-700 dark:text-amber-400'">{{ c.message }}</span>
          <Button
            v-if="c.action_url && !c.ok"
            type="button"
            size="sm"
            variant="ghost"
            class="h-6 text-xs"
            @click="navigateTo(c.action_url)"
          >
            {{ t('import.preflight_fix') }}
          </Button>
        </li>
      </ul>
    </div>

    <div class="flex flex-wrap gap-2 border-b border-border/60 pb-3">
      <Button size="sm" :variant="panelMode === 'import' ? 'default' : 'outline'" @click="panelMode = 'import'">
        {{ t('import.panel_import') }}
      </Button>
      <Button size="sm" :variant="panelMode === 'export' ? 'default' : 'outline'" class="gap-1" @click="panelMode = 'export'">
        <Download class="w-3.5 h-3.5" />
        {{ t('import.panel_export') }}
      </Button>
    </div>

    <!-- EXPORT -->
    <template v-if="panelMode === 'export'">
      <p class="text-xs text-muted-foreground">{{ t('import.export_hint') }}</p>
      <select v-model="exportWorkflowId" class="w-full h-10 rounded-md border border-input bg-background px-3 text-sm" @change="runDiscoverExport()">
        <option v-for="wf in workflowList" :key="wf.id" :value="wf.id">{{ wf.name }}</option>
      </select>
      <div class="grid gap-3 sm:grid-cols-2">
        <input v-model="exportBundleId" class="h-9 rounded-md border px-3 text-sm" :placeholder="t('import.export_bundle_id')" />
        <select v-model="exportFormat" class="h-9 rounded-md border px-3 text-sm">
          <option value="zip">{{ t('import.export_format_zip') }}</option>
          <option value="json">{{ t('import.export_format_json') }}</option>
        </select>
      </div>
      <input v-model="exportName" class="w-full h-9 rounded-md border px-3 text-sm" :placeholder="t('import.export_name')" />
      <div v-if="exportItems.length" class="rounded-lg border p-3 max-h-48 overflow-auto space-y-1 text-xs">
        <label v-for="item in exportItems" :key="`${item.kind}-${item.id}`" class="flex items-center gap-2">
          <input v-model="item.selected" type="checkbox" class="rounded" />
          <span class="text-muted-foreground">[{{ item.kind }}]</span>
          <span>{{ item.label }}</span>
        </label>
      </div>
      <Button class="gap-2" :disabled="exporting" @click="runExport()">
        <Loader2 v-if="exporting" class="w-4 h-4 animate-spin" />
        <Download v-else class="w-4 h-4" />
        {{ t('import.export_run') }}
      </Button>
    </template>

    <!-- IMPORT -->
    <template v-else>
      <div class="flex flex-wrap gap-2">
        <Button size="sm" :variant="sourceMode === 'catalog' ? 'default' : 'outline'" @click="sourceMode = 'catalog'">{{ t('import.tab_catalog') }}</Button>
        <Button size="sm" :variant="sourceMode === 'upload' ? 'default' : 'outline'" class="gap-1" @click="sourceMode = 'upload'">
          <Upload class="w-3.5 h-3.5" />{{ t('import.tab_upload') }}
        </Button>
        <Button size="sm" :variant="sourceMode === 'paste' ? 'default' : 'outline'" class="gap-1" @click="sourceMode = 'paste'">
          <FileJson class="w-3.5 h-3.5" />{{ t('import.tab_paste') }}
        </Button>
      </div>

      <div v-if="recentBundles.length" class="text-xs text-muted-foreground">
        {{ t('import.recent') }}: {{ recentBundles.join(', ') }}
      </div>

      <template v-if="sourceMode === 'catalog'">
        <div class="flex flex-wrap gap-2">
          <Button size="sm" :variant="kindFilter === 'all' ? 'default' : 'outline'" @click="kindFilter = 'all'">{{ t('import.filter_all') }}</Button>
          <Button size="sm" :variant="kindFilter === 'platform' ? 'default' : 'outline'" @click="kindFilter = 'platform'">{{ t('import.kind_platform') }}</Button>
          <Button size="sm" :variant="kindFilter === 'workflow' ? 'default' : 'outline'" @click="kindFilter = 'workflow'">{{ t('import.kind_workflow') }}</Button>
        </div>
        <div v-if="loading" class="flex gap-2 text-sm text-muted-foreground"><Loader2 class="w-4 h-4 animate-spin" />{{ t('import.loading') }}</div>
        <div v-else class="grid gap-3 sm:grid-cols-2">
          <button
            v-for="item in filteredCatalog"
            :key="catalogKey(item)"
            type="button"
            class="rounded-lg border p-4 text-left transition-colors"
            :class="selectedCatalogKey === catalogKey(item) ? 'border-indigo-500 bg-indigo-500/5' : 'border-border/60 hover:bg-muted/30'"
            @click="selectedCatalogKey = catalogKey(item)"
          >
            <p class="text-xs text-muted-foreground mb-1">[{{ kindLabel(item.kind) }}]</p>
            <p class="font-medium text-sm">{{ item.name }}</p>
            <p class="text-xs text-muted-foreground line-clamp-2 mt-1">{{ item.description }}</p>
            <div v-if="item.tags?.length" class="flex flex-wrap gap-1 mt-2">
              <span v-for="tag in item.tags" :key="tag" class="text-[10px] px-1.5 py-0.5 rounded bg-muted">{{ tag }}</span>
            </div>
            <p v-if="item.estimated_minutes" class="text-[10px] text-muted-foreground mt-1">
              ~{{ item.estimated_minutes }} {{ t('import.minutes') }}
            </p>
            <button
              v-if="item.playbook_url"
              type="button"
              class="text-[10px] text-indigo-600 hover:underline mt-2"
              @click.stop="navigateTo(item.playbook_url!)"
            >
              {{ t('import.open_playbook') }}
            </button>
          </button>
        </div>
      </template>

      <template v-else-if="sourceMode === 'upload'">
        <div
          class="rounded-lg border border-dashed p-10 text-center cursor-pointer hover:bg-muted/30"
          @dragover.prevent
          @drop="onDrop"
        >
          <Upload class="w-8 h-8 mx-auto text-muted-foreground mb-2" />
          <p class="text-sm">{{ t('import.upload_choose') }}</p>
          <input type="file" accept=".json,.zip" class="hidden" id="bundle-upload-input" @change="onFileInput" />
          <label for="bundle-upload-input" class="text-xs text-indigo-600 cursor-pointer underline mt-2 inline-block">{{ t('import.upload_pick') }}</label>
        </div>
      </template>

      <template v-else>
        <textarea v-model="pasteJson" rows="8" class="w-full rounded-md border px-3 py-2 text-xs font-mono" />
        <div class="flex gap-2">
          <Button size="sm" variant="outline" @click="validatePaste">{{ t('import.validate') }}</Button>
          <Button size="sm" variant="outline" @click="runPreviewForPaste">{{ t('import.preview') }}</Button>
        </div>
      </template>

      <div v-if="preview" class="rounded-lg border bg-muted/20 p-3 text-xs space-y-2">
        <p class="font-medium">{{ t('import.preview_title') }}</p>
        <p>{{ t('import.preview_counts', preview.summary) }}</p>
        <p v-if="preview.conflicts.length" class="text-amber-600">{{ t('import.conflicts', { n: preview.conflicts.length }) }}</p>
        <p v-if="preview.estimated_index_seconds">{{ t('import.index_eta', { sec: preview.estimated_index_seconds }) }}</p>
        <div v-if="preview.next_steps_preview?.length" class="space-y-1 pt-1 border-t border-border/40">
          <p class="font-medium text-muted-foreground">{{ t('import.next_steps_preview') }}</p>
          <button
            v-for="step in preview.next_steps_preview"
            :key="step.id"
            type="button"
            class="block w-full text-left text-xs rounded px-2 py-1 hover:bg-muted/60"
            :class="previewStepHref(step) ? 'text-indigo-600 cursor-pointer' : 'text-muted-foreground cursor-default'"
            :disabled="!previewStepHref(step)"
            @click="navigateTo(previewStepHref(step))"
          >
            {{ t(nextStepLabels[step.label] || step.label) }}
          </button>
        </div>
        <Button v-if="preview.curl_hint" type="button" size="sm" variant="ghost" class="gap-1 h-7" @click="copyCurl()">
          <Copy class="w-3 h-3" />{{ curlCopied ? t('import.copied') : t('import.copy_curl') }}
        </Button>
      </div>

      <div v-if="showPlatformOptions" class="rounded-lg border bg-muted/30 p-4 space-y-2 text-sm">
        <div class="flex items-center gap-2 font-medium"><Sparkles class="w-4 h-4 text-emerald-600" />{{ t('import.platform_includes') }}</div>
        <label class="flex gap-2"><input v-model="waitDocumentIndex" type="checkbox" class="rounded" />{{ t('import.wait_kb_index') }}</label>
        <label class="flex gap-2"><input v-model="useAsyncJob" type="checkbox" class="rounded" />{{ t('import.async_job') }}</label>
      </div>

      <label class="flex gap-2 text-sm"><input v-model="publishWorkflows" type="checkbox" class="rounded" />{{ t('import.publish_after') }}</label>
      <label class="flex gap-2 text-sm"><input v-model="runPublishGate" type="checkbox" class="rounded" />{{ t('import.run_publish_gate') }}</label>
      <label class="flex gap-2 text-sm"><input v-model="autoNavigate" type="checkbox" class="rounded" />{{ t('import.auto_navigate') }}</label>
      <div class="flex gap-2 items-center text-sm">
        <span>{{ t('import.conflict_strategy') }}</span>
        <select v-model="conflictStrategy" class="h-8 rounded border px-2 text-sm">
          <option value="skip">{{ t('import.conflict_skip') }}</option>
          <option value="duplicate">{{ t('import.conflict_duplicate') }}</option>
        </select>
      </div>

      <Button
        class="gap-2 bg-indigo-600 hover:bg-indigo-700 text-white"
        :disabled="importing || (sourceMode === 'catalog' && !selectedCatalogItem)"
        @click="runImport()"
      >
        <Loader2 v-if="importing" class="w-4 h-4 animate-spin" />
        {{ t('import.run') }}
      </Button>

      <div v-if="importJobSteps.length" class="rounded-lg border p-3 text-xs space-y-1">
        <p class="font-medium">{{ t('import.job_progress') }}</p>
        <div v-for="s in importJobSteps" :key="s.id" class="flex justify-between">
          <span>{{ s.label }}</span>
          <span class="text-muted-foreground">{{ s.status }}</span>
        </div>
      </div>
    </template>

    <p v-if="errorMessage" class="text-sm text-red-500">{{ errorMessage }}</p>
    <p v-if="validateHint" class="text-xs text-emerald-600">{{ validateHint }}</p>

    <div v-if="lastResult?.warnings?.length" class="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-xs space-y-1">
      <p class="font-medium">{{ t('import.warnings') }}</p>
      <p v-for="(w, i) in lastResult.warnings" :key="i">{{ w }}</p>
    </div>

    <div v-if="lastResult" class="rounded-lg border p-4 space-y-3 text-sm">
      <p class="font-medium">{{ t('import.result_title') }}</p>
      <div class="flex flex-wrap gap-2">
        <Button
          v-if="lastResult.edit_url_hint"
          type="button"
          size="sm"
          variant="outline"
          @click="navigateTo(lastResult.edit_url_hint)"
        >
          {{ t('import.open_edit') }}
        </Button>
        <Button
          v-if="lastResult.run_url_hint"
          type="button"
          size="sm"
          variant="outline"
          @click="navigateTo(lastResult.run_url_hint)"
        >
          {{ t('import.open_run') }}
        </Button>
      </div>
      <div v-if="resultResourceLinks.length" class="space-y-1">
        <p class="text-xs font-medium text-muted-foreground">{{ t('import.resource_links') }}</p>
        <button
          v-for="link in resultResourceLinks"
          :key="link.key"
          type="button"
          class="block w-full text-left text-xs text-indigo-600 hover:underline px-1 py-0.5"
          @click="navigateTo(link.href)"
        >
          {{ link.label }}
        </button>
      </div>
      <div v-if="lastResult.next_steps?.length" class="space-y-1">
        <p class="text-xs font-medium text-muted-foreground">{{ t('import.next_steps') }}</p>
        <button
          v-for="step in lastResult.next_steps"
          :key="step.id"
          type="button"
          class="block w-full text-left text-xs rounded px-2 py-1.5 hover:bg-muted/60"
          :class="step.href ? 'text-indigo-600' : 'text-muted-foreground cursor-default'"
          :disabled="!step.href"
          @click="navigateTo(step.href)"
        >
          {{ t(nextStepLabels[step.label] || step.label) }}
        </button>
      </div>
      <div v-if="showMcpWizard" class="rounded border border-violet-500/30 bg-violet-500/5 p-3 text-xs">
        <p class="font-medium mb-1">{{ t('import.mcp_wizard_title') }}</p>
        <p class="text-muted-foreground mb-2">{{ t('import.mcp_wizard_desc') }}</p>
        <Button type="button" size="sm" @click="navigateTo('/settings/mcp')">{{ t('import.step_mcp') }}</Button>
      </div>
      <Button v-if="lastResult.curl_hint" size="sm" variant="outline" class="gap-1" @click="copyCurl()">
        <Copy class="w-3.5 h-3.5" />{{ t('import.copy_curl') }}
      </Button>
    </div>
  </div>
</template>

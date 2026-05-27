import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  diffImportBundle,
  discoverImportExport,
  exportEnvironmentBundle,
  getImportCatalog,
  getImportJobStatus,
  getImportPreflight,
  previewImportBundle,
  runOneClickImport,
  runOneClickImportFromBody,
  uploadImportBundle,
  validateImportBundle,
  listWorkflows,
  type ExportDiscoverItem,
  type ImportCatalogItem,
  type ImportKind,
  type ImportPreviewResponse,
  type ImportPreflightCheck,
  type ImportRunResponse,
  type WorkflowRecord,
} from '@/services/api'

const RECENT_BUNDLES_KEY = 'perilla_recent_import_bundles'

export type PanelMode = 'import' | 'export'
export type SourceMode = 'catalog' | 'upload' | 'paste'
export type WizardPath = 'canvas' | 'platform' | 'upload' | null

export function useBundleImportHub(options?: {
  initialPanelMode?: PanelMode
  initialWorkflowId?: string
}) {
  const router = useRouter()
  const panelMode = ref<PanelMode>(options?.initialPanelMode ?? 'import')
  const wizardPath = ref<WizardPath>(null)
  const loading = ref(false)
  const importing = ref(false)
  const exporting = ref(false)
  const catalog = ref<ImportCatalogItem[]>([])
  const envPreflight = ref<{ ready: boolean; tenant_id: string; checks: ImportPreflightCheck[] } | null>(null)
  const sourceMode = ref<SourceMode>('catalog')
  const kindFilter = ref<'all' | ImportKind>('all')
  const selectedCatalogKey = ref('')
  const publishWorkflows = ref(false)
  const waitDocumentIndex = ref(true)
  const autoNavigate = ref(false)
  const conflictStrategy = ref<'skip' | 'duplicate'>('skip')
  const runPublishGate = ref(true)
  const useAsyncJob = ref(true)
  const lastResult = ref<ImportRunResponse | null>(null)
  const preview = ref<ImportPreviewResponse | null>(null)
  const diffResult = ref<{ will_create: Record<string, number>; conflicts: unknown[] } | null>(null)
  const errorMessage = ref<string | null>(null)
  const pasteJson = ref('')
  const uploadKindOverride = ref<ImportKind | ''>('')
  const validateHint = ref<string | null>(null)
  const workflowList = ref<WorkflowRecord[]>([])
  const exportWorkflowId = ref(options?.initialWorkflowId ?? '')
  const exportBundleId = ref('my-export')
  const exportName = ref('')
  const exportDescription = ref('')
  const exportFormat = ref<'zip' | 'json'>('zip')
  const exportKind = ref<ImportKind>('platform')
  const exportItems = ref<ExportDiscoverItem[]>([])
  const importJobId = ref<string | null>(null)
  const importJobSteps = ref<Array<{ id: string; label: string; status: string; detail?: string }>>([])
  const recentBundles = ref<string[]>([])
  const curlCopied = ref(false)
  let jobPollTimer: ReturnType<typeof setInterval> | null = null

  const filteredCatalog = computed(() => {
    if (kindFilter.value === 'all') return catalog.value
    return catalog.value.filter((x) => x.kind === kindFilter.value)
  })

  const selectedCatalogItem = computed(() =>
    catalog.value.find((x) => `${x.kind}:${x.bundle_id}` === selectedCatalogKey.value),
  )

  const showPlatformOptions = computed(() => {
    if (sourceMode.value === 'catalog') return selectedCatalogItem.value?.kind === 'platform'
    if (uploadKindOverride.value === 'platform') return true
    if (uploadKindOverride.value === 'workflow') return false
    return true
  })

  function catalogKey(item: ImportCatalogItem) {
    return `${item.kind}:${item.bundle_id}`
  }

  function loadRecent() {
    try {
      const raw = localStorage.getItem(RECENT_BUNDLES_KEY)
      recentBundles.value = raw ? (JSON.parse(raw) as string[]) : []
    } catch {
      recentBundles.value = []
    }
  }

  function pushRecent(bundleId: string) {
    const next = [bundleId, ...recentBundles.value.filter((x) => x !== bundleId)].slice(0, 8)
    recentBundles.value = next
    localStorage.setItem(RECENT_BUNDLES_KEY, JSON.stringify(next))
  }

  async function refreshPreflight() {
    try {
      if (sourceMode.value === 'catalog' && selectedCatalogItem.value) {
        const p = await previewImportBundle({
          bundle_id: selectedCatalogItem.value.bundle_id,
          catalog_kind: selectedCatalogItem.value.kind,
        })
        preview.value = p
        const env = p.environment as { ready: boolean; tenant_id?: string; checks: ImportPreflightCheck[] }
        envPreflight.value = {
          ready: env.ready,
          tenant_id: env.tenant_id ?? envPreflight.value?.tenant_id ?? 'default',
          checks: env.checks ?? [],
        }
        return
      }
      const base = await getImportPreflight()
      envPreflight.value = base
      if (sourceMode.value !== 'catalog') {
        preview.value = null
      }
    } catch (e) {
      errorMessage.value = (e as Error).message
    }
  }

  function navigateTo(target: string | null | undefined) {
    const path = (target || '').trim()
    if (!path) return
    if (/^https?:\/\//i.test(path)) {
      window.open(path, '_blank', 'noopener,noreferrer')
      return
    }
    if (path.endsWith('.md')) {
      window.open(path, '_blank', 'noopener,noreferrer')
      return
    }
    void router.push(path)
  }

  const resultResourceLinks = computed(() => {
    const r = lastResult.value
    if (!r) return [] as Array<{ key: string; label: string; href: string }>
    const rows: Array<{ key: string; label: string; href: string }> = []
    for (const [key, href] of Object.entries(r.knowledge_url_hints || {})) {
      rows.push({ key: `kb-${key}`, label: key, href })
    }
    for (const [key, href] of Object.entries(r.agents_url_hints || {})) {
      rows.push({ key: `agent-${key}`, label: key, href })
    }
    for (const [key, href] of Object.entries(r.skills_url_hints || {})) {
      rows.push({ key: `skill-${key}`, label: key, href })
    }
    return rows
  })

  function previewStepHref(step: { href?: string; href_hint?: string }): string {
    return (step.href || '').trim()
  }

  async function loadCatalog() {
    loading.value = true
    errorMessage.value = null
    try {
      const res = await getImportCatalog()
      catalog.value = res.items || []
      if (!selectedCatalogKey.value && catalog.value[0]) {
        selectedCatalogKey.value = catalogKey(catalog.value[0])
      }
      await refreshPreflight()
    } catch (e) {
      errorMessage.value = (e as Error).message
    } finally {
      loading.value = false
    }
  }

  watch(selectedCatalogKey, () => {
    void refreshPreflight()
  })

  async function loadWorkflows() {
    try {
      const res = await listWorkflows({ limit: 100 })
      workflowList.value = res.items || []
      if (!exportWorkflowId.value && workflowList.value[0]) {
        exportWorkflowId.value = workflowList.value[0].id
        exportName.value = workflowList.value[0].name
        const slug = workflowList.value[0].name
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, '-')
          .replace(/^-|-$/g, '')
        exportBundleId.value = slug || `export-${workflowList.value[0].id.slice(0, 8)}`
      }
    } catch {
      workflowList.value = []
    }
  }

  function parsePaste(): Record<string, unknown> {
    const raw = pasteJson.value.trim()
    if (!raw) throw new Error('paste_empty')
    const parsed = JSON.parse(raw) as unknown
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('paste_invalid')
    return parsed as Record<string, unknown>
  }

  async function runPreviewForPaste() {
    const bundle = parsePaste()
    preview.value = await previewImportBundle({ bundle, kind: uploadKindOverride.value || undefined })
    diffResult.value = await diffImportBundle(bundle)
  }

  async function pollJob(jobId: string) {
    const job = await getImportJobStatus(jobId)
    importJobSteps.value = job.steps || []
    if (job.status === 'completed' && job.result) {
      stopJobPoll()
      lastResult.value = job.result
      importing.value = false
      pushRecent(job.result.bundle_id)
      if (autoNavigate.value && job.result.edit_url_hint) navigateTo(job.result.edit_url_hint)
    } else if (job.status === 'failed') {
      stopJobPoll()
      importing.value = false
      errorMessage.value = job.error || 'import_failed'
    }
  }

  function startJobPoll(jobId: string) {
    importJobId.value = jobId
    stopJobPoll()
    jobPollTimer = setInterval(() => {
      void pollJob(jobId)
    }, 1200)
    void pollJob(jobId)
  }

  function stopJobPoll() {
    if (jobPollTimer) {
      clearInterval(jobPollTimer)
      jobPollTimer = null
    }
    importJobId.value = null
  }

  async function runImport() {
    importing.value = true
    errorMessage.value = null
    lastResult.value = null
    validateHint.value = null
    const common = {
      publish_workflows: publishWorkflows.value,
      wait_document_index: waitDocumentIndex.value,
      conflict_strategy: conflictStrategy.value,
      run_publish_gate: runPublishGate.value,
      use_async_job: useAsyncJob.value && showPlatformOptions.value,
    }
    try {
      let res: ImportRunResponse
      if (sourceMode.value === 'catalog') {
        const item = selectedCatalogItem.value
        if (!item) return
        res = await runOneClickImport({
          kind: item.kind,
          bundle_id: item.bundle_id,
          ...common,
        })
      } else {
        const bundle = parsePaste()
        res = await runOneClickImportFromBody({
          bundle,
          kind: uploadKindOverride.value || undefined,
          ...common,
        })
      }
      if (res.job_id) {
        startJobPoll(res.job_id)
        return
      }
      lastResult.value = res
      pushRecent(res.bundle_id)
      if (autoNavigate.value && res.edit_url_hint) navigateTo(res.edit_url_hint)
    } catch (e) {
      errorMessage.value = (e as Error).message
    } finally {
      if (!importJobId.value) importing.value = false
    }
  }

  async function onUploadFile(file: File) {
    importing.value = true
    errorMessage.value = null
    lastResult.value = null
    try {
      const res = await uploadImportBundle(file, {
        kind: uploadKindOverride.value || undefined,
        publish_workflows: publishWorkflows.value,
        wait_document_index: waitDocumentIndex.value,
        conflict_strategy: conflictStrategy.value,
        run_publish_gate: runPublishGate.value,
      })
      lastResult.value = res
      pushRecent(res.bundle_id)
      const text = await file.text().catch(() => '')
      if (text) {
        try {
          const bundle = JSON.parse(text) as Record<string, unknown>
          preview.value = await previewImportBundle({ bundle })
          diffResult.value = await diffImportBundle(bundle)
        } catch {
          /* zip */
        }
      }
      if (autoNavigate.value && res.edit_url_hint) navigateTo(res.edit_url_hint)
    } catch (e) {
      errorMessage.value = (e as Error).message
    } finally {
      importing.value = false
    }
  }

  async function runDiscoverExport() {
    if (!exportWorkflowId.value) return
    const data = await discoverImportExport({ workflow_ids: [exportWorkflowId.value] })
    exportItems.value = data.items || []
  }

  async function runExport() {
    if (!exportWorkflowId.value || !exportBundleId.value.trim()) return
    exporting.value = true
    errorMessage.value = null
    const selected = exportItems.value.filter((x) => x.selected)
    const pick = (kind: string) => selected.filter((x) => x.kind === kind).map((x) => x.id)
    try {
      const res = await exportEnvironmentBundle(
        {
          kind: exportKind.value,
          format: exportFormat.value,
          bundle_id: exportBundleId.value.trim(),
          name: exportName.value.trim() || exportBundleId.value.trim(),
          description: exportDescription.value,
          workflow_ids: pick('workflow').length ? pick('workflow') : [exportWorkflowId.value],
          agent_ids: pick('agent'),
          knowledge_base_ids: pick('knowledge_base'),
          skill_ids: pick('skill'),
          mcp_server_ids: pick('mcp_server'),
        },
        { download: true },
      )
      if (res.format === 'zip') downloadBlob(res.blob, res.filename)
      else downloadBlob(new Blob([JSON.stringify(res.data.bundle, null, 2)], { type: 'application/json' }), res.data.filename)
    } catch (e) {
      errorMessage.value = (e as Error).message
    } finally {
      exporting.value = false
    }
  }

  function downloadBlob(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  function goCanvasDemo() {
    wizardPath.value = 'canvas'
    void router.push({ name: 'workflow-create' })
  }

  function goPlatformCatalog() {
    wizardPath.value = 'platform'
    panelMode.value = 'import'
    sourceMode.value = 'catalog'
    kindFilter.value = 'platform'
  }

  function goUploadPath() {
    wizardPath.value = 'upload'
    panelMode.value = 'import'
    sourceMode.value = 'upload'
  }

  async function copyCurl() {
    const hint = preview.value?.curl_hint || lastResult.value?.curl_hint
    if (!hint) return
    await navigator.clipboard.writeText(hint)
    curlCopied.value = true
    setTimeout(() => {
      curlCopied.value = false
    }, 2000)
  }

  onMounted(() => {
    loadRecent()
    void loadCatalog()
    void loadWorkflows()
    if (options?.initialWorkflowId) {
      panelMode.value = 'export'
      void runDiscoverExport()
    }
  })

  onUnmounted(() => {
    stopJobPoll()
  })

  return {
    panelMode,
    wizardPath,
    loading,
    importing,
    exporting,
    catalog,
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
    diffResult,
    errorMessage,
    pasteJson,
    uploadKindOverride,
    validateHint,
    workflowList,
    exportWorkflowId,
    exportBundleId,
    exportName,
    exportDescription,
    exportFormat,
    exportKind,
    exportItems,
    importJobSteps,
    recentBundles,
    curlCopied,
    catalogKey,
    loadCatalog,
    refreshPreflight,
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
    router,
  }
}

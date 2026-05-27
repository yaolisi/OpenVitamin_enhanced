<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import OneClickImportPanel from '@/components/import/OneClickImportPanel.vue'

defineOptions({ name: 'BundleImportView' })

const route = useRoute()
const initialWorkflowId = computed(() => String(route.query.workflowId || ''))
const initialPanelMode = computed(() =>
  route.query.mode === 'export' ? ('export' as const) : ('import' as const),
)
</script>

<template>
  <div class="flex flex-1 min-h-0 min-w-0 flex-col bg-background overflow-auto">
    <OneClickImportPanel
      :initial-workflow-id="initialWorkflowId || undefined"
      :initial-panel-mode="initialPanelMode"
    />
  </div>
</template>

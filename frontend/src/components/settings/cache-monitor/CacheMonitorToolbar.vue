<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Button } from '@/components/ui/button'

defineProps<{
  cacheStatsLoading: boolean
  autoRefreshEnabled: boolean
  autoRefreshIntervalMs: number
  lastRefreshedText: string
}>()

const emit = defineEmits<{
  (e: 'refresh'): void
  (e: 'toggle-auto-refresh'): void
  (e: 'set-interval', ms: number): void
  (e: 'reset-prefs'): void
}>()
const { t } = useI18n()
</script>

<template>
  <div class="space-y-3">
    <div class="flex items-center justify-between gap-4">
      <div>
        <h3 class="text-sm font-semibold text-foreground">{{ t('cache_monitor.toolbar.title') }}</h3>
        <p class="text-xs text-muted-foreground">{{ t('cache_monitor.toolbar.desc') }}</p>
      </div>
      <div class="flex items-center gap-2">
        <Button
          variant="outline"
          class="h-9"
          :disabled="cacheStatsLoading"
          @click="emit('refresh')"
        >
          {{ cacheStatsLoading ? t('cache_monitor.toolbar.refreshing') : t('cache_monitor.toolbar.refresh') }}
        </Button>
        <Button
          variant="outline"
          class="h-9"
          @click="emit('toggle-auto-refresh')"
        >
          {{ autoRefreshEnabled ? t('cache_monitor.toolbar.pause_polling') : t('cache_monitor.toolbar.resume_polling') }}
        </Button>
      </div>
    </div>

    <div class="flex items-center justify-between gap-3 text-xs text-muted-foreground">
      <div>{{ t('cache_monitor.toolbar.last_refreshed') }}{{ lastRefreshedText }}</div>
      <div class="flex items-center gap-2">
        <span>{{ t('cache_monitor.toolbar.polling_interval') }}</span>
        <Button variant="outline" class="h-7 px-2" :disabled="autoRefreshIntervalMs === 10000" @click="emit('set-interval', 10000)">10s</Button>
        <Button variant="outline" class="h-7 px-2" :disabled="autoRefreshIntervalMs === 30000" @click="emit('set-interval', 30000)">30s</Button>
        <Button variant="outline" class="h-7 px-2" :disabled="autoRefreshIntervalMs === 60000" @click="emit('set-interval', 60000)">60s</Button>
        <Button variant="outline" class="h-7 px-2" @click="emit('reset-prefs')">{{ t('cache_monitor.toolbar.reset') }}</Button>
      </div>
    </div>
  </div>
</template>

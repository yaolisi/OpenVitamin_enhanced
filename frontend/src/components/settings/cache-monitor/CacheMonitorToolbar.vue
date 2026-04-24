<script setup lang="ts">
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
</script>

<template>
  <div class="space-y-3">
    <div class="flex items-center justify-between gap-4">
      <div>
        <h3 class="text-sm font-semibold text-foreground">推理缓存统计</h3>
        <p class="text-xs text-muted-foreground">用于观察缓存命中率和节省时延效果</p>
      </div>
      <div class="flex items-center gap-2">
        <Button
          variant="outline"
          class="h-9"
          :disabled="cacheStatsLoading"
          @click="emit('refresh')"
        >
          {{ cacheStatsLoading ? '刷新中...' : '刷新统计' }}
        </Button>
        <Button
          variant="outline"
          class="h-9"
          @click="emit('toggle-auto-refresh')"
        >
          {{ autoRefreshEnabled ? '暂停轮询' : '继续轮询' }}
        </Button>
      </div>
    </div>

    <div class="flex items-center justify-between gap-3 text-xs text-muted-foreground">
      <div>最近刷新：{{ lastRefreshedText }}</div>
      <div class="flex items-center gap-2">
        <span>轮询间隔</span>
        <Button variant="outline" class="h-7 px-2" :disabled="autoRefreshIntervalMs === 10000" @click="emit('set-interval', 10000)">10s</Button>
        <Button variant="outline" class="h-7 px-2" :disabled="autoRefreshIntervalMs === 30000" @click="emit('set-interval', 30000)">30s</Button>
        <Button variant="outline" class="h-7 px-2" :disabled="autoRefreshIntervalMs === 60000" @click="emit('set-interval', 60000)">60s</Button>
        <Button variant="outline" class="h-7 px-2" @click="emit('reset-prefs')">重置</Button>
      </div>
    </div>
  </div>
</template>

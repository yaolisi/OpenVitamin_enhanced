<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

defineProps<{
  clearCacheLoading: boolean
  clearCacheMessage: string
  clearCacheError: string
  cacheClearUserId: string
  cacheClearModelAlias: string
}>()

const emit = defineEmits<{
  (e: 'update:cacheClearUserId', value: string): void
  (e: 'update:cacheClearModelAlias', value: string): void
  (e: 'clear-cache'): void
}>()
const { t } = useI18n()
</script>

<template>
  <div class="space-y-4">
    <div class="grid gap-3 md:grid-cols-2">
      <div class="space-y-2">
        <p class="text-xs text-muted-foreground">{{ t('cache_monitor.clear.user_scope') }}</p>
        <Input
          :model-value="cacheClearUserId"
          :placeholder="t('cache_monitor.clear.user_placeholder')"
          class="h-10 bg-background border-border text-foreground rounded-xl px-3"
          @update:modelValue="(v) => emit('update:cacheClearUserId', String(v ?? ''))"
        />
      </div>
      <div class="space-y-2">
        <p class="text-xs text-muted-foreground">{{ t('cache_monitor.clear.model_scope') }}</p>
        <Input
          :model-value="cacheClearModelAlias"
          :placeholder="t('cache_monitor.clear.model_placeholder')"
          class="h-10 bg-background border-border text-foreground rounded-xl px-3"
          @update:modelValue="(v) => emit('update:cacheClearModelAlias', String(v ?? ''))"
        />
      </div>
    </div>
    <div class="flex items-center gap-3">
      <Button
        variant="outline"
        class="h-10"
        :disabled="clearCacheLoading"
        @click="emit('clear-cache')"
      >
        {{ clearCacheLoading ? t('cache_monitor.clear.clearing') : t('cache_monitor.clear.clear_action') }}
      </Button>
      <span v-if="clearCacheMessage" class="text-xs text-emerald-400">{{ clearCacheMessage }}</span>
      <span v-if="clearCacheError" class="text-xs text-red-400">{{ clearCacheError }}</span>
    </div>
  </div>
</template>

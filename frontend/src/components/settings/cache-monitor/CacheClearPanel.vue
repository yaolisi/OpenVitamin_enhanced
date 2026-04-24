<script setup lang="ts">
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
</script>

<template>
  <div class="space-y-4">
    <div class="grid gap-3 md:grid-cols-2">
      <div class="space-y-2">
        <p class="text-xs text-muted-foreground">按用户清理（可选）</p>
        <Input
          :model-value="cacheClearUserId"
          placeholder="例如：u1"
          class="h-10 bg-background border-border text-foreground rounded-xl px-3"
          @update:modelValue="(v) => emit('update:cacheClearUserId', String(v ?? ''))"
        />
      </div>
      <div class="space-y-2">
        <p class="text-xs text-muted-foreground">按模型别名清理（可选）</p>
        <Input
          :model-value="cacheClearModelAlias"
          placeholder="例如：reasoning-model"
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
        {{ clearCacheLoading ? '清理中...' : '清理推理缓存' }}
      </Button>
      <span v-if="clearCacheMessage" class="text-xs text-emerald-400">{{ clearCacheMessage }}</span>
      <span v-if="clearCacheError" class="text-xs text-red-400">{{ clearCacheError }}</span>
    </div>
  </div>
</template>

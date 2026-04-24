<script setup lang="ts">
defineProps<{
  issuedTotal: number
  successRateText: string
  actorMismatchRateText: string
  rateLimitedTotal: number
  issuedDeltaText: string
  issuedDeltaClass: string
  successDeltaText: string
  successDeltaClass: string
  mismatchDeltaText: string
  mismatchDeltaClass: string
  rateLimitedDeltaText: string
  rateLimitedDeltaClass: string
}>()
</script>

<template>
  <div class="grid gap-3 md:grid-cols-4">
    <div class="rounded-xl border border-border/60 bg-background/60 p-3">
      <div class="text-xs text-muted-foreground">挑战码签发次数</div>
      <div class="mt-1 text-lg font-semibold">{{ issuedTotal }}</div>
      <div class="mt-1 text-xs" :class="issuedDeltaClass">Δ {{ issuedDeltaText }}</div>
    </div>
    <div class="rounded-xl border border-border/60 bg-background/60 p-3">
      <div class="text-xs text-muted-foreground">挑战码校验成功率</div>
      <div class="mt-1 text-lg font-semibold">{{ successRateText }}</div>
      <div class="mt-1 text-xs" :class="successDeltaClass">Δ success {{ successDeltaText }}</div>
    </div>
    <div class="rounded-xl border border-border/60 bg-background/60 p-3">
      <div class="text-xs text-muted-foreground">跨用户失败占比</div>
      <div class="mt-1 text-lg font-semibold">{{ actorMismatchRateText }}</div>
      <div class="mt-1 text-xs" :class="mismatchDeltaClass">Δ mismatch {{ mismatchDeltaText }}</div>
    </div>
    <div class="rounded-xl border border-border/60 bg-background/60 p-3">
      <div class="text-xs text-muted-foreground">限流触发次数</div>
      <div class="mt-1 text-lg font-semibold">{{ rateLimitedTotal }}</div>
      <div class="mt-1 text-xs" :class="rateLimitedDeltaClass">Δ {{ rateLimitedDeltaText }}</div>
    </div>
  </div>
</template>

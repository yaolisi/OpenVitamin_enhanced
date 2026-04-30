<script setup lang="ts">
import { useI18n } from 'vue-i18n'
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
const { t } = useI18n()
</script>

<template>
  <div class="grid gap-3 md:grid-cols-4">
    <div class="rounded-xl border border-border/60 bg-background/60 p-3">
      <div class="text-xs text-muted-foreground">{{ t('cache_monitor.security.issued_total') }}</div>
      <div class="mt-1 text-lg font-semibold">{{ issuedTotal }}</div>
      <div class="mt-1 text-xs" :class="issuedDeltaClass">Δ {{ issuedDeltaText }}</div>
    </div>
    <div class="rounded-xl border border-border/60 bg-background/60 p-3">
      <div class="text-xs text-muted-foreground">{{ t('cache_monitor.security.success_rate') }}</div>
      <div class="mt-1 text-lg font-semibold">{{ successRateText }}</div>
      <div class="mt-1 text-xs" :class="successDeltaClass">Δ {{ t('cache_monitor.security.delta_success') }} {{ successDeltaText }}</div>
    </div>
    <div class="rounded-xl border border-border/60 bg-background/60 p-3">
      <div class="text-xs text-muted-foreground">{{ t('cache_monitor.security.actor_mismatch_rate') }}</div>
      <div class="mt-1 text-lg font-semibold">{{ actorMismatchRateText }}</div>
      <div class="mt-1 text-xs" :class="mismatchDeltaClass">Δ {{ t('cache_monitor.security.delta_mismatch') }} {{ mismatchDeltaText }}</div>
    </div>
    <div class="rounded-xl border border-border/60 bg-background/60 p-3">
      <div class="text-xs text-muted-foreground">{{ t('cache_monitor.security.rate_limited_total') }}</div>
      <div class="mt-1 text-lg font-semibold">{{ rateLimitedTotal }}</div>
      <div class="mt-1 text-xs" :class="rateLimitedDeltaClass">Δ {{ rateLimitedDeltaText }}</div>
    </div>
  </div>
</template>

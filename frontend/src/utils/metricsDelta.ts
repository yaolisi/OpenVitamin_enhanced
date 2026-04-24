export function metricDelta(current: number, previous: number): number {
  return Number.isFinite(current) && Number.isFinite(previous) ? current - previous : 0
}

export function metricDeltaText(current: number, previous: number): string {
  const delta = metricDelta(current, previous)
  if (delta > 0) return `+${delta}`
  if (delta < 0) return `${delta}`
  return '0'
}

export function metricDeltaClass(delta: number, inverse = false): string {
  if (delta === 0) return 'text-muted-foreground'
  if (inverse) return delta > 0 ? 'text-red-400' : 'text-emerald-400'
  return delta > 0 ? 'text-emerald-400' : 'text-red-400'
}

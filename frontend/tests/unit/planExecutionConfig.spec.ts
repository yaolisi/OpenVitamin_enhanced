import { describe, expect, it } from 'vitest'
import {
  buildPlanExecutionPayload,
  defaultPlanExecutionFormState,
  loadPlanExecutionFormFromModelParams,
} from '@/utils/planExecutionConfig'

describe('planExecutionConfig', () => {
  it('defaultPlanExecutionFormState is empty for optional fields', () => {
    const s = defaultPlanExecutionFormState()
    expect(s.maxParallelInGroup).toBe(0)
    expect(s.onTimeoutStrategy).toBe('')
  })

  it('buildPlanExecutionPayload returns null when nothing set', () => {
    const f = defaultPlanExecutionFormState()
    expect(buildPlanExecutionPayload(f)).toBeNull()
  })

  it('roundtrip: build then load from model_params', () => {
    const f = defaultPlanExecutionFormState()
    f.maxParallelInGroup = 3
    f.defaultTimeoutSeconds = 15
    f.defaultMaxRetries = 1
    f.retryIntervalSeconds = 0.5
    f.onTimeoutStrategy = 'stop'
    const pe = buildPlanExecutionPayload(f)
    expect(pe).toBeTruthy()
    const back = loadPlanExecutionFormFromModelParams({ plan_execution: pe! })
    expect(back.maxParallelInGroup).toBe(3)
    expect(back.defaultTimeoutSeconds).toBe(15)
    expect(back.defaultMaxRetries).toBe(1)
    expect(back.retryIntervalSeconds).toBe(0.5)
    expect(back.onTimeoutStrategy).toBe('stop')
  })

  it('loadPlanExecutionFormFromModelParams handles missing plan_execution', () => {
    const s = loadPlanExecutionFormFromModelParams({ intent_rules: [] })
    expect(s).toEqual(defaultPlanExecutionFormState())
  })
})

import { describe, expect, it } from 'vitest'
import { buildWorkflowNewRunQuery, buildWorkflowRunPresetQuery } from '@/utils/workflowRunNavigation'

describe('buildWorkflowNewRunQuery', () => {
  it('preserves preset keys and sets auto_start + t', () => {
    const q = buildWorkflowNewRunQuery({
      version_id: 'ver-1',
      input_data: '{"x":1}',
    })
    expect(q.version_id).toBe('ver-1')
    expect(q.auto_start).toBe('1')
    expect(q.t).toMatch(/^\d+$/)
  })

  it('strips execution id keys', () => {
    const q = buildWorkflowNewRunQuery({
      execution_id: 'exec-old',
      executionId: 'legacy',
      global_context: '{}',
    })
    expect(q.execution_id).toBeUndefined()
    expect(q.executionId).toBeUndefined()
    expect(q.global_context).toBe('{}')
  })

  it('strips history_only so auto-run merge does not stay in read-only mode', () => {
    const q = buildWorkflowNewRunQuery({
      history_only: '1',
      version_id: 'v1',
    })
    expect(q.history_only).toBeUndefined()
    expect(q.auto_start).toBe('1')
    expect(q.version_id).toBe('v1')
  })
})

describe('buildWorkflowRunPresetQuery', () => {
  it('serializes input_data and global_context', () => {
    const q = buildWorkflowRunPresetQuery({
      inputData: { brief: 'test' },
      globalContext: { correlation_id: 'corr_abc' },
      versionId: 'v-1',
    })
    expect(JSON.parse(String(q.input_data))).toEqual({ brief: 'test' })
    expect(JSON.parse(String(q.global_context))).toEqual({ correlation_id: 'corr_abc' })
    expect(q.version_id).toBe('v-1')
    expect(q.auto_start).toBe('1')
  })
})

import { describe, expect, it } from 'vitest'
import {
  buildDefaultCollaborationGlobalContext,
  generateCorrelationId,
} from '@/utils/collaborationContext'

describe('collaborationContext', () => {
  it('generateCorrelationId has prefix', () => {
    const id = generateCorrelationId()
    expect(id.startsWith('corr_')).toBe(true)
    expect(id.length).toBeGreaterThan(10)
  })

  it('buildDefaultCollaborationGlobalContext includes orchestrator when set', () => {
    const ctx = buildDefaultCollaborationGlobalContext('agent_abc')
    expect(ctx.correlation_id).toBeTruthy()
    expect(ctx.orchestrator_agent_id).toBe('agent_abc')
  })
})

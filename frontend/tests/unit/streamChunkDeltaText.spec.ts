import { describe, expect, it } from 'vitest'
import { streamChunkDeltaText, type ChatStreamChunk } from '@/services/api'

describe('streamChunkDeltaText', () => {
  it('returns null for meta', () => {
    const c: ChatStreamChunk = {
      object: 'perilla.stream.meta',
      stream_id: 's1',
      completion_id: 'c1',
    }
    expect(streamChunkDeltaText(c)).toBeNull()
  })

  it('reads OpenAI delta', () => {
    const c: ChatStreamChunk = {
      id: 'x',
      object: 'chat.completion.chunk',
      created: 0,
      model: 'm',
      choices: [{ index: 0, delta: { content: 'hi' } }],
    }
    expect(streamChunkDeltaText(c)).toBe('hi')
  })

  it('reads jsonl c when not done', () => {
    const c: ChatStreamChunk = {
      object: 'perilla.stream.jsonl',
      i: 0,
      c: 'a',
      d: false,
    }
    expect(streamChunkDeltaText(c)).toBe('a')
  })

  it('returns null for jsonl d:true', () => {
    const c: ChatStreamChunk = {
      object: 'perilla.stream.jsonl',
      d: true,
    }
    expect(streamChunkDeltaText(c)).toBeNull()
  })

  it('reads md chunk', () => {
    const c: ChatStreamChunk = {
      object: 'perilla.stream.md',
      c: 'x',
    }
    expect(streamChunkDeltaText(c)).toBe('x')
  })
})

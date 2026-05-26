import { describe, expect, it } from 'vitest'
import {
  buildDemoWorkflowGraph,
  getDemoWorkflowBundle,
  listDemoWorkflowBundles,
} from '@/components/workflow/editor/demoWorkflowBundles'
import { validateWorkflowNodes, validateWorkflowPreflight } from '@/components/workflow/editor/validation'

describe('demoWorkflowBundles', () => {
  it('lists two demo bundles', () => {
    const list = listDemoWorkflowBundles()
    expect(list.length).toBe(2)
    expect(list.map((x) => x.demo_id).sort()).toEqual([
      'parallel-research-verify',
      'release-brief-gate',
    ])
  })

  it('builds release-brief graph with approval and checkpoint', () => {
    const graph = buildDemoWorkflowGraph('release-brief-gate')
    expect(graph).not.toBeNull()
    const types = graph!.nodes.map((n) => n.data?.type)
    expect(types).toContain('checkpoint')
    expect(graph!.nodes.some((n) => (n.data?.config as Record<string, unknown>)?.workflow_node_type === 'approval')).toBe(true)
    const base = validateWorkflowNodes(graph!.nodes)
    const preflight = validateWorkflowPreflight(graph!.nodes, graph!.edges)
    expect([...base.errors, ...preflight.errors]).toEqual([])
  })

  it('builds parallel-research graph with fork join verify_loop', () => {
    const graph = buildDemoWorkflowGraph('parallel-research-verify')
    expect(graph).not.toBeNull()
    const types = graph!.nodes.map((n) => n.data?.type)
    expect(types).toContain('fork')
    expect(types).toContain('join')
    expect(types).toContain('verify_loop')
    const bundle = getDemoWorkflowBundle('parallel-research-verify')
    expect(bundle?.sample_input?.topic).toBeTruthy()
  })
})

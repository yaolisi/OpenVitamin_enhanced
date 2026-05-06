import { describe, expect, it } from 'vitest'
import type { Node, Edge } from '@vue-flow/core'
import { fromWorkflowDag, inferEditorNodeType, toWorkflowDag } from '@/components/workflow/editor/serialization'
import { validateWorkflowNodes } from '@/components/workflow/editor/validation'
import type { WorkflowNodeData } from '@/components/workflow/editor/types'

describe('workflow sub-workflow editor support', () => {
  it('infers embedding / http_request / variable from workflow_node_type', () => {
    expect(
      inferEditorNodeType({
        id: 'e1',
        type: 'tool',
        name: 'E',
        config: { workflow_node_type: 'embedding' },
        position: { x: 0, y: 0 },
      }),
    ).toBe('embedding')
    expect(
      inferEditorNodeType({
        id: 'h1',
        type: 'tool',
        name: 'H',
        config: { workflow_node_type: 'http_request' },
        position: { x: 0, y: 0 },
      }),
    ).toBe('http_request')
    expect(
      inferEditorNodeType({
        id: 'v1',
        type: 'variable',
        name: 'V',
        config: {},
        position: { x: 0, y: 0 },
      }),
    ).toBe('variable')
  })

  it('infers sub_workflow editor type from workflow_node_type', () => {
    const t = inferEditorNodeType({
      id: 'sub-1',
      type: 'tool',
      name: 'Sub',
      config: { workflow_node_type: 'sub_workflow', target_workflow_id: 'wf-child' },
      position: { x: 100, y: 120 },
    })
    expect(t).toBe('sub_workflow')
  })

  it('persists System Prompt shortcut as prompt_template + role system (scheme B)', () => {
    const nodes = [
      {
        id: 'sp-1',
        type: 'workflow',
        position: { x: 0, y: 0 },
        data: {
          type: 'system_prompt',
          label: 'System',
          config: { template: 'You are helpful.', role: 'system' },
        },
      } as Node<WorkflowNodeData>,
    ]
    const dag = toWorkflowDag(nodes, [])
    expect(dag.nodes[0].type).toBe('prompt_template')
    expect(dag.nodes[0].config?.workflow_node_type).toBe('prompt_template')
    expect(dag.nodes[0].config?.role).toBe('system')
    const restored = fromWorkflowDag(dag)
    expect(restored.nodes[0].data.type).toBe('system_prompt')
  })

  it('infers system_prompt from prompt_template node when role is system', () => {
    expect(
      inferEditorNodeType({
        id: 'p1',
        type: 'prompt_template',
        name: 'P',
        config: { workflow_node_type: 'prompt_template', role: 'system', template: 'Hi' },
        position: { x: 0, y: 0 },
      }),
    ).toBe('system_prompt')
  })

  it('round-trips sub_workflow node through DAG serialization', () => {
    const nodes = [
      {
        id: 'sub-1',
        type: 'workflow',
        position: { x: 120, y: 80 },
        data: {
          type: 'sub_workflow',
          label: 'Sub-workflow',
          config: {
            target_workflow_id: 'wf-registration',
            target_version_selector: 'fixed',
            target_version_id: 'v-2026-01',
          },
        },
      } as Node<WorkflowNodeData>,
    ]
    const edges: Edge[] = []
    const dag = toWorkflowDag(nodes, edges)
    expect(dag.nodes[0].type).toBe('tool')
    expect(dag.nodes[0].config?.workflow_node_type).toBe('sub_workflow')

    const restored = fromWorkflowDag(dag)
    expect(restored.nodes[0].data.type).toBe('sub_workflow')
    expect((restored.nodes[0].data.config as Record<string, unknown>).target_workflow_id).toBe('wf-registration')
  })

  it('validates required fields for fixed version sub_workflow nodes', () => {
    const nodes = [
      {
        id: 'sub-invalid',
        type: 'workflow',
        position: { x: 0, y: 0 },
        data: {
          type: 'sub_workflow',
          label: 'Sub Invalid',
          config: {
            target_workflow_id: '',
            target_version_selector: 'fixed',
          },
        },
      } as Node<WorkflowNodeData>,
    ]
    const result = validateWorkflowNodes(nodes)
    expect(result.valid).toBe(false)
    expect(result.errors.some((e) => e.message.includes('target_workflow_id'))).toBe(true)
    expect(result.errors.some((e) => e.message.includes('target_version_id'))).toBe(true)
  })
})

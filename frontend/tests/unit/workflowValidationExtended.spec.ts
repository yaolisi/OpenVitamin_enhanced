import { describe, expect, it } from 'vitest'
import type { Edge, Node } from '@vue-flow/core'
import { validateWorkflowNodes, validateWorkflowPreflight } from '@/components/workflow/editor/validation'
import type { WorkflowNodeData } from '@/components/workflow/editor/types'

describe('validateWorkflowNodes — embedding / http / variable', () => {
  it('requires llm model_id or legacy model', () => {
    const nodes = [
      {
        id: 'llm1',
        type: 'workflow',
        position: { x: 0, y: 0 },
        data: { type: 'llm', label: 'Llm', config: { workflow_node_type: 'llm' } },
      },
    ] as Node<WorkflowNodeData>[]
    const r = validateWorkflowNodes(nodes)
    expect(r.valid).toBe(false)
    expect(r.errors.some((e) => e.messageKey === 'workflow_editor.llm_model_or_tier_required')).toBe(true)
  })

  it('accepts llm when model_tier is set', () => {
    const nodes = [
      {
        id: 'llm-tier',
        type: 'workflow',
        position: { x: 0, y: 0 },
        data: {
          type: 'llm',
          label: 'Llm',
          config: { model_tier: 'standard' },
        },
      },
    ] as Node<WorkflowNodeData>[]
    const r = validateWorkflowNodes(nodes)
    expect(r.valid).toBe(true)
  })

  it('accepts llm when legacy model is set', () => {
    const nodes = [
      {
        id: 'llm2',
        type: 'workflow',
        position: { x: 0, y: 0 },
        data: {
          type: 'llm',
          label: 'Llm',
          config: { workflow_node_type: 'llm', model: 'gpt-4o-mini' },
        },
      },
    ] as Node<WorkflowNodeData>[]
    const r = validateWorkflowNodes(nodes)
    expect(r.valid).toBe(true)
    expect(r.errors.some((e) => e.messageKey === 'workflow_editor.llm_model_or_tier_required')).toBe(false)
  })

  it('requires embedding model_id', () => {
    const nodes = [
      {
        id: 'e1',
        type: 'workflow',
        position: { x: 0, y: 0 },
        data: { type: 'embedding', label: 'E', config: {} },
      },
    ] as Node<WorkflowNodeData>[]
    const r = validateWorkflowNodes(nodes)
    expect(r.valid).toBe(false)
    expect(r.errors.some((e) => e.messageKey === 'workflow_editor.embedding_model_required')).toBe(true)
  })

  it('requires http url', () => {
    const nodes = [
      {
        id: 'h1',
        type: 'workflow',
        position: { x: 0, y: 0 },
        data: { type: 'http_request', label: 'H', config: { workflow_node_type: 'http_request' } },
      },
    ] as Node<WorkflowNodeData>[]
    const r = validateWorkflowNodes(nodes)
    expect(r.valid).toBe(false)
    expect(r.errors.some((e) => e.messageKey === 'workflow_editor.http_url_required')).toBe(true)
  })

  it('rejects variable.variables when not an object', () => {
    const nodes = [
      {
        id: 'v1',
        type: 'workflow',
        position: { x: 0, y: 0 },
        data: { type: 'variable', label: 'V', config: { variables: [] } },
      },
    ] as Node<WorkflowNodeData>[]
    const r = validateWorkflowNodes(nodes)
    expect(r.valid).toBe(false)
    expect(r.errors.some((e) => e.messageKey === 'workflow_editor.variable_map_object_required')).toBe(true)
  })

  it('requires python code', () => {
    const nodes = [
      {
        id: 'p1',
        type: 'workflow',
        position: { x: 0, y: 0 },
        data: { type: 'python', label: 'P', config: { workflow_node_type: 'python', code: '' } },
      },
    ] as Node<WorkflowNodeData>[]
    const r = validateWorkflowNodes(nodes)
    expect(r.valid).toBe(false)
    expect(r.errors.some((e) => e.messageKey === 'workflow_editor.python_code_required')).toBe(true)
  })

  it('allows empty python code when code_from_upstream', () => {
    const nodes = [
      {
        id: 'p2',
        type: 'workflow',
        position: { x: 0, y: 0 },
        data: {
          type: 'python',
          label: 'P',
          config: { workflow_node_type: 'python', code: '', code_from_upstream: true },
        },
      },
    ] as Node<WorkflowNodeData>[]
    const r = validateWorkflowNodes(nodes)
    expect(r.valid).toBe(true)
  })

  it('requires loop loop_body object', () => {
    const nodes = [
      {
        id: 'l1',
        type: 'workflow',
        position: { x: 0, y: 0 },
        data: { type: 'loop', label: 'L', config: { workflow_node_type: 'loop', loop_body: [] } },
      },
    ] as Node<WorkflowNodeData>[]
    const r = validateWorkflowNodes(nodes)
    expect(r.valid).toBe(false)
    expect(r.errors.some((e) => e.messageKey === 'workflow_editor.loop_body_object_required')).toBe(true)
  })

  it('requires loop_body tool_name when type tool', () => {
    const nodes = [
      {
        id: 'l2',
        type: 'workflow',
        position: { x: 0, y: 0 },
        data: {
          type: 'loop',
          label: 'L',
          config: { workflow_node_type: 'loop', loop_body: { type: 'tool', tool_name: '' } },
        },
      },
    ] as Node<WorkflowNodeData>[]
    const r = validateWorkflowNodes(nodes)
    expect(r.valid).toBe(false)
    expect(r.errors.some((e) => e.messageKey === 'workflow_editor.loop_body_tool_name_required')).toBe(true)
  })

  it('requires skill tool_name', () => {
    const nodes = [
      {
        id: 'sk1',
        type: 'workflow',
        position: { x: 0, y: 0 },
        data: { type: 'skill', label: 'SK', config: {} },
      },
    ] as Node<WorkflowNodeData>[]
    const r = validateWorkflowNodes(nodes)
    expect(r.valid).toBe(false)
    expect(r.errors.some((e) => e.messageKey === 'workflow_editor.skill_tool_name_required')).toBe(true)
  })

  it('requires shell command', () => {
    const nodes = [
      {
        id: 's1',
        type: 'workflow',
        position: { x: 0, y: 0 },
        data: { type: 'shell', label: 'S', config: { workflow_node_type: 'shell', command: '' } },
      },
    ] as Node<WorkflowNodeData>[]
    const r = validateWorkflowNodes(nodes)
    expect(r.valid).toBe(false)
    expect(r.errors.some((e) => e.messageKey === 'workflow_editor.shell_command_required')).toBe(true)
  })
})

describe('validateWorkflowPreflight — global.workflow_variables', () => {
  function condBranchEdges(condId: string): Edge[] {
    return [
      { id: 'e-ct', source: condId, target: 'o1', sourceHandle: 'true' },
      { id: 'e-cf', source: condId, target: 'o2', sourceHandle: 'false' },
    ]
  }

  it('flags missing workflow variable key when Variable nodes declare others', () => {
    const nodes = [
      {
        id: 'v1',
        type: 'workflow',
        position: { x: 0, y: 0 },
        data: { type: 'variable', label: 'V', config: { variables: { a: 1 } } },
      },
      {
        id: 'c1',
        type: 'workflow',
        position: { x: 0, y: 0 },
        data: {
          type: 'condition',
          label: 'C',
          config: { condition_expression: '${global.workflow_variables.b} === 1' },
        },
      },
      {
        id: 'o1',
        type: 'workflow',
        position: { x: 0, y: 0 },
        data: { type: 'output', label: 'O1', config: {} },
      },
      {
        id: 'o2',
        type: 'workflow',
        position: { x: 0, y: 0 },
        data: { type: 'output', label: 'O2', config: {} },
      },
    ] as Node<WorkflowNodeData>[]
    const r = validateWorkflowPreflight(nodes, condBranchEdges('c1'))
    expect(r.valid).toBe(false)
    expect(r.errors.some((e) => e.messageKey === 'workflow_editor.condition_workflow_variable_missing')).toBe(
      true,
    )
  })

  it('accepts nested path when top key is declared', () => {
    const nodes = [
      {
        id: 'v1',
        type: 'workflow',
        position: { x: 0, y: 0 },
        data: { type: 'variable', label: 'V', config: { variables: { a: { x: 1 } } } },
      },
      {
        id: 'c1',
        type: 'workflow',
        position: { x: 0, y: 0 },
        data: {
          type: 'condition',
          label: 'C',
          config: { condition_expression: '${global.workflow_variables.a.x} === 1' },
        },
      },
      {
        id: 'o1',
        type: 'workflow',
        position: { x: 0, y: 0 },
        data: { type: 'output', label: 'O1', config: {} },
      },
      {
        id: 'o2',
        type: 'workflow',
        position: { x: 0, y: 0 },
        data: { type: 'output', label: 'O2', config: {} },
      },
    ] as Node<WorkflowNodeData>[]
    const r = validateWorkflowPreflight(nodes, condBranchEdges('c1'))
    expect(r.errors.some((e) => e.messageKey === 'workflow_editor.condition_workflow_variable_missing')).toBe(
      false,
    )
  })

  it('does not require declared keys when no Variable node exists', () => {
    const nodes = [
      {
        id: 'c1',
        type: 'workflow',
        position: { x: 0, y: 0 },
        data: {
          type: 'condition',
          label: 'C',
          config: { condition_expression: '${global.workflow_variables.only_at_runtime} === 1' },
        },
      },
      {
        id: 'o1',
        type: 'workflow',
        position: { x: 0, y: 0 },
        data: { type: 'output', label: 'O1', config: {} },
      },
      {
        id: 'o2',
        type: 'workflow',
        position: { x: 0, y: 0 },
        data: { type: 'output', label: 'O2', config: {} },
      },
    ] as Node<WorkflowNodeData>[]
    const r = validateWorkflowPreflight(nodes, condBranchEdges('c1'))
    expect(r.errors.some((e) => e.messageKey === 'workflow_editor.condition_workflow_variable_missing')).toBe(
      false,
    )
  })
})

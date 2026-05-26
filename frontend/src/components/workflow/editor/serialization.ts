import type { Edge, Node } from '@vue-flow/core'
import type { WorkflowDagPayload, WorkflowEdgePayload, WorkflowNodePayload } from '@/services/api'
import { i18n } from '@/i18n'
import type { EditorNodeType, WorkflowNodeData } from './types'

const EDITOR_TO_RUNTIME_TYPE: Record<EditorNodeType, string> = {
  start: 'input',
  group: 'group',
  llm: 'llm',
  agent: 'agent',
  embedding: 'embedding',
  prompt_template: 'prompt_template',
  system_prompt: 'prompt_template',
  input: 'input',
  output: 'output',
  variable: 'variable',
  condition: 'condition',
  loop: 'loop',
  parallel: 'parallel',
  fork: 'fork',
  join: 'join',
  verify_loop: 'verify_loop',
  checkpoint: 'tool',
  sub_workflow: 'tool',
  skill: 'tool',
  http_request: 'tool',
  python: 'script',
  shell: 'script',
}

const RUNTIME_TO_EDITOR_TYPE: Record<string, EditorNodeType> = {
  start: 'start',
  input: 'input',
  llm: 'llm',
  embedding: 'embedding',
  prompt_template: 'prompt_template',
  variable: 'variable',
  parallel: 'parallel',
  fork: 'fork',
  join: 'join',
  verify_loop: 'verify_loop',
  checkpoint: 'checkpoint',
  output: 'output',
  condition: 'condition',
  loop: 'loop',
  tool: 'skill',
  script: 'shell',
  agent: 'agent',
}

const EDITOR_NODE_LABEL_KEY_MAP: Partial<Record<EditorNodeType, string>> = {
  start: 'workflow_editor.node_start',
  llm: 'workflow_editor.node_llm',
  embedding: 'workflow_editor.node_embedding',
  prompt_template: 'workflow_editor.node_prompt_template',
  system_prompt: 'workflow_editor.node_system_prompt',
  variable: 'workflow_editor.node_variable',
  parallel: 'workflow_editor.node_parallel',
  fork: 'workflow_editor.node_fork',
  join: 'workflow_editor.node_join',
  verify_loop: 'workflow_editor.node_verify_loop',
  checkpoint: 'workflow_editor.node_checkpoint',
  input: 'workflow_editor.node_input',
  output: 'workflow_editor.node_output',
  condition: 'workflow_editor.node_condition',
  loop: 'workflow_editor.node_loop',
  sub_workflow: 'workflow_editor.node_sub_workflow',
  shell: 'workflow_editor.node_shell',
  python: 'workflow_editor.node_python',
  http_request: 'workflow_editor.node_http_request',
  skill: 'workflow_editor.node_skill',
}

const EDITOR_NODE_SUBTITLE_FALLBACK_KEY_MAP: Partial<Record<EditorNodeType, string>> = {
  llm: 'workflow_editor.default_select_model',
  agent: 'workflow_editor.default_select_agent',
  skill: 'workflow_editor.default_select_tool',
}

/** 从持久化 DAG 推断编辑器节点类型（tool + workflow_node_type 等） */
export function inferEditorNodeType(node: WorkflowNodePayload): EditorNodeType {
  if (node.id === 'start') return 'start'
  const cfg = (node.config || {}) as Record<string, unknown>
  const wnt = String(cfg.workflow_node_type || '').trim().toLowerCase()
  if (wnt === 'sub_workflow') return 'sub_workflow'
  if (wnt === 'parallel') return 'parallel'
  if (wnt === 'loop') return 'loop'
  if (wnt === 'embedding') return 'embedding'
  if (wnt === 'variable') return 'variable'
  if (wnt === 'http_request') return 'http_request'
  /** 旧版曾单独存 workflow_node_type=system_prompt；加载后运行时会规范为 prompt_template */
  if (wnt === 'system_prompt') return 'system_prompt'
  const rtLower = String(node.type || '').trim().toLowerCase()
  const roleStr = String(cfg.role ?? '').trim().toLowerCase()
  if (
    (wnt === 'prompt_template' || rtLower === 'prompt_template') &&
    roleStr === 'system'
  ) {
    return 'system_prompt'
  }
  if (wnt === 'prompt_template') return 'prompt_template'
  if (wnt === 'python') return 'python'
  if (wnt === 'checkpoint') return 'checkpoint'
  if (wnt === 'fork') return 'fork'
  if (wnt === 'join') return 'join'
  if (wnt === 'verify_loop') return 'verify_loop'
  const mapped = RUNTIME_TO_EDITOR_TYPE[rtLower]
  if (mapped) return mapped
  return 'skill'
}

export function toWorkflowDag(
  nodes: Node<WorkflowNodeData>[],
  edges: Edge[],
  globalConfig: Record<string, unknown> = {},
): WorkflowDagPayload {
  const dagNodes: WorkflowNodePayload[] = nodes.map((node) => {
    const data = node.data ?? { type: 'skill', label: 'Tool', config: {} }
    const editorType = data.type
    const runtimeType = EDITOR_TO_RUNTIME_TYPE[editorType] ?? editorType
    const config = { ...(data.config || {}) } as Record<string, unknown>

    if (editorType === 'llm') {
      const modelId = typeof config.model_id === 'string' ? config.model_id.trim() : ''
      const legacyModel = typeof config.model === 'string' ? config.model.trim() : ''
      if (!modelId && legacyModel) {
        config.model_id = legacyModel
      }
      // 归一化：持久化时不再写 legacy model 字段
      delete config.model
    }

    if (editorType === 'embedding') {
      const modelId = typeof config.model_id === 'string' ? config.model_id.trim() : ''
      const legacyModel = typeof config.model === 'string' ? config.model.trim() : ''
      if (!modelId && legacyModel) {
        config.model_id = legacyModel
      }
      delete config.model
      config.workflow_node_type = 'embedding'
    }

    if (editorType === 'variable') {
      config.workflow_node_type = 'variable'
    }

    if (editorType === 'parallel') {
      config.workflow_node_type = 'parallel'
    }

    if (editorType === 'checkpoint') {
      config.workflow_node_type = 'checkpoint'
    }

    if (editorType === 'fork') {
      config.workflow_node_type = 'fork'
    }

    if (editorType === 'join') {
      config.workflow_node_type = 'join'
      if (!config.dependency_mode) {
        config.dependency_mode = 'all'
      }
    }

    if (editorType === 'verify_loop') {
      config.workflow_node_type = 'verify_loop'
      const lb = config.loop_body
      if (!lb || typeof lb !== 'object' || Array.isArray(lb)) {
        config.loop_body = {
          type: 'llm',
          model_tier: 'standard',
          prompt: '根据任务迭代改进，输出 JSON 含 text 字段。',
        }
      }
    }

    if (editorType === 'loop') {
      config.workflow_node_type = 'loop'
      const lb = config.loop_body
      if (!lb || typeof lb !== 'object' || Array.isArray(lb)) {
        config.loop_body = { type: 'tool', tool_name: 'time.now' }
      }
    }

    /** 方案 B：System Prompt 仅为快捷入口，持久化为 prompt_template + role=system */
    if (editorType === 'system_prompt') {
      config.workflow_node_type = 'prompt_template'
      if (config.role === undefined || config.role === null || config.role === '') {
        config.role = 'system'
      }
    }

    if (editorType === 'prompt_template') {
      config.workflow_node_type = 'prompt_template'
    }

    if (editorType === 'http_request') {
      config.workflow_node_type = 'http_request'
      if (!config.tool_name) {
        config.tool_name = 'http.request'
      }
    }

    if (editorType === 'agent') {
      const timeout = config.timeout
      const legacyTimeout = config.agent_timeout_seconds
      if ((timeout === undefined || timeout === null || timeout === '') && legacyTimeout !== undefined && legacyTimeout !== null && legacyTimeout !== '') {
        config.timeout = legacyTimeout
      }
      delete config.agent_timeout_seconds
    }

    if (editorType === 'skill' && !config.tool_name && typeof config.tool_id === 'string' && config.tool_id) {
      config.tool_name = config.tool_id
    }
    if (editorType === 'skill') {
      // 归一化：tool_name 为主，tool_id 仅作为历史兼容输入
      delete config.tool_id
    }

    if (editorType === 'shell' || editorType === 'python') {
      config.workflow_node_type = editorType
    }
    if (editorType === 'sub_workflow') {
      config.workflow_node_type = 'sub_workflow'
    }

    return {
      id: node.id,
      type: runtimeType,
      name: data.label,
      config,
      position: node.position,
    }
  })

  const dagEdges: WorkflowEdgePayload[] = edges.map((edge) => ({
    from_node: edge.source,
    to_node: edge.target,
    condition: ((edge.data as Record<string, unknown> | undefined)?.condition as string) || null,
    label: typeof edge.label === 'string' ? edge.label : null,
    source_handle: typeof edge.sourceHandle === 'string' ? edge.sourceHandle : null,
    target_handle: typeof edge.targetHandle === 'string' ? edge.targetHandle : null,
  }))

  return {
    nodes: dagNodes,
    edges: dagEdges,
    entry_node: dagNodes[0]?.id ?? null,
    global_config: globalConfig,
  }
}

export function fromWorkflowDag(dag: WorkflowDagPayload): {
  nodes: Node<WorkflowNodeData>[]
  edges: Edge[]
} {
  const nodes: Node<WorkflowNodeData>[] = (dag.nodes || []).map((node) => {
    const editorType = inferEditorNodeType(node)
    const config = { ...(node.config || {}) }

    return {
      id: node.id,
      type: 'workflow',
      position: node.position ?? { x: 80, y: 120 },
      data: {
        type: editorType,
        label: node.name || labelForEditorType(editorType),
        subtitle: subtitleFromConfig(editorType, config),
        config,
      },
    }
  })

  const edges: Edge[] = (dag.edges || []).map((edge, index) => ({
    id: `e-${edge.from_node}-${edge.to_node}-${index}`,
    source: edge.from_node,
    target: edge.to_node,
    label: edge.label || undefined,
    sourceHandle: edge.source_handle || undefined,
    targetHandle: edge.target_handle || undefined,
    data: edge.condition ? { condition: edge.condition } : undefined,
  }))

  return { nodes, edges }
}

function labelForEditorType(type: EditorNodeType): string {
  const t = i18n.global.t
  const key = EDITOR_NODE_LABEL_KEY_MAP[type] || 'workflow_editor.node_skill'
  return String(t(key))
}

function subtitleFromConfig(type: EditorNodeType, config: Record<string, unknown>): string | undefined {
  const t = i18n.global.t
  if (type === 'llm') {
    return (config.model_display_name as string) || (config.model_id as string) || (config.model as string) || String(t(EDITOR_NODE_SUBTITLE_FALLBACK_KEY_MAP.llm!))
  }
  if (type === 'agent') {
    return (config.agent_display_name as string) || (config.agent_id as string) || String(t(EDITOR_NODE_SUBTITLE_FALLBACK_KEY_MAP.agent!))
  }
  if (type === 'skill') {
    return (config.tool_display_name as string) || (config.tool_name as string) || (config.tool_id as string) || String(t(EDITOR_NODE_SUBTITLE_FALLBACK_KEY_MAP.skill!))
  }
  if (type === 'sub_workflow') {
    const id = String((config.target_workflow_id as string) ?? '').trim()
    return id || undefined
  }
  if (type === 'embedding') {
    return (config.model_display_name as string) || (config.model_id as string) || undefined
  }
  if (type === 'http_request') {
    const u = String(config.url ?? '').trim()
    return u || undefined
  }
  if (type === 'parallel') {
    const mp = config.max_parallel
    return mp !== undefined && mp !== null ? String(mp) : undefined
  }
  return undefined
}

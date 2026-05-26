import type { Edge, Node } from '@vue-flow/core'
import type { WorkflowNodeData } from './types'

/** 高价值编排模板（对齐 OmX：澄清 → 计划 → 执行 → 验收） */
export type OrchestrationTemplateId =
  | 'clarify_plan_verify'
  | 'tiered_draft_refine'
  | 'acceptance_gate'
  | 'parallel_team'
  | 'ralph_verify_loop'

export interface OrchestrationTemplate {
  id: OrchestrationTemplateId
  name: string
  description: string
}

const TEMPLATES: OrchestrationTemplate[] = [
  {
    id: 'clarify_plan_verify',
    name: '澄清 · 计划 · 验收（OmX）',
    description:
      '需求澄清 → 计划模板 → 人工审批 → 执行 → 验收检查点 → 输出（对齐 deep-interview / ralplan / ralph 验收纪律）',
  },
  {
    id: 'tiered_draft_refine',
    name: '分档双 LLM（快稿 + 精修）',
    description: '低档位快速草稿 → 高档位精修 → 验收 → 输出（对齐 ecomode + ultrawork 分档路由）',
  },
  {
    id: 'acceptance_gate',
    name: '验收门禁',
    description: '输入 → LLM → 验收检查点 → 输出（最小 acceptance criteria 闭环）',
  },
  {
    id: 'parallel_team',
    name: '并行小队（Fork/Join）',
    description: '扇出 → 双路 LLM（低/标准分档）→ 汇聚 → 验收 → 输出（对齐 $team / ultrawork）',
  },
  {
    id: 'ralph_verify_loop',
    name: 'Ralph 验证环',
    description: '输入 → 验证环（迭代 LLM + 验收直至通过）→ 输出',
  },
]

function newId(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

function startNode(): Node<WorkflowNodeData> {
  return {
    id: 'start',
    type: 'workflow',
    position: { x: 80, y: 160 },
    data: { type: 'start', label: 'Start', config: {} },
  }
}

export function listOrchestrationTemplates(): OrchestrationTemplate[] {
  return TEMPLATES
}

export function buildOrchestrationGraph(templateId: OrchestrationTemplateId): {
  nodes: Node<WorkflowNodeData>[]
  edges: Edge[]
} {
  if (templateId === 'parallel_team') {
    const inputId = newId('input')
    const forkId = newId('fork')
    const branchA = newId('llm')
    const branchB = newId('llm')
    const joinId = newId('join')
    const cpId = newId('checkpoint')
    const outputId = newId('output')
    const nodes: Node<WorkflowNodeData>[] = [
      startNode(),
      {
        id: inputId,
        type: 'workflow',
        position: { x: 240, y: 200 },
        data: {
          type: 'input',
          label: 'Task',
          config: { input_key: 'task', workflow_node_type: 'input' },
        },
      },
      {
        id: forkId,
        type: 'workflow',
        position: { x: 440, y: 200 },
        data: {
          type: 'fork',
          label: 'Fork',
          config: { workflow_node_type: 'fork', branch_hint: 'parallel branches' },
        },
      },
      {
        id: branchA,
        type: 'workflow',
        position: { x: 660, y: 120 },
        data: {
          type: 'llm',
          label: 'Branch A (low)',
          config: {
            model_tier: 'low',
            prompt: '快速要点：{{global.input_data.task}}',
          },
        },
      },
      {
        id: branchB,
        type: 'workflow',
        position: { x: 660, y: 280 },
        data: {
          type: 'llm',
          label: 'Branch B (standard)',
          config: {
            model_tier: 'standard',
            prompt: '补充分析：{{global.input_data.task}}',
          },
        },
      },
      {
        id: joinId,
        type: 'workflow',
        position: { x: 880, y: 200 },
        data: {
          type: 'join',
          label: 'Join',
          config: { workflow_node_type: 'join', dependency_mode: 'all', merge_mode: 'flat' },
        },
      },
      {
        id: cpId,
        type: 'workflow',
        position: { x: 1080, y: 200 },
        data: {
          type: 'checkpoint',
          label: 'Acceptance',
          config: {
            workflow_node_type: 'checkpoint',
            required_keys: ['text'],
            forbid_error_key: true,
          },
        },
      },
      {
        id: outputId,
        type: 'workflow',
        position: { x: 1280, y: 200 },
        data: {
          type: 'output',
          label: 'Result',
          config: { output_key: 'result', workflow_node_type: 'output' },
        },
      },
    ]
    const edges: Edge[] = [
      { id: newId('e'), source: 'start', target: inputId },
      { id: newId('e'), source: inputId, target: forkId },
      { id: newId('e'), source: forkId, target: branchA },
      { id: newId('e'), source: forkId, target: branchB },
      { id: newId('e'), source: branchA, target: joinId },
      { id: newId('e'), source: branchB, target: joinId },
      { id: newId('e'), source: joinId, target: cpId },
      { id: newId('e'), source: cpId, target: outputId },
    ]
    return { nodes, edges }
  }

  if (templateId === 'ralph_verify_loop') {
    const inputId = newId('input')
    const verifyId = newId('verify')
    const outputId = newId('output')
    const nodes: Node<WorkflowNodeData>[] = [
      startNode(),
      {
        id: inputId,
        type: 'workflow',
        position: { x: 280, y: 160 },
        data: {
          type: 'input',
          label: 'Task',
          config: { input_key: 'task', workflow_node_type: 'input' },
        },
      },
      {
        id: verifyId,
        type: 'workflow',
        position: { x: 520, y: 160 },
        data: {
          type: 'verify_loop',
          label: 'Ralph Verify',
          config: {
            workflow_node_type: 'verify_loop',
            max_iterations: 5,
            required_keys: ['text'],
            forbid_error_key: true,
            loop_body: {
              type: 'llm',
              model_tier: 'thorough',
              prompt:
                '完成任务并输出 JSON（含 text）：\n\n{{global.input_data.task}}\n\n若上一轮有失败，请修正：{{prev}}',
              temperature: 0.3,
            },
          },
        },
      },
      {
        id: outputId,
        type: 'workflow',
        position: { x: 760, y: 160 },
        data: {
          type: 'output',
          label: 'Deliverable',
          config: { output_key: 'deliverable', workflow_node_type: 'output' },
        },
      },
    ]
    const edges: Edge[] = [
      { id: newId('e'), source: 'start', target: inputId },
      { id: newId('e'), source: inputId, target: verifyId },
      { id: newId('e'), source: verifyId, target: outputId },
    ]
    return { nodes, edges }
  }

  if (templateId === 'acceptance_gate') {
    const inputId = newId('input')
    const llmId = newId('llm')
    const cpId = newId('checkpoint')
    const outputId = newId('output')
    const nodes: Node<WorkflowNodeData>[] = [
      startNode(),
      {
        id: inputId,
        type: 'workflow',
        position: { x: 280, y: 160 },
        data: {
          type: 'input',
          label: 'Task Input',
          config: { input_key: 'task', workflow_node_type: 'input' },
        },
      },
      {
        id: llmId,
        type: 'workflow',
        position: { x: 520, y: 160 },
        data: {
          type: 'llm',
          label: 'Execute',
          subtitle: 'standard tier',
          config: {
            model_tier: 'standard',
            prompt:
              '根据任务完成工作，输出 JSON 含 text 字段：\n\n任务：{{global.input_data.task}}',
            temperature: 0.4,
          },
        },
      },
      {
        id: cpId,
        type: 'workflow',
        position: { x: 760, y: 160 },
        data: {
          type: 'checkpoint',
          label: 'Acceptance',
          config: {
            workflow_node_type: 'checkpoint',
            description: '输出须含非空 text，且上游无 error',
            required_keys: ['text'],
            forbid_error_key: true,
          },
        },
      },
      {
        id: outputId,
        type: 'workflow',
        position: { x: 980, y: 160 },
        data: {
          type: 'output',
          label: 'Result',
          config: { output_key: 'result', workflow_node_type: 'output' },
        },
      },
    ]
    const edges: Edge[] = [
      { id: newId('e'), source: 'start', target: inputId },
      { id: newId('e'), source: inputId, target: llmId },
      { id: newId('e'), source: llmId, target: cpId },
      { id: newId('e'), source: cpId, target: outputId },
    ]
    return { nodes, edges }
  }

  if (templateId === 'tiered_draft_refine') {
    const inputId = newId('input')
    const draftId = newId('llm')
    const refineId = newId('llm')
    const cpId = newId('checkpoint')
    const outputId = newId('output')
    const nodes: Node<WorkflowNodeData>[] = [
      startNode(),
      {
        id: inputId,
        type: 'workflow',
        position: { x: 260, y: 160 },
        data: {
          type: 'input',
          label: 'Task Input',
          config: { input_key: 'task', workflow_node_type: 'input' },
        },
      },
      {
        id: draftId,
        type: 'workflow',
        position: { x: 480, y: 100 },
        data: {
          type: 'llm',
          label: 'Draft (low)',
          subtitle: 'low tier',
          config: {
            model_tier: 'low',
            prompt: '快速草稿，简洁要点，任务：{{global.input_data.task}}',
            temperature: 0.5,
          },
        },
      },
      {
        id: refineId,
        type: 'workflow',
        position: { x: 700, y: 160 },
        data: {
          type: 'llm',
          label: 'Refine (thorough)',
          subtitle: 'thorough tier',
          config: {
            model_tier: 'thorough',
            prompt:
              '基于上游草稿精修为可交付结果，输出 JSON 含 text 字段。草稿上下文：{{prev}}',
            temperature: 0.3,
          },
        },
      },
      {
        id: cpId,
        type: 'workflow',
        position: { x: 920, y: 160 },
        data: {
          type: 'checkpoint',
          label: 'Acceptance',
          config: {
            workflow_node_type: 'checkpoint',
            description: '精修结果须含 text',
            required_keys: ['text'],
            min_nonempty_fields: 1,
          },
        },
      },
      {
        id: outputId,
        type: 'workflow',
        position: { x: 1140, y: 160 },
        data: {
          type: 'output',
          label: 'Result',
          config: { output_key: 'result', workflow_node_type: 'output' },
        },
      },
    ]
    const edges: Edge[] = [
      { id: newId('e'), source: 'start', target: inputId },
      { id: newId('e'), source: inputId, target: draftId },
      { id: newId('e'), source: draftId, target: refineId },
      { id: newId('e'), source: refineId, target: cpId },
      { id: newId('e'), source: cpId, target: outputId },
    ]
    return { nodes, edges }
  }

  // clarify_plan_verify
  const inputId = newId('input')
  const clarifyId = newId('llm')
  const planId = newId('prompt')
  const approvalId = newId('approval')
  const executeId = newId('llm')
  const cpId = newId('checkpoint')
  const outputId = newId('output')
  const nodes: Node<WorkflowNodeData>[] = [
    startNode(),
    {
      id: inputId,
      type: 'workflow',
      position: { x: 240, y: 200 },
      data: {
        type: 'input',
        label: 'Brief',
        config: { input_key: 'brief', workflow_node_type: 'input' },
      },
    },
    {
      id: clarifyId,
      type: 'workflow',
      position: { x: 440, y: 200 },
      data: {
        type: 'llm',
        label: 'Clarify',
        subtitle: 'standard',
        config: {
          model_tier: 'standard',
          prompt:
            '澄清需求：列出目标、约束、非目标、待确认问题。输入：{{global.input_data.brief}}',
          temperature: 0.4,
        },
      },
    },
    {
      id: planId,
      type: 'workflow',
      position: { x: 640, y: 200 },
      data: {
        type: 'prompt_template',
        label: 'Plan Template',
        config: {
          workflow_node_type: 'prompt_template',
          role: 'user',
          template:
            '根据澄清结果输出分步实施计划（含验收标准）：\n\n{{prev.text}}',
        },
      },
    },
    {
      id: approvalId,
      type: 'workflow',
      position: { x: 840, y: 200 },
      data: {
        type: 'skill',
        label: 'Plan Approval',
        subtitle: 'approval',
        config: {
          workflow_node_type: 'approval',
          title: '确认实施计划',
          description: '请审核计划后再继续执行',
        },
      },
    },
    {
      id: executeId,
      type: 'workflow',
      position: { x: 1040, y: 200 },
      data: {
        type: 'llm',
        label: 'Execute',
        subtitle: 'thorough',
        config: {
          model_tier: 'thorough',
          prompt: '按计划执行并输出 JSON，含 text 与 summary 字段。计划：{{prev.text}}',
          temperature: 0.3,
        },
      },
    },
    {
      id: cpId,
      type: 'workflow',
      position: { x: 1240, y: 200 },
      data: {
        type: 'checkpoint',
        label: 'Verify',
        config: {
          workflow_node_type: 'checkpoint',
          description: '执行结果须含 text、summary',
          required_keys: ['text', 'summary'],
          forbid_error_key: true,
        },
      },
    },
    {
      id: outputId,
      type: 'workflow',
      position: { x: 1440, y: 200 },
      data: {
        type: 'output',
        label: 'Deliverable',
        config: { output_key: 'deliverable', workflow_node_type: 'output' },
      },
    },
  ]
  const edges: Edge[] = [
    { id: newId('e'), source: 'start', target: inputId },
    { id: newId('e'), source: inputId, target: clarifyId },
    { id: newId('e'), source: clarifyId, target: planId },
    { id: newId('e'), source: planId, target: approvalId },
    { id: newId('e'), source: approvalId, target: executeId },
    { id: newId('e'), source: executeId, target: cpId },
    { id: newId('e'), source: cpId, target: outputId },
  ]
  return { nodes, edges }
}

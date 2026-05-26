/**
 * 工作流编辑器发布/保存前校验：Input/Output 节点配置
 * GAP P1-6：input_key 仅允许字符串；使用 expression 时 output_key 必填
 */
import type { Node } from '@vue-flow/core'
import type { Edge } from '@vue-flow/core'
import type { WorkflowNodeData } from './types'

export interface ValidationError {
  nodeId: string
  nodeLabel?: string
  message: string
  messageKey?: string
  messageParams?: Record<string, unknown>
}

const DEFAULT_INPUT_KEYS = new Set(['query', 'text', 'prompt', 'message'])

const WF_VARS_PREFIX = 'global.workflow_variables.'

/** 从 `${global.workflow_variables.foo}` 或 `${global.workflow_variables.foo.bar}` 取顶层键 foo */
function workflowVariableTopKeyFromToken(token: string): string | null {
  const t = token.trim()
  if (!t.startsWith(WF_VARS_PREFIX)) return null
  const rest = t.slice(WF_VARS_PREFIX.length).trim()
  if (!rest) return null
  const top = rest.split('.')[0]?.trim()
  return top || null
}

function extractVars(expr: string): string[] {
  const out: string[] = []
  const re = /\$\{([^}]+)\}/g
  let m: RegExpExecArray | null = null
  while ((m = re.exec(expr)) !== null) {
    const token = String(m[1] || '').trim()
    if (token) out.push(token)
  }
  return out
}

export function validateWorkflowNodes(
  nodes: Node<WorkflowNodeData>[]
): { valid: boolean; errors: ValidationError[] } {
  const errors: ValidationError[] = []

  for (const node of nodes) {
    const type = node.data?.type
    const config = (node.data?.config ?? {}) as Record<string, unknown>
    const label = node.data?.label ?? node.id

    if (type === 'input') {
      const inputKey = config.input_key
      if (inputKey !== undefined && inputKey !== null && inputKey !== '') {
        if (typeof inputKey !== 'string') {
          errors.push({
            nodeId: node.id,
            nodeLabel: label,
            message: 'Input 节点：input_key 仅允许字符串',
            messageKey: 'workflow_editor.input_key_string_only',
          })
        }
      }
      const fixedInput = config.fixed_input
      if (fixedInput !== undefined && fixedInput !== null) {
        if (typeof fixedInput !== 'object' || Array.isArray(fixedInput)) {
          errors.push({
            nodeId: node.id,
            nodeLabel: label,
            message: 'Input 节点：fixed_input 须为合法 JSON 对象',
            messageKey: 'workflow_editor.fixed_input_object_only',
          })
        }
      }
      const schema = config.input_schema
      if (schema !== undefined && schema !== null) {
        if (typeof schema !== 'object' || Array.isArray(schema)) {
          errors.push({
            nodeId: node.id,
            nodeLabel: label,
            message: 'Input 节点：input_schema 须为合法 JSON 对象',
            messageKey: 'workflow_editor.input_schema_object_only',
          })
        }
      }
    }

    if (type === 'output') {
      const expression = (config.expression as string)?.trim?.() ?? ''
      const outputKey = config.output_key
      const outputKeyStr =
        outputKey === undefined || outputKey === null ? '' : String(outputKey).trim()

      if (expression !== '' && outputKeyStr === '') {
        errors.push({
          nodeId: node.id,
          nodeLabel: label,
          message: 'Output 节点：使用 expression 时 output_key 必填',
          messageKey: 'workflow_editor.output_key_required_with_expression',
        })
      }
    }

    if (type === 'llm') {
      const modelId = String(config.model_id ?? '').trim()
      const legacyModel = String(config.model ?? '').trim()
      const tier = String(config.model_tier ?? '').trim().toLowerCase()
      const validTier = tier === 'low' || tier === 'standard' || tier === 'thorough'
      if (!modelId && !legacyModel && !validTier) {
        errors.push({
          nodeId: node.id,
          nodeLabel: label,
          message: 'LLM 节点：请选择模型或模型分档（low / standard / thorough）',
          messageKey: 'workflow_editor.llm_model_or_tier_required',
        })
      }
    }

    if (type === 'join') {
      const mode = String(config.dependency_mode ?? 'all').trim().toLowerCase()
      if (mode !== 'all' && mode !== 'any') {
        errors.push({
          nodeId: node.id,
          nodeLabel: label,
          message: 'Join 节点：dependency_mode 须为 all 或 any',
          messageKey: 'workflow_editor.join_dependency_mode_invalid',
        })
      }
    }

    if (type === 'verify_loop') {
      const keys = config.required_keys
      const hasKeys = Array.isArray(keys) && keys.length > 0
      let minFields = 0
      try {
        minFields = Number(config.min_nonempty_fields ?? 0)
      } catch {
        minFields = 0
      }
      const acc = config.acceptance
      if (typeof acc === 'object' && acc !== null && !Array.isArray(acc)) {
        const ak = (acc as Record<string, unknown>).required_keys
        if (Array.isArray(ak) && ak.length) {
          // ok
        } else {
          try {
            minFields = Math.max(minFields, Number((acc as Record<string, unknown>).min_nonempty_fields ?? 0))
          } catch {
            /* ignore */
          }
        }
      }
      if (!hasKeys && !(minFields > 0)) {
        errors.push({
          nodeId: node.id,
          nodeLabel: label,
          message: '验证环：须配置 required_keys 或 min_nonempty_fields',
          messageKey: 'workflow_editor.verify_loop_criteria_required',
        })
      }
      const body = config.loop_body
      if (!body || typeof body !== 'object' || Array.isArray(body)) {
        errors.push({
          nodeId: node.id,
          nodeLabel: label,
          message: '验证环：loop_body 须为对象',
          messageKey: 'workflow_editor.verify_loop_body_required',
        })
      }
    }

    if (type === 'checkpoint') {
      const keys = config.required_keys
      const hasKeys = Array.isArray(keys) && keys.length > 0
      let minFields = 0
      try {
        minFields = Number(config.min_nonempty_fields ?? 0)
      } catch {
        minFields = 0
      }
      if (!hasKeys && !(minFields > 0)) {
        errors.push({
          nodeId: node.id,
          nodeLabel: label,
          message: '验收节点：请配置 required_keys 或 min_nonempty_fields > 0',
          messageKey: 'workflow_editor.checkpoint_criteria_required',
        })
      }
      if (keys !== undefined && keys !== null && keys !== '' && !Array.isArray(keys)) {
        errors.push({
          nodeId: node.id,
          nodeLabel: label,
          message: '验收节点：required_keys 须为 JSON 数组',
          messageKey: 'workflow_editor.checkpoint_keys_array_required',
        })
      }
    }

    if (type === 'sub_workflow') {
      const wid = String(config.target_workflow_id ?? '').trim()
      if (!wid) {
        errors.push({
          nodeId: node.id,
          nodeLabel: label,
          message: 'Sub-workflow 节点：请填写目标工作流 ID（target_workflow_id）',
          messageKey: 'workflow_editor.subworkflow_target_required',
        })
      }
      const selector = String(config.target_version_selector ?? config.version_selector ?? 'fixed')
        .trim()
        .toLowerCase()
      if (selector === 'fixed') {
        const hasVer =
          String(config.target_version_id ?? '').trim() ||
          String(config.target_version ?? '').trim()
        if (!hasVer) {
          errors.push({
            nodeId: node.id,
            nodeLabel: label,
            message:
              'Sub-workflow（固定版本）：请填写 target_version_id 或语义化版本 target_version（如 1.0.0）',
            messageKey: 'workflow_editor.subworkflow_fixed_version_required',
          })
        }
      } else if (selector !== 'latest') {
        errors.push({
          nodeId: node.id,
          nodeLabel: label,
          message: `Sub-workflow：不支持的版本策略 "${selector}"，仅支持 fixed / latest`,
          messageKey: 'workflow_editor.subworkflow_selector_unsupported',
          messageParams: { selector },
        })
      }
      for (const key of ['input_mapping', 'output_mapping'] as const) {
        const raw = config[key]
        if (raw === undefined || raw === null || raw === '') continue
        if (typeof raw !== 'object' || Array.isArray(raw)) {
          errors.push({
            nodeId: node.id,
            nodeLabel: label,
            message: `Sub-workflow：${key} 须为 JSON 对象`,
            messageKey: 'workflow_editor.subworkflow_mapping_object_required',
            messageParams: { key },
          })
        }
      }
    }

    if (type === 'embedding') {
      const mid = String(config.model_id ?? '').trim()
      if (!mid) {
        errors.push({
          nodeId: node.id,
          nodeLabel: label,
          message: 'Embedding 节点：请选择或填写 model_id',
          messageKey: 'workflow_editor.embedding_model_required',
        })
      }
    }

    if (type === 'http_request') {
      const url = String(config.url ?? '').trim()
      if (!url) {
        errors.push({
          nodeId: node.id,
          nodeLabel: label,
          message: 'HTTP 节点：请填写 url',
          messageKey: 'workflow_editor.http_url_required',
        })
      }
    }

    if (type === 'variable') {
      const vars = config.variables
      if (vars !== undefined && vars !== null && (typeof vars !== 'object' || Array.isArray(vars))) {
        errors.push({
          nodeId: node.id,
          nodeLabel: label,
          message: 'Variable 节点：variables 须为 JSON 对象',
          messageKey: 'workflow_editor.variable_map_object_required',
        })
      }
    }

    if (type === 'python') {
      const fromUpstream = config.code_from_upstream === true
      if (!fromUpstream) {
        const code = String(config.code ?? '').trim()
        if (!code) {
          errors.push({
            nodeId: node.id,
            nodeLabel: label,
            message: 'Python 节点：请填写 code（走 python.run）',
            messageKey: 'workflow_editor.python_code_required',
          })
        }
      }
    }

    if (type === 'skill') {
      const skillWnt = String(config.workflow_node_type ?? '').trim().toLowerCase()
      if (skillWnt !== 'approval') {
        const tool = String(config.tool_name ?? config.tool_id ?? '').trim()
        if (!tool) {
          errors.push({
            nodeId: node.id,
            nodeLabel: label,
            message: 'Skill 节点：请选择或填写工具（tool_name）',
            messageKey: 'workflow_editor.skill_tool_name_required',
          })
        }
      }
    }

    if (type === 'shell') {
      const command = String(config.command ?? '').trim()
      if (!command) {
        errors.push({
          nodeId: node.id,
          nodeLabel: label,
          message: 'Shell 节点：请填写 command',
          messageKey: 'workflow_editor.shell_command_required',
        })
      }
    }

    if (type === 'loop') {
      const lb = config.loop_body
      if (!lb || typeof lb !== 'object' || Array.isArray(lb)) {
        errors.push({
          nodeId: node.id,
          nodeLabel: label,
          message: 'Loop 节点：loop_body 须为对象（单次迭代执行的配置）',
          messageKey: 'workflow_editor.loop_body_object_required',
        })
      } else {
        const body = lb as Record<string, unknown>
        const bodyType = String(body.type ?? 'tool').trim().toLowerCase()
        if (bodyType === 'tool') {
          const tn = String(body.tool_name ?? body.tool_id ?? '').trim()
          if (!tn) {
            errors.push({
              nodeId: node.id,
              nodeLabel: label,
              message: 'Loop 节点：loop_body.type 为 tool 时需填写 tool_name',
              messageKey: 'workflow_editor.loop_body_tool_name_required',
            })
          }
        } else if (['agent', 'manager', 'worker', 'reflector'].includes(bodyType)) {
          const aid = String(body.agent_id ?? '').trim()
          if (!aid) {
            errors.push({
              nodeId: node.id,
              nodeLabel: label,
              message: `Loop 节点：loop_body 为 ${bodyType} 时需填写 agent_id`,
              messageKey: 'workflow_editor.loop_body_agent_required',
              messageParams: { role: bodyType },
            })
          }
        }
      }
    }
  }

  return {
    valid: errors.length === 0,
    errors,
  }
}

export function validateWorkflowPreflight(
  nodes: Node<WorkflowNodeData>[],
  edges: Edge[],
): { valid: boolean; errors: ValidationError[] } {
  const errors: ValidationError[] = []
  const nodeById = new Map(nodes.map((n) => [n.id, n]))

  const inputFixedInputKeySet = new Set<string>(DEFAULT_INPUT_KEYS)
  let inputQueryDefault: unknown = undefined
  const declaredWorkflowVariableKeys = new Set<string>()
  for (const node of nodes) {
    if (node.data?.type === 'variable') {
      const cfg = (node.data?.config ?? {}) as Record<string, unknown>
      const vars = cfg.variables
      if (vars && typeof vars === 'object' && !Array.isArray(vars)) {
        for (const k of Object.keys(vars as Record<string, unknown>)) {
          const key = String(k).trim()
          if (key) declaredWorkflowVariableKeys.add(key)
        }
      }
      continue
    }
    if (node.data?.type !== 'input') continue
    const cfg = (node.data?.config ?? {}) as Record<string, unknown>
    const fixed = cfg.fixed_input
    if (fixed && typeof fixed === 'object' && !Array.isArray(fixed)) {
      for (const k of Object.keys(fixed as Record<string, unknown>)) inputFixedInputKeySet.add(k)
      if (inputQueryDefault === undefined && Object.prototype.hasOwnProperty.call(fixed, 'query')) {
        inputQueryDefault = (fixed as Record<string, unknown>).query
      }
    }
  }

  for (const node of nodes) {
    if (node.data?.type !== 'condition') continue
    const label = node.data?.label ?? node.id
    const cfg = (node.data?.config ?? {}) as Record<string, unknown>
    const expr = String(cfg.condition_expression ?? '').trim()
    if (!expr) {
      errors.push({
        nodeId: node.id,
        nodeLabel: label,
        message: 'Condition 节点：condition_expression 为空，请填写条件表达式',
        messageKey: 'workflow_editor.condition_expression_required',
      })
      continue
    }

    const vars = extractVars(expr)
    for (const v of vars) {
      if (v.startsWith('input.')) {
        const key = v.slice('input.'.length).split('.')[0]
        if (key && !inputFixedInputKeySet.has(key)) {
          errors.push({
            nodeId: node.id,
            nodeLabel: label,
            message: `Condition 变量不存在：\${${v}}。当前 Input 未提供该字段（可用: ${Array.from(inputFixedInputKeySet).join(', ')})`,
            messageKey: 'workflow_editor.condition_variable_missing',
            messageParams: { variable: v, available: Array.from(inputFixedInputKeySet).join(', ') },
          })
        }
      } else if (v.startsWith('nodes.')) {
        const parts = v.split('.')
        const refNodeId = parts[1]
        if (!refNodeId || !nodeById.has(refNodeId)) {
          errors.push({
            nodeId: node.id,
            nodeLabel: label,
            message: `Condition 引用了不存在的节点变量：\${${v}}`,
            messageKey: 'workflow_editor.condition_node_reference_missing',
            messageParams: { variable: v },
          })
        }
      } else {
        const wfTop = workflowVariableTopKeyFromToken(v)
        if (
          wfTop &&
          declaredWorkflowVariableKeys.size > 0 &&
          !declaredWorkflowVariableKeys.has(wfTop)
        ) {
          errors.push({
            nodeId: node.id,
            nodeLabel: label,
            message: `Condition 变量不存在：\${${v}}。当前 Variable 节点未声明 workflow_variables.${wfTop}（已声明: ${Array.from(declaredWorkflowVariableKeys).join(', ')}）`,
            messageKey: 'workflow_editor.condition_workflow_variable_missing',
            messageParams: {
              variable: v,
              key: wfTop,
              available: Array.from(declaredWorkflowVariableKeys).join(', '),
            },
          })
        }
      }
    }

    if (
      (expr.includes('${input.query}') || expr.includes('${global.input_data.query}')) &&
      (inputQueryDefault === '' || inputQueryDefault === null)
    ) {
      errors.push({
        nodeId: node.id,
        nodeLabel: label,
        message: 'Condition 可能恒为 false：query 默认值为空，请检查 Input.fixed_input.query 或执行入参 input_data.query',
        messageKey: 'workflow_editor.condition_query_maybe_always_false',
      })
    }
  }

  // 检查 Condition 出边 true/false 是否都存在（编辑器内快速预检）
  for (const node of nodes) {
    if (node.data?.type !== 'condition') continue
    const label = node.data?.label ?? node.id
    const out = edges.filter((e) => e.source === node.id)
    const triggerSet = new Set(out.map((e) => String(e.sourceHandle || e.label || '').toLowerCase()))
    const hasTrue = triggerSet.has('true') || triggerSet.has('condition_true')
    const hasFalse = triggerSet.has('false') || triggerSet.has('condition_false')
    if (!hasTrue || !hasFalse) {
      errors.push({
        nodeId: node.id,
        nodeLabel: label,
        message: 'Condition 分支不完整：需要同时配置 true 与 false 两条出边',
        messageKey: 'workflow_editor.condition_branch_incomplete',
      })
    }
  }

  return { valid: errors.length === 0, errors }
}

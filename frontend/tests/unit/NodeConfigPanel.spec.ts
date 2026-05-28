import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { describe, expect, it, vi } from 'vitest'
import NodeConfigPanel from '@/components/workflow/editor/NodeConfigPanel.vue'

vi.mock('@/services/api', () => ({
  listWorkflows: vi.fn(async () => ({
    items: [],
    total: 0,
    limit: 500,
    offset: 0,
  })),
  listWorkflowVersions: vi.fn(async () => ({
    items: [],
    total: 0,
    limit: 200,
    offset: 0,
  })),
  getWorkflowVersion: vi.fn(async () => ({
    version_id: 'v1',
    workflow_id: 'wf1',
    version_number: '1.0.0',
    state: 'published',
    created_at: '',
    dag: { nodes: [], edges: [] },
  })),
  listModels: vi.fn(async () => ({
    data: [
      { id: 'qwen-7b', name: 'qwen-7b', display_name: 'Qwen 7B', backend: 'ollama', model_type: 'llm' },
      { id: 'llama-3.1', name: 'llama-3.1', display_name: 'Llama 3.1', backend: 'llama.cpp', model_type: 'llm' },
      { id: 'embed-1', name: 'embed-1', display_name: 'Embed 1', backend: 'ollama', model_type: 'embedding' },
    ],
  })),
  listAgents: vi.fn(async () => ({
    data: [
      { agent_id: 'planner-agent', name: 'Planner Agent' },
      { agent_id: 'reporter-agent', name: 'Reporter Agent' },
    ],
  })),
  listTools: vi.fn(async () => ({
    data: [
      { name: 'web.search', ui: { display_name: 'Web Search' }, input_schema: {} },
      { name: 'python.exec', ui: { display_name: 'Python Exec' }, input_schema: {} },
    ],
  })),
}))

function makeI18n() {
  return createI18n({
    legacy: false,
    locale: 'zh',
    messages: {
      zh: {
        workflow_editor: {
          subworkflow_target_required: '请选择或填写目标工作流 ID（target_workflow_id）',
          subworkflow_fixed_version_required: '固定版本策略下，请选择版本或填写 target_version_id / target_version',
          config_validation: '配置校验',
          llm_model_tier: '模型分档',
          llm_model_tier_none: '不指定分档',
          llm_model_tier_low: '低',
          llm_model_tier_standard: '标准',
          llm_model_tier_thorough: '深入',
          llm_model_tier_hint: '分档提示',
          search_models_placeholder: '搜索模型',
          llm_model_placeholder: '选择模型',
          llm_models_loading: '加载中',
        },
      },
    },
    missingWarn: false,
    fallbackWarn: false,
  })
}

function llmModelSelect(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAll('select').find((s) => s.html().includes('qwen-7b')) ?? null
}

describe('NodeConfigPanel searchable selectors', () => {
  it('filters llm model options by keyword', async () => {
    const wrapper = mount(NodeConfigPanel, {
      props: {
        node: {
          id: 'n-1',
          data: { type: 'llm', label: 'LLM', config: {} },
        } as any,
        selectedNodeId: 'n-1',
        nodes: [{ id: 'n-1', data: { type: 'llm', label: 'LLM', config: {} } }] as any,
      },
      global: { plugins: [makeI18n()] },
    })

    await flushPromises()
    const modelSelect = llmModelSelect(wrapper)
    expect(modelSelect).toBeTruthy()
    expect(modelSelect!.text()).toContain('Qwen 7B')
    expect(modelSelect!.text()).toContain('Llama 3.1')

    const searchInput = wrapper.find('input[placeholder="搜索模型"]')
    await searchInput.setValue('qwen')
    await flushPromises()

    expect(modelSelect!.text()).toContain('Qwen 7B')
    expect(modelSelect!.text()).not.toContain('Llama 3.1')
  })

  it('filters tool options by keyword', async () => {
    const wrapper = mount(NodeConfigPanel, {
      props: {
        node: {
          id: 'n-2',
          data: { type: 'skill', label: 'Tool', config: {} },
        } as any,
        selectedNodeId: 'n-2',
        nodes: [{ id: 'n-2', data: { type: 'skill', label: 'Tool', config: {} } }] as any,
      },
      global: { plugins: [makeI18n()] },
    })

    await flushPromises()
    const selects = wrapper.findAll('select')
    expect(selects[0].text()).toContain('Web Search')
    expect(selects[0].text()).toContain('Python Exec')

    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('python')
    await flushPromises()

    expect(selects[0].text()).not.toContain('Web Search')
    expect(selects[0].text()).toContain('Python Exec')
  })

  it('filters agent options by keyword', async () => {
    const wrapper = mount(NodeConfigPanel, {
      props: {
        node: {
          id: 'n-3',
          data: { type: 'agent', label: 'Agent', config: {} },
        } as any,
        selectedNodeId: 'n-3',
        nodes: [{ id: 'n-3', data: { type: 'agent', label: 'Agent', config: {} } }] as any,
      },
      global: { plugins: [makeI18n()] },
    })

    await flushPromises()
    const selects = wrapper.findAll('select')
    expect(selects[0].text()).toContain('Planner Agent')
    expect(selects[0].text()).toContain('Reporter Agent')

    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('planner')
    await flushPromises()

    expect(selects[0].text()).toContain('Planner Agent')
    expect(selects[0].text()).not.toContain('Reporter Agent')
  })

  it('emits normalized model config when selecting model', async () => {
    const wrapper = mount(NodeConfigPanel, {
      props: {
        node: {
          id: 'n-4',
          data: { type: 'llm', label: 'LLM', config: {} },
        } as any,
        selectedNodeId: 'n-4',
        nodes: [{ id: 'n-4', data: { type: 'llm', label: 'LLM', config: {} } }] as any,
      },
      global: { plugins: [makeI18n()] },
    })

    await flushPromises()
    const modelSelect = llmModelSelect(wrapper)
    expect(modelSelect).toBeTruthy()
    await modelSelect!.setValue('qwen-7b')
    await flushPromises()

    const events = wrapper.emitted('update:config')
    expect(events).toBeTruthy()
    const modelEvent = events?.find((e) => (e[1] as Record<string, unknown>)?.model_id === 'qwen-7b')
    expect(modelEvent?.[0]).toBe('n-4')
    expect(modelEvent?.[1]).toMatchObject({
      model_id: 'qwen-7b',
      model_display_name: 'Qwen 7B',
      model_tier: undefined,
      model: undefined,
    })
  })

  it('emits agent config when selecting agent', async () => {
    const wrapper = mount(NodeConfigPanel, {
      props: {
        node: {
          id: 'n-5',
          data: { type: 'agent', label: 'Agent', config: {} },
        } as any,
        selectedNodeId: 'n-5',
        nodes: [{ id: 'n-5', data: { type: 'agent', label: 'Agent', config: {} } }] as any,
      },
      global: { plugins: [makeI18n()] },
    })

    await flushPromises()
    const agentSelect = wrapper.find('select')
    await agentSelect.setValue('planner-agent')
    await flushPromises()

    const events = wrapper.emitted('update:config')
    expect(events).toBeTruthy()
    const payload = events?.at(-1)
    expect(payload?.[0]).toBe('n-5')
    expect(payload?.[1]).toMatchObject({
      agent_id: 'planner-agent',
      agent_display_name: 'Planner Agent',
    })
  })

  it('emits tool config when selecting tool', async () => {
    const wrapper = mount(NodeConfigPanel, {
      props: {
        node: {
          id: 'n-6',
          data: { type: 'skill', label: 'Tool', config: {} },
        } as any,
        selectedNodeId: 'n-6',
        nodes: [{ id: 'n-6', data: { type: 'skill', label: 'Tool', config: {} } }] as any,
      },
      global: { plugins: [makeI18n()] },
    })

    await flushPromises()
    const toolSelect = wrapper.find('select')
    await toolSelect.setValue('web.search')
    await flushPromises()

    const events = wrapper.emitted('update:config')
    expect(events).toBeTruthy()
    const payload = events?.at(-1)
    expect(payload?.[0]).toBe('n-6')
    expect(payload?.[1]).toMatchObject({
      tool_name: 'web.search',
      tool_id: 'web.search',
      tool_display_name: 'Web Search',
    })
  })

  it('shows sub_workflow config validation warnings', async () => {
    const wrapper = mount(NodeConfigPanel, {
      props: {
        node: {
          id: 'n-7',
          data: {
            type: 'sub_workflow',
            label: 'Sub-workflow',
            config: { target_version_selector: 'fixed' },
          },
        } as any,
        selectedNodeId: 'n-7',
        nodes: [
          {
            id: 'n-7',
            data: {
              type: 'sub_workflow',
              label: 'Sub-workflow',
              config: { target_version_selector: 'fixed' },
            },
          },
        ] as any,
      },
      global: { plugins: [makeI18n()] },
    })

    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('请选择或填写目标工作流 ID')
    expect(text).toContain('固定版本策略下')
  })
})

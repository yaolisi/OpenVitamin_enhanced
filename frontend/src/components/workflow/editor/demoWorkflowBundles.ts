import type { Edge, Node } from '@vue-flow/core'
import type { WorkflowDagPayload } from '@/services/api'
import demo1Bundle from '../../../../../demos/workflows/demo1-release-brief-gate.bundle.json'
import demo2Bundle from '../../../../../demos/workflows/demo2-parallel-research-verify.bundle.json'
import { fromWorkflowDag } from './serialization'
import type { WorkflowNodeData } from './types'

export interface DemoWorkflowBundle {
  schema_version: number
  demo_id: string
  name: string
  description: string
  workflow_name: string
  tags?: string[]
  agent_placeholders?: Record<
    string,
    { node_id: string; display_name: string; hint?: string }
  >
  dag: WorkflowDagPayload
  sample_input?: Record<string, unknown>
}

const BUNDLES: DemoWorkflowBundle[] = [
  demo1Bundle as DemoWorkflowBundle,
  demo2Bundle as DemoWorkflowBundle,
]

export function listDemoWorkflowBundles(): Pick<
  DemoWorkflowBundle,
  'demo_id' | 'name' | 'description'
>[] {
  return BUNDLES.map(({ demo_id, name, description }) => ({
    demo_id,
    name,
    description,
  }))
}

export function getDemoWorkflowBundle(demoId: string): DemoWorkflowBundle | undefined {
  return BUNDLES.find((b) => b.demo_id === demoId)
}

export function buildDemoWorkflowGraph(demoId: string): {
  workflowName: string
  tags: string[]
  nodes: Node<WorkflowNodeData>[]
  edges: Edge[]
  sampleInput: Record<string, unknown>
} | null {
  const bundle = getDemoWorkflowBundle(demoId)
  if (!bundle) return null
  const { nodes, edges } = fromWorkflowDag(bundle.dag)
  return {
    workflowName: bundle.workflow_name,
    tags: bundle.tags ?? ['demo'],
    nodes,
    edges,
    sampleInput: (bundle.sample_input as Record<string, unknown>) ?? {},
  }
}

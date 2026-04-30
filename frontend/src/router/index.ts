import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { i18n } from '@/i18n'

// 路由配置
const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/chat'
  },
  {
    path: '/chat',
    name: 'chat',
    component: () => import('@/views/ChatView.vue'),
    meta: {
      title: 'Chat'
    }
  },
  {
    path: '/workflow',
    name: 'workflow',
    component: () => import('@/views/WorkflowView.vue'),
    meta: {
      title: 'Workflow'
    }
  },
  {
    path: '/workflow/create',
    name: 'workflow-create',
    component: () => import('@/components/workflow/CreateWorkflowView.vue'),
    meta: {
      title: 'Create Workflow'
    }
  },
  {
    path: '/workflow/:id',
    name: 'workflow-detail',
    component: () => import('@/components/workflow/WorkflowDetailView.vue'),
    meta: {
      title: 'Workflow Detail'
    }
  },
  {
    path: '/workflow/:id/edit',
    name: 'workflow-edit',
    component: () => import('@/components/workflow/EditWorkflowView.vue'),
    meta: {
      title: 'Edit Workflow'
    }
  },
  {
    path: '/workflow/:id/run',
    name: 'workflow-run',
    component: () => import('@/components/workflow/WorkflowExecutionView.vue'),
    meta: {
      title: 'Run Workflow'
    }
  },
  {
    path: '/workflow/:id/versions',
    name: 'workflow-versions',
    component: () => import('@/components/workflow/WorkflowVersionsView.vue'),
    meta: {
      title: 'Workflow Versions'
    }
  },
  {
    path: '/images',
    name: 'images',
    component: () => import('@/views/ImageGenerationView.vue'),
    meta: {
      title: 'Image Generation'
    }
  },
  {
    path: '/images/history',
    name: 'images-history',
    component: () => import('@/views/ImageGenerationHistoryView.vue'),
    meta: {
      title: 'Image Generation History'
    }
  },
  {
    path: '/images/jobs/:jobId',
    name: 'images-job-detail',
    component: () => import('@/views/ImageGenerationView.vue'),
    meta: {
      title: 'Image Generation Job'
    }
  },
  {
    path: '/models',
    name: 'models',
    component: () => import('@/views/ModelsView.vue'),
    meta: {
      title: 'Models'
    }
  },
  {
    path: '/models/llm',
    name: 'models-llm',
    component: () => import('@/views/ModelsView.vue'),
    meta: {
      title: 'Models',
      capability: 'llm'
    }
  },
  {
    path: '/models/vlm',
    name: 'models-vlm',
    component: () => import('@/views/ModelsView.vue'),
    meta: {
      title: 'Models',
      capability: 'vlm'
    }
  },
  {
    path: '/models/asr',
    name: 'models-asr',
    component: () => import('@/views/ModelsView.vue'),
    meta: {
      title: 'Models',
      capability: 'asr'
    }
  },
  {
    path: '/models/perception',
    name: 'models-perception',
    component: () => import('@/views/ModelsView.vue'),
    meta: {
      title: 'Models',
      capability: 'perception'
    }
  },
  {
    path: '/models/perception/object-detection',
    name: 'models-perception-detection',
    component: () => import('@/views/ModelsView.vue'),
    meta: {
      title: 'Models',
      capability: 'perception',
      subtype: 'object-detection'
    }
  },
  {
    path: '/models/perception/segmentation',
    name: 'models-perception-segmentation',
    component: () => import('@/views/ModelsView.vue'),
    meta: {
      title: 'Models',
      capability: 'perception',
      subtype: 'segmentation'
    }
  },
  {
    path: '/models/perception/tracking',
    name: 'models-perception-tracking',
    component: () => import('@/views/ModelsView.vue'),
    meta: {
      title: 'Models',
      capability: 'perception',
      subtype: 'tracking'
    }
  },
  {
    path: '/models/embedding',
    name: 'models-embedding',
    component: () => import('@/views/ModelsView.vue'),
    meta: {
      title: 'Models',
      capability: 'embedding'
    }
  },
  {
    path: '/models/image-generation',
    name: 'models-image-generation',
    component: () => import('@/views/ModelsView.vue'),
    meta: {
      title: 'Models',
      capability: 'image_generation'
    }
  },
  {
    path: '/models/:id/config',
    name: 'model-config',
    component: () => import('@/components/models/ModelConfigView.vue'),
    meta: {
      title: 'Model Config'
    }
  },
  {
    path: '/knowledge',
    name: 'knowledge',
    component: () => import('@/views/KnowledgeView.vue'),
    meta: {
      title: 'Knowledge Base'
    }
  },
  {
    path: '/knowledge/create',
    name: 'knowledge-create',
    component: () => import('@/components/knowledge/CreateKnowledgeBaseView.vue'),
    meta: {
      title: 'Create Knowledge Base'
    }
  },
  {
    path: '/knowledge/:id',
    name: 'knowledge-detail',
    component: () => import('@/components/knowledge/KnowledgeBaseDetailView.vue'),
    meta: {
      title: 'Knowledge Base Detail'
    }
  },
  {
    path: '/agents',
    name: 'agents',
    component: () => import('@/views/AgentsView.vue'),
    meta: {
      title: 'Agents'
    }
  },
  {
    path: '/agents/create',
    name: 'agents-create',
    component: () => import('@/components/agents/CreateAgentView.vue'),
    meta: {
      title: 'Create Agent'
    }
  },
  {
    path: '/agents/:id/run',
    name: 'agents-run',
    component: () => import('@/components/agents/AgentExecutionView.vue'),
    meta: {
      title: 'Agent Execution'
    }
  },
  {
    path: '/agents/:id/trace',
    name: 'agents-trace',
    component: () => import('@/components/agents/AgentExecutionTraceView.vue'),
    meta: {
      title: 'Agent Execution Trace'
    }
  },
  {
    path: '/agents/:id/edit',
    name: 'agents-edit',
    component: () => import('@/components/agents/EditAgentView.vue'),
    meta: {
      title: 'Edit Agent'
    }
  },
  {
    path: '/skills',
    name: 'skills',
    component: () => import('@/views/SkillsView.vue'),
    meta: {
      title: 'Skills'
    }
  },
  {
    path: '/skills/create',
    name: 'skills-create',
    component: () => import('@/components/skills/CreateSkillView.vue'),
    meta: {
      title: 'Create Skill'
    }
  },
  {
    path: '/skills/:id',
    name: 'skill-detail',
    component: () => import('@/components/skills/SkillDetailView.vue'),
    meta: {
      title: 'Skill Detail'
    }
  },
  {
    path: '/logs',
    name: 'logs',
    component: () => import('@/views/LogsView.vue'),
    meta: {
      title: 'Logs'
    }
  },
  {
    path: '/settings',
    name: 'settings',
    redirect: '/settings/general',
    meta: {
      title: 'Settings'
    }
  },
  {
    path: '/settings/general',
    name: 'settings-general',
    component: () => import('@/views/SettingsGeneralView.vue'),
    meta: {
      title: 'General Settings'
    }
  },
  {
    path: '/settings/backend',
    name: 'settings-backend',
    component: () => import('@/views/SettingsBackendView.vue'),
    meta: {
      title: 'Backend Configuration'
    }
  },
  {
    path: '/settings/object-detection',
    name: 'settings-object-detection',
    component: () => import('@/views/SettingsObjectDetectionView.vue'),
    meta: {
      title: 'Object Detection (YOLO)'
    }
  },
  {
    path: '/settings/image-generation',
    name: 'settings-image-generation',
    component: () => import('@/views/SettingsImageGenerationView.vue'),
    meta: {
      title: 'Image Generation'
    }
  },
  {
    path: '/settings/asr',
    name: 'settings-asr',
    component: () => import('@/views/SettingsAsrView.vue'),
    meta: {
      title: 'ASR Configuration'
    }
  },
  {
    path: '/settings/backup',
    name: 'settings-backup',
    component: () => import('@/views/SettingsBackupView.vue'),
    meta: {
      title: 'Database Backup'
    }
  },
  {
    path: '/settings/model-backup',
    name: 'settings-model-backup',
    component: () => import('@/views/SettingsModelBackupView.vue'),
    meta: {
      title: 'Model Config Backup'
    }
  },
  {
    path: '/settings/runtime',
    name: 'settings-runtime',
    component: () => import('@/views/SettingsRuntimeView.vue'),
    meta: {
      title: 'Runtime Configuration'
    }
  },
  {
    path: '/settings/mcp',
    name: 'settings-mcp',
    component: () => import('@/views/SettingsMcpView.vue'),
    meta: {
      title: 'MCP Servers'
    }
  },
  {
    path: '/optimization',
    name: 'optimization',
    component: () => import('@/views/OptimizationDashboard.vue'),
    meta: {
      title: 'Optimization Dashboard'
    }
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/chat'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

const routeTitleKeyMap: Record<string, string> = {
  chat: 'router.chat',
  workflow: 'router.workflow',
  'workflow-create': 'router.workflow_create',
  'workflow-detail': 'router.workflow_detail',
  'workflow-edit': 'router.workflow_edit',
  'workflow-run': 'router.workflow_run',
  'workflow-versions': 'router.workflow_versions',
  images: 'router.images',
  'images-history': 'router.images_history',
  'images-job-detail': 'router.images_job_detail',
  models: 'router.models',
  'models-llm': 'router.models',
  'models-vlm': 'router.models',
  'models-asr': 'router.models',
  'models-perception': 'router.models',
  'models-perception-detection': 'router.models',
  'models-perception-segmentation': 'router.models',
  'models-perception-tracking': 'router.models',
  'models-embedding': 'router.models',
  'models-image-generation': 'router.models',
  'model-config': 'router.model_config',
  knowledge: 'router.knowledge',
  'knowledge-create': 'router.knowledge_create',
  'knowledge-detail': 'router.knowledge_detail',
  agents: 'router.agents',
  'agents-create': 'router.agents_create',
  'agents-run': 'router.agents_run',
  'agents-trace': 'router.agents_trace',
  'agents-edit': 'router.agents_edit',
  skills: 'router.skills',
  'skills-create': 'router.skills_create',
  'skill-detail': 'router.skill_detail',
  logs: 'router.logs',
  settings: 'router.settings',
  'settings-general': 'router.settings_general',
  'settings-backend': 'router.settings_backend',
  'settings-object-detection': 'router.settings_object_detection',
  'settings-image-generation': 'router.settings_image_generation',
  'settings-asr': 'router.settings_asr',
  'settings-backup': 'router.settings_backup',
  'settings-model-backup': 'router.settings_model_backup',
  'settings-runtime': 'router.settings_runtime',
  'settings-mcp': 'router.settings_mcp',
  optimization: 'router.optimization',
}

// 路由守卫：确保路由正确导航
router.beforeEach((to, from, next) => {
  // 记录路由变化，便于调试
  console.log('[Router] Navigating from', from.path, 'to', to.path)
  next()
})

router.afterEach((to) => {
  const routeName = typeof to.name === 'string' ? to.name : ''
  const titleKey = routeTitleKeyMap[routeName]
  const routeTitle = titleKey ? i18n.global.t(titleKey) : String(to.meta.title ?? '')
  const appTitle = i18n.global.t('app.title')
  document.title = routeTitle ? `${routeTitle} - ${appTitle}` : appTitle
})

export default router

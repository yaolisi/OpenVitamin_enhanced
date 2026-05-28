<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Bot, ChevronLeft, ChevronRight, Check, Loader2, Sparkles, X } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import {
  createAgent,
  generateAgentFromNl,
  listModels,
  listSkills,
  type CreateAgentRequest,
  type GenerateAgentFromNlResponse,
  type ModelInfo,
  type SkillRecord,
} from '@/services/api'
import { formatAgentMutationErrorMessage } from '@/utils/agentMutationMessages'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  created: [agentId: string]
}>()

const router = useRouter()
const { t } = useI18n()

const step = ref(0)
const entryMode = ref<'template' | 'nl'>('template')
const nlDescription = ref('')
const nlBusy = ref(false)
const nlDraft = ref<GenerateAgentFromNlResponse | null>(null)
const submitting = ref(false)
const submitError = ref<string | null>(null)
const models = ref<ModelInfo[]>([])
const skills = ref<SkillRecord[]>([])
const loadingMeta = ref(false)

type TemplateId = 'research' | 'writer' | 'ops'

const templateId = ref<TemplateId>('research')
const name = ref('')
const description = ref('')
const modelId = ref('')
const selectedSkillIds = ref<string[]>([])

const templates: { id: TemplateId; titleKey: string; descKey: string }[] = [
  { id: 'research', titleKey: 'agents.wizard.tpl_research', descKey: 'agents.wizard.tpl_research_desc' },
  { id: 'writer', titleKey: 'agents.wizard.tpl_writer', descKey: 'agents.wizard.tpl_writer_desc' },
  { id: 'ops', titleKey: 'agents.wizard.tpl_ops', descKey: 'agents.wizard.tpl_ops_desc' },
]

const templateDefaults: Record<
  TemplateId,
  { name: string; description: string; systemPrompt: string; skillHints: string[]; executionMode: string }
> = {
  research: {
    name: '研究助手',
    description: '检索资料、归纳要点并给出可引用结论',
    systemPrompt: '你是研究型助手：先澄清问题，再分步检索与归纳，标注不确定性。',
    skillHints: ['web', 'search', 'file'],
    executionMode: 'plan_based',
  },
  writer: {
    name: '文稿助手',
    description: '根据要点生成结构化文稿与修订建议',
    systemPrompt: '你是文稿助手：输出结构清晰、语气一致，必要时列出待确认项。',
    skillHints: ['file', 'content'],
    executionMode: 'legacy',
  },
  ops: {
    name: '运维助手',
    description: '解读日志与指标，给出可执行排查步骤',
    systemPrompt: '你是运维助手：结论须可验证，避免臆测根因，列出下一步检查项。',
    skillHints: ['terminal', 'metrics', 'audit'],
    executionMode: 'plan_based',
  },
}

function close() {
  emit('update:open', false)
}

function applyTemplate() {
  const tpl = templateDefaults[templateId.value]
  if (!name.value.trim()) name.value = tpl.name
  if (!description.value.trim()) description.value = tpl.description
  const hints = tpl.skillHints
  selectedSkillIds.value = skills.value
    .filter((s) => {
      const blob = `${s.id} ${s.name}`.toLowerCase()
      return hints.some((h) => blob.includes(h))
    })
    .slice(0, 6)
    .map((s) => s.id)
}

watch(
  () => props.open,
  (v) => {
    if (v) {
      step.value = 0
      entryMode.value = 'template'
      nlDescription.value = ''
      nlDraft.value = null
      submitError.value = null
      templateId.value = 'research'
      name.value = ''
      description.value = ''
      modelId.value = models.value[0]?.id || ''
      selectedSkillIds.value = []
      void loadMeta()
    }
  },
)

async function loadMeta() {
  loadingMeta.value = true
  try {
    const [mRes, sRes] = await Promise.all([listModels(), listSkills()])
    models.value = mRes.data || []
    skills.value = sRes.data || []
    const firstModel = models.value[0]
    if (!modelId.value && firstModel?.id) {
      modelId.value = firstModel.id
    }
  } catch {
    models.value = []
    skills.value = []
  } finally {
    loadingMeta.value = false
  }
}

onMounted(() => {
  if (props.open) void loadMeta()
})

const canNext = computed(() => {
  if (step.value === 0) return true
  if (step.value === 1) return name.value.trim().length > 0 && !!modelId.value
  if (step.value === 2) return true
  return true
})

async function runNlGenerate() {
  const q = nlDescription.value.trim()
  if (q.length < 4) {
    submitError.value = t('agents.nl.err_short')
    return
  }
  nlBusy.value = true
  submitError.value = null
  try {
    nlDraft.value = await generateAgentFromNl({
      description: q,
      model_id: modelId.value || undefined,
    })
    const d = nlDraft.value.draft
    name.value = d.name || name.value
    description.value = d.description || description.value
    if (d.model_id) modelId.value = d.model_id
    if (d.enabled_skills?.length) selectedSkillIds.value = d.enabled_skills
    entryMode.value = 'template'
    step.value = 1
  } catch (e) {
    submitError.value = formatAgentMutationErrorMessage(e, t) || t('agents.create.create_failed')
  } finally {
    nlBusy.value = false
  }
}

function nextStep() {
  if (step.value === 0 && entryMode.value === 'template') applyTemplate()
  if (step.value < 3 && canNext.value) step.value += 1
}

function prevStep() {
  if (step.value > 0) step.value -= 1
}

function toggleSkill(id: string) {
  const set = new Set(selectedSkillIds.value)
  if (set.has(id)) set.delete(id)
  else set.add(id)
  selectedSkillIds.value = Array.from(set)
}

async function submit() {
  submitError.value = null
  if (!name.value.trim() || !modelId.value) {
    submitError.value = t('agents.wizard.err_required')
    return
  }
  const tpl = templateDefaults[templateId.value]
  const payload: CreateAgentRequest = {
    name: name.value.trim(),
    description: description.value.trim(),
    model_id: modelId.value,
    system_prompt: tpl.systemPrompt,
    enabled_skills: selectedSkillIds.value,
    execution_mode: tpl.executionMode,
    max_steps: tpl.executionMode === 'plan_based' ? 12 : 8,
    temperature: 0.3,
  }
  submitting.value = true
  try {
    const agent = await createAgent(payload)
    const id = (agent.agent_id || '').trim()
    emit('created', id)
    close()
    if (id) router.push(`/agents/${id}/run`)
    else router.push('/agents')
  } catch (e) {
    submitError.value = formatAgentMutationErrorMessage(e, t) || t('agents.create.create_failed')
  } finally {
    submitting.value = false
  }
}

function openAdvanced() {
  close()
  router.push('/agents/create')
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      @click.self="close"
    >
      <div
        class="bg-card border border-border rounded-2xl shadow-2xl max-w-xl w-full max-h-[90vh] flex flex-col overflow-hidden"
        @click.stop
      >
        <div class="px-6 pt-6 pb-4 border-b border-border shrink-0 flex items-start justify-between gap-4">
          <div>
            <h2 class="text-xl font-bold text-foreground flex items-center gap-2">
              <Sparkles class="w-5 h-5 text-indigo-500" />
              {{ t('agents.wizard.title') }}
            </h2>
            <p class="text-sm text-muted-foreground mt-1">{{ t('agents.wizard.subtitle') }}</p>
            <div class="flex gap-2 mt-3">
              <Badge
                v-for="i in 4"
                :key="i"
                :variant="step === i - 1 ? 'default' : 'outline'"
                class="text-[10px]"
              >
                {{ t(`agents.wizard.step_${i}`) }}
              </Badge>
            </div>
          </div>
          <Button variant="ghost" size="icon" class="shrink-0" @click="close">
            <X class="w-4 h-4" />
          </Button>
        </div>

        <div class="flex-1 min-h-0 overflow-y-auto px-6 py-4 space-y-4">
          <div v-if="step === 0" class="space-y-3">
            <div class="flex gap-2">
              <Button
                size="sm"
                :variant="entryMode === 'template' ? 'default' : 'outline'"
                @click="entryMode = 'template'"
              >
                {{ t('agents.wizard.mode_template') }}
              </Button>
              <Button
                size="sm"
                :variant="entryMode === 'nl' ? 'default' : 'outline'"
                @click="entryMode = 'nl'"
              >
                {{ t('agents.wizard.mode_nl') }}
              </Button>
            </div>
            <div v-if="entryMode === 'nl'" class="space-y-3">
              <Textarea v-model="nlDescription" rows="4" :placeholder="t('agents.nl.placeholder')" />
              <Button
                class="w-full bg-indigo-600 hover:bg-indigo-700 text-white"
                :disabled="nlBusy"
                @click="runNlGenerate"
              >
                <Loader2 v-if="nlBusy" class="w-4 h-4 animate-spin mr-2" />
                {{ t('agents.wizard.nl_generate') }}
              </Button>
            </div>
            <template v-else>
            <p class="text-sm text-muted-foreground">{{ t('agents.wizard.pick_template') }}</p>
            <button
              v-for="tpl in templates"
              :key="tpl.id"
              type="button"
              class="w-full text-left rounded-xl border p-4 transition-all"
              :class="
                templateId === tpl.id
                  ? 'border-indigo-500/50 bg-indigo-500/10'
                  : 'border-border hover:bg-muted/50'
              "
              @click="templateId = tpl.id"
            >
              <div class="font-semibold text-foreground">{{ t(tpl.titleKey) }}</div>
              <div class="text-xs text-muted-foreground mt-1">{{ t(tpl.descKey) }}</div>
            </button>
            </template>
          </div>

          <div v-else-if="step === 1" class="space-y-4">
            <div class="space-y-2">
              <label class="text-xs font-semibold text-muted-foreground">{{ t('agents.wizard.name_label') }}</label>
              <Input v-model="name" class="h-10" :placeholder="t('agents.wizard.name_ph')" />
            </div>
            <div class="space-y-2">
              <label class="text-xs font-semibold text-muted-foreground">{{ t('agents.create.desc_label') }}</label>
              <Textarea v-model="description" rows="3" :placeholder="t('agents.create.desc_placeholder')" />
            </div>
            <div class="space-y-2">
              <label class="text-xs font-semibold text-muted-foreground">{{ t('agents.wizard.model_label') }}</label>
              <select
                v-model="modelId"
                class="w-full h-10 rounded-lg border border-border bg-background px-3 text-sm"
                :disabled="loadingMeta"
              >
                <option v-for="m in models" :key="m.id" :value="m.id">{{ m.name || m.id }}</option>
              </select>
            </div>
          </div>

          <div v-else-if="step === 2" class="space-y-3">
            <p class="text-sm text-muted-foreground">{{ t('agents.wizard.skills_hint') }}</p>
            <div v-if="loadingMeta" class="flex justify-center py-8">
              <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
            <div v-else class="flex flex-wrap gap-2 max-h-48 overflow-y-auto">
              <button
                v-for="s in skills"
                :key="s.id"
                type="button"
                class="px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors"
                :class="
                  selectedSkillIds.includes(s.id)
                    ? 'border-indigo-500/50 bg-indigo-500/15 text-indigo-900 dark:text-indigo-100'
                    : 'border-border text-muted-foreground hover:bg-muted'
                "
                @click="toggleSkill(s.id)"
              >
                {{ s.name || s.id }}
              </button>
            </div>
          </div>

          <div v-else class="space-y-3 rounded-xl border border-border bg-muted/30 p-4 text-sm">
            <div class="flex items-center gap-2 font-semibold text-foreground">
              <Bot class="w-4 h-4 text-indigo-500" />
              {{ name }}
            </div>
            <p class="text-muted-foreground">{{ description || '—' }}</p>
            <p class="text-xs text-muted-foreground">
              {{ t('agents.wizard.review_model') }}: {{ modelId }}
            </p>
            <p class="text-xs text-muted-foreground">
              {{ t('agents.wizard.review_skills') }}: {{ selectedSkillIds.length }}
            </p>
          </div>

          <p v-if="submitError" class="text-sm text-red-500">{{ submitError }}</p>
        </div>

        <div class="px-6 py-4 border-t border-border flex items-center justify-between gap-2 shrink-0">
          <Button variant="ghost" size="sm" class="text-muted-foreground" @click="openAdvanced">
            {{ t('agents.wizard.advanced') }}
          </Button>
          <div class="flex items-center gap-2">
            <Button v-if="step > 0" variant="outline" size="sm" :disabled="submitting" @click="prevStep">
              <ChevronLeft class="w-4 h-4 mr-1" />
              {{ t('agents.wizard.back') }}
            </Button>
            <Button
              v-if="step === 0 && entryMode === 'nl'"
              size="sm"
              class="bg-indigo-600 hover:bg-indigo-700 text-white"
              :disabled="nlBusy"
              @click="runNlGenerate"
            >
              {{ t('agents.wizard.nl_generate') }}
            </Button>
            <Button
              v-else-if="step < 3"
              size="sm"
              class="bg-indigo-600 hover:bg-indigo-700 text-white"
              :disabled="!canNext || loadingMeta"
              @click="nextStep"
            >
              {{ t('agents.wizard.next') }}
              <ChevronRight class="w-4 h-4 ml-1" />
            </Button>
            <Button
              v-else
              size="sm"
              class="bg-indigo-600 hover:bg-indigo-700 text-white gap-1"
              :disabled="submitting"
              @click="submit"
            >
              <Loader2 v-if="submitting" class="w-4 h-4 animate-spin" />
              <Check v-else class="w-4 h-4" />
              {{ t('agents.wizard.create') }}
            </Button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

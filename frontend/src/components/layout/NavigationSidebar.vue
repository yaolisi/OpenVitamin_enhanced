<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useNavigation, type ViewType } from '@/composables/useNavigation'
import { useI18n } from 'vue-i18n'
import { 
  MessageSquare, 
  Settings,
  Database,
  BookOpen,
  BarChart3,
  User,
  Bot,
  Zap,
  Sparkles,
  Workflow,
  ChevronLeft,
  Image,
  LogIn,
  UserPlus,
  PackageOpen,
} from 'lucide-vue-next'
import { useRoute, useRouter } from 'vue-router'
import { useSystemConfigWithDebounce } from '@/composables/useSystemConfigWithDebounce'
import { getAuthConfig, getAuthSession, localLogout, type AuthConfig, type AuthSession } from '@/services/api'

const { activeView, setView } = useNavigation()
const router = useRouter()
const route = useRoute()
const { t } = useI18n()

const { systemConfig, refreshSystemConfig } = useSystemConfigWithDebounce({
  logPrefix: 'NavigationSidebar',
})
const systemVersion = computed(() => systemConfig.value?.version?.trim() || '')
const authSession = ref<AuthSession | null>(null)
const authConfig = ref<AuthConfig | null>(null)

const showAuthNav = computed(() => {
  const cfg = authConfig.value
  if (!cfg) return true
  return cfg.local_auth_enabled || cfg.oidc_enabled
})

const isLocalSignedIn = computed(
  () => authSession.value?.authenticated === true && authSession.value?.auth_method === 'local',
)

const userDisplayName = computed(() => {
  const s = authSession.value
  if (!s || !s.authenticated) return t('nav.guest')
  if (s.display_name) return s.display_name
  if (s.username) return s.username
  if (s.oidc_signed_in && s.user_id && s.user_id !== 'default') return s.user_id
  const roleKey = `nav.role_${s.platform_role}` as const
  const roleLabel = t(roleKey)
  if (roleLabel !== roleKey) return roleLabel
  return s.display_label || t('nav.guest')
})

const userStatusLine = computed(() => {
  const s = authSession.value
  if (!s) return t('nav.online')
  if (s.local_dev_admin) return t('nav.local_dev_admin')
  if (s.oidc_enabled && !s.oidc_signed_in) return t('nav.sign_in_hint')
  if (s.auth_method === 'api_key') return t('nav.api_key_auth')
  return t('nav.online')
})

async function refreshAuthSession() {
  try {
    const [session, config] = await Promise.all([getAuthSession(), getAuthConfig()])
    authSession.value = session
    authConfig.value = config
  } catch {
    authSession.value = null
    authConfig.value = null
  }
}

function goLogin() {
  router.push({ name: 'login', query: { redirect: router.currentRoute.value.fullPath } })
}

function goRegister() {
  router.push({ name: 'register', query: { redirect: router.currentRoute.value.fullPath } })
}

function goOneClickImport() {
  router.push({ name: 'bundle-import' })
}

function openAccountSettings() {
  const s = authSession.value
  if (s?.require_login && !s.authenticated) {
    router.push({ name: 'login', query: { redirect: router.currentRoute.value.fullPath } })
    return
  }
  if (s?.oidc_enabled && !s.oidc_signed_in) {
    router.push({ name: 'settings-enterprise' })
    return
  }
  router.push({ name: 'settings-backend' })
}

async function signOut() {
  try {
    await localLogout()
  } finally {
    await refreshAuthSession()
    if (authSession.value?.require_login) {
      router.push({ name: 'login' })
    }
  }
}

// Collapsible sidebar state
const isCollapsed = ref(false)
const toggleSidebar = () => {
  isCollapsed.value = !isCollapsed.value
}

onMounted(() => {
  void refreshSystemConfig()
  void refreshAuthSession()
})

// 平台主轴：对话 → 智能体 → 工作流 → 知识/技能/模型；文生图归入「工具」分组
const navGroups = computed(() => [
  {
    id: 'platform',
    label: t('nav.platform'),
    items: [
      { id: 'chat' as ViewType, label: t('nav.chat'), icon: MessageSquare },
      { id: 'agents' as ViewType, label: t('nav.agents'), icon: Bot },
      { id: 'workflow' as ViewType, label: t('nav.workflow'), icon: Workflow },
    ],
  },
  {
    id: 'capabilities',
    label: t('nav.capabilities'),
    items: [
      { id: 'knowledge' as ViewType, label: t('nav.knowledge'), icon: BookOpen },
      { id: 'skills' as ViewType, label: t('nav.skills'), icon: Sparkles },
      { id: 'models' as ViewType, label: t('nav.models'), icon: Database },
    ],
  },
  {
    id: 'tools',
    label: t('nav.tools'),
    items: [{ id: 'images' as ViewType, label: t('nav.image_generation'), icon: Image }],
  },
  {
    id: 'system',
    label: t('nav.system') || 'System',
    items: [
      { id: 'logs' as ViewType, label: t('nav.logs'), icon: BarChart3 },
      { id: 'settings' as ViewType, label: t('nav.settings'), icon: Settings },
    ],
  },
])

const utilityNavItems = computed(() => [
  { id: 'import', label: t('nav.one_click_import'), icon: PackageOpen, action: goOneClickImport },
])

const authNavItems = computed(() => {
  if (!showAuthNav.value) return []
  if (isLocalSignedIn.value) return []
  const items: Array<{ id: string; label: string; icon: typeof LogIn; action: () => void }> = []
  if (authConfig.value?.local_auth_enabled !== false) {
    items.push({ id: 'login', label: t('nav.sign_in'), icon: LogIn, action: goLogin })
    if (authConfig.value?.local_auth_allow_registration !== false) {
      items.push({ id: 'register', label: t('nav.sign_up'), icon: UserPlus, action: goRegister })
    }
  } else if (authConfig.value?.oidc_enabled) {
    items.push({ id: 'login', label: t('nav.sign_in'), icon: LogIn, action: goLogin })
  }
  return items
})
</script>

<template>
  <aside 
    :class="[
      'border-r border-border/40 bg-background flex flex-col h-full overflow-hidden relative z-20 transition-all duration-300',
      isCollapsed ? 'w-[72px]' : 'w-[200px]'
    ]"
  >
    <!-- Header：收缩时仅 Logo，展开时 Logo + 收起按钮 -->
    <div
      :class="[
        'flex p-3 transition-all duration-200 shrink-0',
        isCollapsed ? 'justify-center' : 'items-center justify-between'
      ]"
    >
      <div
        class="w-11 h-11 bg-gradient-to-br from-[#4f46e5] to-[#7c3aed] rounded-2xl flex items-center justify-center shadow-lg shadow-indigo-500/25 active:scale-95 transition-transform cursor-pointer shrink-0"
        :title="isCollapsed ? (t('nav.expand') || 'Expand') : (t('nav.collapse') || 'Collapse')"
        @click="toggleSidebar"
      >
        <Zap class="w-6 h-6 text-white" />
      </div>
      <button
        v-if="!isCollapsed"
        @click="toggleSidebar"
        class="p-2 rounded-xl text-muted-foreground/60 hover:text-foreground hover:bg-muted/60 transition-all"
      >
        <ChevronLeft class="w-5 h-5" />
      </button>
    </div>

    <!-- Navigation Menu - Scrollable -->
    <div class="flex-1 overflow-y-auto overflow-x-hidden px-3 py-2 space-y-6 scrollbar-thin">
      <div 
        v-for="(group, groupIndex) in navGroups" 
        :key="group.id"
        class="space-y-2"
      >
        <!-- Group Label -->
        <div 
          v-if="!isCollapsed && group.label" 
          class="px-3 pt-1"
        >
          <span class="text-[11px] font-bold tracking-[0.08em] text-muted-foreground/40 uppercase">
            {{ group.label }}
          </span>
        </div>
        <div 
          v-else-if="groupIndex > 0"
          class="px-3 pt-2 flex justify-center"
        >
          <div class="w-6 h-px bg-border/30"></div>
        </div>

        <!-- Nav Items -->
        <div :class="['space-y-1', isCollapsed ? 'flex flex-col items-center' : '']">
          <button
            v-for="nav in group.items"
            :key="nav.id"
            :class="[
              'group w-full flex items-center transition-all duration-200 relative',
              isCollapsed
                ? 'justify-center w-11 h-11 min-w-11 rounded-2xl'
                : 'justify-start py-3 px-4 rounded-2xl gap-3.5',
              activeView === nav.id
                ? 'bg-[#4f46e5] text-white shadow-lg shadow-indigo-500/30'
                : 'text-muted-foreground/70 hover:bg-muted/60 hover:text-foreground'
            ]"
            @click="setView(nav.id)"
            :title="isCollapsed ? nav.label : ''"
          >
            <component
              :is="nav.icon"
              :class="[
                'shrink-0 transition-all duration-200',
                isCollapsed ? 'w-5 h-5' : 'w-[22px] h-[22px]',
                activeView === nav.id ? 'stroke-[2px]' : 'stroke-[1.8px]'
              ]"
            />
            <span
              v-if="!isCollapsed"
              class="text-[14px] font-medium tracking-tight"
            >
              {{ nav.label }}
            </span>
            <!-- Active: 展开时右侧圆点 -->
            <div
              v-if="activeView === nav.id && !isCollapsed"
              class="absolute right-3 w-2 h-2 bg-white/90 rounded-full"
            />
            <!-- Active: 收缩时左侧竖条 -->
            <div
              v-if="activeView === nav.id && isCollapsed"
              class="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 bg-white/90 rounded-r"
            />
          </button>
        </div>
      </div>

      <!-- 一键导入 -->
      <div class="space-y-2">
        <div v-if="!isCollapsed" class="px-3 pt-1">
          <span class="text-[11px] font-bold tracking-[0.08em] text-muted-foreground/40 uppercase">
            {{ t('nav.utilities') }}
          </span>
        </div>
        <div v-else class="px-3 pt-2 flex justify-center">
          <div class="w-6 h-px bg-border/30"></div>
        </div>
        <div :class="['space-y-1', isCollapsed ? 'flex flex-col items-center' : '']">
          <button
            v-for="nav in utilityNavItems"
            :key="nav.id"
            type="button"
            class="group w-full flex items-center transition-all duration-200 relative text-muted-foreground/70 hover:bg-muted/60 hover:text-foreground"
            :class="[
              isCollapsed ? 'justify-center w-11 h-11 min-w-11 rounded-2xl' : 'justify-start py-3 px-4 rounded-2xl gap-3.5',
              route.name === 'bundle-import' ? 'bg-[#4f46e5] text-white shadow-lg shadow-indigo-500/30' : '',
            ]"
            :title="isCollapsed ? nav.label : ''"
            @click="nav.action"
          >
            <component
              :is="nav.icon"
              :class="[
                'shrink-0 transition-all duration-200',
                isCollapsed ? 'w-5 h-5' : 'w-[22px] h-[22px]',
                route.name === 'bundle-import' ? 'stroke-[2px]' : 'stroke-[1.8px]',
              ]"
            />
            <span v-if="!isCollapsed" class="text-[14px] font-medium tracking-tight">{{ nav.label }}</span>
          </button>
        </div>
      </div>

      <!-- 账号：未登录时快捷进入登录 / 注册 -->
      <div v-if="authNavItems.length" class="space-y-2">
        <div v-if="!isCollapsed" class="px-3 pt-1">
          <span class="text-[11px] font-bold tracking-[0.08em] text-muted-foreground/40 uppercase">
            {{ t('nav.account') }}
          </span>
        </div>
        <div v-else class="px-3 pt-2 flex justify-center">
          <div class="w-6 h-px bg-border/30"></div>
        </div>
        <div :class="['space-y-1', isCollapsed ? 'flex flex-col items-center' : '']">
          <button
            v-for="nav in authNavItems"
            :key="nav.id"
            type="button"
            class="group w-full flex items-center transition-all duration-200 relative text-muted-foreground/70 hover:bg-muted/60 hover:text-foreground"
            :class="isCollapsed ? 'justify-center w-11 h-11 min-w-11 rounded-2xl' : 'justify-start py-3 px-4 rounded-2xl gap-3.5'"
            :title="isCollapsed ? nav.label : ''"
            @click="nav.action"
          >
            <component
              :is="nav.icon"
              :class="[
                'shrink-0 transition-all duration-200',
                isCollapsed ? 'w-5 h-5' : 'w-[22px] h-[22px]',
                'stroke-[1.8px]',
              ]"
            />
            <span v-if="!isCollapsed" class="text-[14px] font-medium tracking-tight">{{ nav.label }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Bottom Section：收起/展开改为点 Logo，此处保留版本与用户区 -->
    <div class="mt-auto p-3 border-t border-border/30 space-y-2">
      <div
        v-if="systemVersion"
        :class="[
          'rounded-2xl border border-border/40 bg-muted/30 transition-all',
          isCollapsed ? 'px-2 py-2 flex justify-center' : 'px-3 py-2.5'
        ]"
        :title="isCollapsed ? `${t('nav.version') || 'Version'} v${systemVersion}` : ''"
      >
        <span v-if="isCollapsed" class="text-[11px] font-semibold text-muted-foreground/70">v{{ systemVersion }}</span>
        <div v-else class="flex items-center justify-between gap-3">
          <span class="text-[11px] font-medium uppercase tracking-[0.08em] text-muted-foreground/45">{{ t('nav.version') }}</span>
          <span class="text-[12px] font-semibold text-foreground/80">v{{ systemVersion }}</span>
        </div>
      </div>
      <!-- User Profile -->
      <button
        type="button"
        class="w-full flex items-center gap-3 group transition-all duration-200 rounded-2xl p-2.5 hover:bg-muted/60"
        :class="isCollapsed ? 'justify-center' : 'justify-start'"
        :title="userStatusLine"
        @click="openAccountSettings"
      >
        <div class="relative shrink-0">
          <div class="rounded-full bg-gradient-to-br from-muted/80 to-muted/40 border border-border/50 flex items-center justify-center overflow-hidden group-hover:border-indigo-500/50 transition-all duration-300 relative z-10"
            :class="isCollapsed ? 'w-9 h-9' : 'w-9 h-9'"
          >
            <User class="text-muted-foreground/70 group-hover:text-indigo-400 transition-colors"
              :class="isCollapsed ? 'w-[18px] h-[18px]' : 'w-[18px] h-[18px]'"
            />
          </div>
          <!-- Online Status Indicator -->
          <div class="absolute bottom-0 right-0 w-2.5 h-2.5 bg-emerald-500 border-2 border-background rounded-full z-20"></div>
        </div>
        <div v-if="!isCollapsed" class="flex flex-col items-start min-w-0">
          <span class="text-[13px] font-medium text-foreground/90 truncate">{{ userDisplayName }}</span>
          <span class="text-[11px] text-muted-foreground/50 truncate">{{ userStatusLine }}</span>
        </div>
      </button>
      <button
        v-if="authSession?.authenticated && authSession.auth_method === 'local' && !isCollapsed"
        type="button"
        class="w-full text-xs text-muted-foreground hover:text-foreground py-1"
        @click.stop="signOut"
      >
        {{ t('auth.logout') }}
      </button>
    </div>
  </aside>
</template>

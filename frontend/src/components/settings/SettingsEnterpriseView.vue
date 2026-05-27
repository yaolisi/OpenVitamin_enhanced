<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Shield, ChevronLeft, ChevronRight, Sliders, RefreshCw, CheckCircle2, AlertTriangle } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  getEnterpriseCapabilities,
  getOidcLoginConfig,
  prepareOidcAuthorize,
  type EnterpriseCapabilities,
} from '@/services/api'
import { useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()
const { t } = useI18n()
const settingsSection = computed(() => route.name as string)
const navCollapsed = ref(false)
const loading = ref(true)
const error = ref<string | null>(null)
const caps = ref<EnterpriseCapabilities | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    caps.value = await getEnterpriseCapabilities()
  } catch (e) {
    error.value = (e as Error)?.message || String(e)
  } finally {
    loading.value = false
  }
}

async function startOidcLogin() {
  try {
    const cfg = await getOidcLoginConfig()
    if (!cfg.enabled) return
    const prep = await prepareOidcAuthorize()
    sessionStorage.setItem('oidc_state', prep.state)
    sessionStorage.setItem('oidc_code_verifier', prep.code_verifier)
    window.location.href = prep.authorize_url
  } catch (e) {
    error.value = (e as Error)?.message || String(e)
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="flex-1 flex flex-col min-h-0 overflow-hidden bg-background">
    <header class="px-10 pt-10 pb-6 shrink-0 border-b border-border/50">
      <div class="flex items-center justify-between gap-4">
        <div>
          <h1 class="text-3xl font-black text-foreground flex items-center gap-3">
            <Shield class="w-8 h-8 text-indigo-500" />
            {{ t('settings.enterprise.title') }}
          </h1>
          <p class="text-muted-foreground mt-2 max-w-2xl">{{ t('settings.enterprise.subtitle') }}</p>
        </div>
        <Button
          v-if="caps?.oidc_enabled"
          variant="outline"
          class="gap-2"
          @click="startOidcLogin"
        >
          {{ t('auth.login_oidc') }}
        </Button>
        <Button variant="outline" class="gap-2" :disabled="loading" @click="load">
          <RefreshCw class="w-4 h-4" :class="loading ? 'animate-spin' : ''" />
          {{ t('settings.enterprise.refresh') }}
        </Button>
      </div>
    </header>

    <div class="flex-1 flex overflow-hidden px-10 pb-10 gap-8 pt-8">
      <aside
        class="shrink-0 hidden lg:flex flex-col transition-all duration-200"
        :class="navCollapsed ? 'w-16' : 'w-56'"
      >
        <div class="flex items-center justify-between mb-4">
          <div v-if="!navCollapsed" class="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
            {{ t('settings.navigation_title') }}
          </div>
          <button
            class="h-7 w-7 rounded-lg border border-border/50 flex items-center justify-center"
            @click="navCollapsed = !navCollapsed"
          >
            <ChevronLeft v-if="!navCollapsed" class="w-4 h-4" />
            <ChevronRight v-else class="w-4 h-4" />
          </button>
        </div>
        <button
          class="w-full text-left text-sm font-semibold px-3 py-2 rounded-lg hover:bg-muted/40 mb-1"
          @click="router.push('/settings/general')"
        >
          <span v-if="!navCollapsed">{{ t('settings.general_nav') }}</span>
          <Sliders v-else class="w-4 h-4 mx-auto" />
        </button>
        <button
          class="w-full text-left text-sm font-semibold px-3 py-2 rounded-lg bg-muted/40 text-foreground"
        >
          <span v-if="!navCollapsed">{{ t('settings.enterprise.nav') }}</span>
          <Shield v-else class="w-4 h-4 mx-auto" />
        </button>
      </aside>

      <main class="flex-1 min-w-0 overflow-y-auto space-y-6">
        <p v-if="error" class="text-sm text-red-500">{{ error }}</p>
        <div v-if="loading" class="text-muted-foreground text-sm">{{ t('settings.enterprise.loading') }}</div>

        <template v-else-if="caps">
          <div class="rounded-2xl border border-border p-6 bg-card">
            <div class="flex items-center justify-between flex-wrap gap-3">
              <div>
                <p class="text-sm text-muted-foreground">{{ t('settings.enterprise.readiness') }}</p>
                <p class="text-3xl font-black text-foreground">
                  {{ caps.production_readiness?.percent ?? 0 }}%
                </p>
              </div>
              <Badge :variant="caps.identity_boundary_ready ? 'default' : 'outline'">
                {{
                  caps.identity_boundary_ready
                    ? t('settings.enterprise.identity_ok')
                    : t('settings.enterprise.identity_warn')
                }}
              </Badge>
            </div>
          </div>

          <div class="grid md:grid-cols-2 gap-4">
            <div class="rounded-xl border border-border p-4 space-y-2 text-sm">
              <p class="font-semibold">{{ t('settings.enterprise.block_identity') }}</p>
              <p>OIDC: {{ caps.oidc_enabled ? (caps.oidc_configured ? '✓' : '⚠') : '—' }}</p>
              <p>RBAC: {{ caps.rbac_enabled ? '✓' : '—' }}</p>
              <p>{{ t('settings.enterprise.tenant') }}: {{ caps.tenant_enforcement_enabled ? '✓' : '—' }}</p>
            </div>
            <div class="rounded-xl border border-border p-4 space-y-2 text-sm">
              <p class="font-semibold">{{ t('settings.enterprise.block_obs') }}</p>
              <p>OTel: {{ caps.otel_ready ? '✓' : caps.otel_enabled ? '⚠' : '—' }}</p>
              <p>Prometheus: {{ caps.prometheus_enabled ? '✓' : '—' }}</p>
              <p>{{ t('settings.enterprise.audit') }}: {{ caps.audit_log_enabled ? '✓' : '—' }}</p>
            </div>
          </div>

          <div class="rounded-xl border border-border p-4">
            <p class="font-semibold mb-3">{{ t('settings.enterprise.checklist') }}</p>
            <ul class="space-y-2">
              <li
                v-for="item in caps.production_readiness?.checks || []"
                :key="item.id"
                class="flex items-start gap-2 text-sm"
              >
                <CheckCircle2 v-if="item.status === 'ok'" class="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                <AlertTriangle v-else class="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
                <div>
                  <span>{{ item.label }}</span>
                  <p v-if="item.hint" class="text-xs text-muted-foreground">{{ item.hint }}</p>
                </div>
              </li>
            </ul>
          </div>

          <p class="text-xs text-muted-foreground">{{ t('settings.enterprise.disclaimer') }}</p>
        </template>
      </main>
    </div>
  </div>
</template>

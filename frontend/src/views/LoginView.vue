<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Loader2, LogIn, Shield } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  getAuthConfig,
  localLogin,
  prepareOidcAuthorize,
  type AuthConfig,
} from '@/services/api'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const config = ref<AuthConfig | null>(null)
const loading = ref(true)
const submitting = ref(false)
const error = ref<string | null>(null)
const username = ref('')
const password = ref('')

const redirectTo = computed(() => String(route.query.redirect || '/chat'))

const showLocal = computed(() => config.value?.local_auth_enabled === true)
const showOidc = computed(() => config.value?.oidc_enabled === true)

onMounted(async () => {
  try {
    config.value = await getAuthConfig()
    if (!config.value.local_auth_enabled && !config.value.oidc_enabled) {
      error.value = t('auth.login.no_method')
    }
  } catch (e) {
    error.value = (e as Error)?.message || String(e)
  } finally {
    loading.value = false
  }
})

async function submitLocal() {
  error.value = null
  submitting.value = true
  try {
    await localLogin({ username: username.value.trim(), password: password.value })
    await router.replace(redirectTo.value)
  } catch (e) {
    error.value = (e as Error)?.message || t('auth.login.failed')
  } finally {
    submitting.value = false
  }
}

async function startOidc() {
  error.value = null
  submitting.value = true
  try {
    const prep = await prepareOidcAuthorize()
    sessionStorage.setItem('oidc_state', prep.state)
    sessionStorage.setItem('oidc_code_verifier', prep.code_verifier)
    sessionStorage.setItem('oidc_redirect_after', redirectTo.value)
    window.location.href = prep.authorize_url
  } catch (e) {
    error.value = (e as Error)?.message || t('auth.login.failed')
    submitting.value = false
  }
}

function goRegister() {
  router.push({ path: '/register', query: route.query })
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center p-6 bg-gradient-to-br from-background via-background to-indigo-500/5">
    <div class="w-full max-w-md rounded-2xl border border-border bg-card shadow-xl p-8 space-y-6">
      <div class="text-center space-y-2">
        <div class="mx-auto w-12 h-12 rounded-2xl bg-indigo-600 flex items-center justify-center">
          <Shield class="w-6 h-6 text-white" />
        </div>
        <h1 class="text-2xl font-bold">{{ t('auth.login.title') }}</h1>
        <p class="text-sm text-muted-foreground">{{ t('auth.login.subtitle') }}</p>
      </div>

      <div v-if="loading" class="flex justify-center py-8">
        <Loader2 class="w-8 h-8 animate-spin text-indigo-500" />
      </div>

      <template v-else>
        <form v-if="showLocal" class="space-y-4" @submit.prevent="submitLocal">
          <div class="space-y-2">
            <label class="text-sm font-medium">{{ t('auth.login.username') }}</label>
            <Input v-model="username" autocomplete="username" required />
          </div>
          <div class="space-y-2">
            <label class="text-sm font-medium">{{ t('auth.login.password') }}</label>
            <Input v-model="password" type="password" autocomplete="current-password" required />
          </div>
          <Button
            type="submit"
            class="w-full gap-2 bg-indigo-600 hover:bg-indigo-700 text-white"
            :disabled="submitting"
          >
            <Loader2 v-if="submitting" class="w-4 h-4 animate-spin" />
            <LogIn v-else class="w-4 h-4" />
            {{ t('auth.login.submit') }}
          </Button>
        </form>

        <div v-if="showLocal && showOidc" class="relative py-2">
          <div class="absolute inset-0 flex items-center">
            <div class="w-full border-t border-border" />
          </div>
          <div class="relative flex justify-center text-xs uppercase">
            <span class="bg-card px-2 text-muted-foreground">{{ t('auth.login.or') }}</span>
          </div>
        </div>

        <Button
          v-if="showOidc"
          variant="outline"
          class="w-full"
          :disabled="submitting"
          @click="startOidc"
        >
          {{ t('auth.login_oidc') }}
        </Button>

        <p v-if="showLocal && config?.local_auth_allow_registration" class="text-center text-sm text-muted-foreground">
          {{ t('auth.login.no_account') }}
          <button type="button" class="text-indigo-600 hover:underline ml-1" @click="goRegister">
            {{ t('auth.login.register_link') }}
          </button>
        </p>

        <div
          v-if="!showLocal && !showOidc && !loading"
          class="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 space-y-3 text-sm"
        >
          <p class="font-medium text-foreground">{{ t('auth.login.setup_title') }}</p>
          <p class="text-muted-foreground leading-relaxed">{{ t('auth.login.setup_hint') }}</p>
          <code class="block text-xs bg-muted/60 rounded-lg p-3 whitespace-pre-wrap text-left">
LOCAL_AUTH_ENABLED=true
LOCAL_AUTH_ALLOW_REGISTRATION=true
          </code>
          <p class="text-xs text-muted-foreground">{{ t('auth.login.setup_restart') }}</p>
        </div>

        <p v-if="error" class="text-sm text-red-500 text-center">{{ error }}</p>
      </template>
    </div>
  </div>
</template>

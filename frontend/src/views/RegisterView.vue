<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Loader2, UserPlus } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { getAuthConfig, localRegister } from '@/services/api'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const loading = ref(true)
const submitting = ref(false)
const error = ref<string | null>(null)
const username = ref('')
const password = ref('')
const displayName = ref('')
const email = ref('')

onMounted(async () => {
  try {
    const cfg = await getAuthConfig()
    if (!cfg.local_auth_enabled || !cfg.local_auth_allow_registration) {
      error.value = t('auth.register.disabled')
    }
  } catch (e) {
    error.value = (e as Error)?.message || String(e)
  } finally {
    loading.value = false
  }
})

async function submit() {
  error.value = null
  submitting.value = true
  try {
    await localRegister({
      username: username.value.trim(),
      password: password.value,
      display_name: displayName.value.trim() || undefined,
      email: email.value.trim() || undefined,
    })
    const redirect = String(route.query.redirect || '/chat')
    await router.replace(redirect)
  } catch (e) {
    error.value = (e as Error)?.message || t('auth.register.failed')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center p-6 bg-gradient-to-br from-background via-background to-indigo-500/5">
    <div class="w-full max-w-md rounded-2xl border border-border bg-card shadow-xl p-8 space-y-6">
      <div class="text-center space-y-2">
        <h1 class="text-2xl font-bold">{{ t('auth.register.title') }}</h1>
        <p class="text-sm text-muted-foreground">{{ t('auth.register.subtitle') }}</p>
      </div>

      <div v-if="loading" class="flex justify-center py-8">
        <Loader2 class="w-8 h-8 animate-spin text-indigo-500" />
      </div>

      <form v-else class="space-y-4" @submit.prevent="submit">
        <div class="space-y-2">
          <label class="text-sm font-medium">{{ t('auth.login.username') }}</label>
          <Input v-model="username" autocomplete="username" required />
        </div>
        <div class="space-y-2">
          <label class="text-sm font-medium">{{ t('auth.register.display_name') }}</label>
          <Input v-model="displayName" autocomplete="name" />
        </div>
        <div class="space-y-2">
          <label class="text-sm font-medium">{{ t('auth.register.email') }}</label>
          <Input v-model="email" type="email" autocomplete="email" />
        </div>
        <div class="space-y-2">
          <label class="text-sm font-medium">{{ t('auth.login.password') }}</label>
          <Input v-model="password" type="password" autocomplete="new-password" required />
          <p class="text-xs text-muted-foreground">{{ t('auth.register.password_hint') }}</p>
        </div>
        <Button
          type="submit"
          class="w-full gap-2 bg-indigo-600 hover:bg-indigo-700 text-white"
          :disabled="submitting"
        >
          <Loader2 v-if="submitting" class="w-4 h-4 animate-spin" />
          <UserPlus v-else class="w-4 h-4" />
          {{ t('auth.register.submit') }}
        </Button>
        <p class="text-center text-sm">
          <button type="button" class="text-indigo-600 hover:underline" @click="router.push({ path: '/login', query: route.query })">
            {{ t('auth.register.back_login') }}
          </button>
        </p>
        <p v-if="error" class="text-sm text-red-500 text-center">{{ error }}</p>
      </form>
    </div>
  </div>
</template>

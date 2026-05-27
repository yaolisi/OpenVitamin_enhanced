<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { exchangeOidcToken, setOidcAccessToken } from '@/services/api'
import { Loader2 } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const error = ref<string | null>(null)

onMounted(async () => {
  const code = String(route.query.code || '')
  const state = String(route.query.state || '')
  const savedState = sessionStorage.getItem('oidc_state') || ''
  const verifier = sessionStorage.getItem('oidc_code_verifier') || ''
  sessionStorage.removeItem('oidc_state')
  sessionStorage.removeItem('oidc_code_verifier')

  if (!code || !verifier) {
    error.value = t('auth.callback.missing_code')
    return
  }
  if (state && savedState && state !== savedState) {
    error.value = t('auth.callback.state_mismatch')
    return
  }
  try {
    const tokens = await exchangeOidcToken({ code, code_verifier: verifier })
    setOidcAccessToken(tokens.access_token)
    router.replace('/chat')
  } catch (e) {
    error.value = (e as Error)?.message || t('auth.callback.failed')
  }
})
</script>

<template>
  <div class="min-h-screen flex flex-col items-center justify-center gap-4 p-8">
    <Loader2 v-if="!error" class="w-8 h-8 animate-spin text-indigo-500" />
    <p v-if="!error" class="text-muted-foreground">{{ t('auth.callback.signing_in') }}</p>
    <p v-else class="text-red-500 text-sm max-w-md text-center">{{ error }}</p>
  </div>
</template>

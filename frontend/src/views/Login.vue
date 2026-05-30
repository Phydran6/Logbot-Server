<!-- ==============================================================================
     Name:        Phydran6
     Kontakt:     Phydran6
     Version:     2026.05.30.17.22.26
     Beschreibung: LogBot - Login (Passwort + optional MFA-Code)
     ============================================================================== -->

<template>
  <div class="min-h-screen flex items-center justify-center" :style="{ backgroundColor: 'var(--color-bg)' }">
    <div class="p-8 rounded-lg shadow-md w-full max-w-md" :style="cardStyle">
      <h1 class="text-3xl font-bold text-center mb-2" :style="{ color: 'var(--color-text-primary)' }">📋 LogBot</h1>
      <p class="text-center mb-6" :style="{ color: 'var(--color-text-muted)' }">Zentraler Log-Server</p>

      <div v-if="error" class="px-4 py-3 rounded mb-4" :style="errorStyle">
        {{ error }}
      </div>

      <!-- Schritt 1: Benutzername + Passwort -->
      <form v-if="!mfaToken" @submit.prevent="handleLogin">
        <div class="mb-4">
          <label class="block text-sm font-bold mb-2" :style="{ color: 'var(--color-text-secondary)' }">Benutzername</label>
          <input
            v-model="username"
            type="text"
            class="w-full px-3 py-2 rounded focus:outline-none"
            :style="inputStyle"
            required
            autofocus
          >
        </div>
        <div class="mb-6">
          <label class="block text-sm font-bold mb-2" :style="{ color: 'var(--color-text-secondary)' }">Passwort</label>
          <input
            v-model="password"
            type="password"
            class="w-full px-3 py-2 rounded focus:outline-none"
            :style="inputStyle"
            required
          >
        </div>
        <button
          type="submit"
          :disabled="loading"
          class="w-full text-white font-bold py-2 px-4 rounded disabled:opacity-50 hover:opacity-90"
          :style="{ backgroundColor: 'var(--color-primary)' }"
        >
          {{ loading ? 'Anmelden...' : 'Anmelden' }}
        </button>
      </form>

      <!-- Schritt 2: MFA-Code -->
      <form v-else @submit.prevent="handleMfa">
        <p class="text-sm mb-4" :style="{ color: 'var(--color-text-secondary)' }">
          🔐 Zwei-Faktor-Authentifizierung erforderlich. Gib den 6-stelligen Code aus deiner Authenticator-App oder einen Backup-Code ein.
        </p>
        <div class="mb-2">
          <label class="block text-sm font-bold mb-2" :style="{ color: 'var(--color-text-secondary)' }">Code</label>
          <input
            v-model="mfaCode"
            type="text"
            inputmode="text"
            autocomplete="one-time-code"
            class="w-full px-3 py-2 rounded focus:outline-none text-center tracking-widest"
            :style="inputStyle"
            placeholder="123456 oder Backup-Code"
            required
            autofocus
          >
        </div>
        <p class="text-xs mb-6" :style="{ color: 'var(--color-text-muted)' }">
          Gültig noch <strong>{{ formatCountdown(mfaSecondsLeft) }}</strong>
        </p>
        <button
          type="submit"
          :disabled="loading || mfaSecondsLeft <= 0"
          class="w-full text-white font-bold py-2 px-4 rounded disabled:opacity-50 hover:opacity-90 mb-2"
          :style="{ backgroundColor: 'var(--color-primary)' }"
        >
          {{ loading ? 'Prüfe Code...' : 'Code bestätigen' }}
        </button>
        <button
          type="button"
          @click="resetToStep1"
          class="w-full text-sm py-1 hover:underline"
          :style="{ color: 'var(--color-text-muted)' }"
        >
          Abbrechen
        </button>
      </form>

      <div class="flex justify-center gap-4 mt-6 text-xs" :style="{ color: 'var(--color-text-muted)' }">
        <router-link to="/impressum" class="hover:underline">Impressum</router-link>
        <router-link to="/datenschutz" class="hover:underline">Datenschutz</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useThemeStore } from '../stores/themeStore'

const router = useRouter()
const auth = useAuthStore()
const themeStore = useThemeStore()

const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

// MFA-Schritt 2
const mfaToken = ref(null)
const mfaCode = ref('')
const mfaSecondsLeft = ref(0)
let mfaTimer = null

// Computed Styles
const cardStyle = computed(() => ({
  backgroundColor: 'var(--color-surface)',
  borderColor: 'var(--color-border)'
}))

const inputStyle = computed(() => ({
  backgroundColor: 'var(--color-surface-elevated)',
  borderColor: 'var(--color-border)',
  color: 'var(--color-text-primary)',
  border: '1px solid var(--color-border)'
}))

const errorStyle = computed(() => ({
  backgroundColor: 'var(--color-surface-elevated)',
  border: '1px solid var(--color-danger)',
  color: 'var(--color-danger)'
}))

onMounted(() => {
  if (!document.documentElement.getAttribute('data-theme')) {
    themeStore.initTheme('dark')
  }
})

onUnmounted(() => {
  if (mfaTimer) clearInterval(mfaTimer)
})

function formatCountdown(secs) {
  if (secs <= 0) return 'abgelaufen'
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

function startMfaCountdown(seconds) {
  if (mfaTimer) clearInterval(mfaTimer)
  mfaSecondsLeft.value = seconds
  mfaTimer = setInterval(() => {
    mfaSecondsLeft.value = Math.max(0, mfaSecondsLeft.value - 1)
    if (mfaSecondsLeft.value === 0) clearInterval(mfaTimer)
  }, 1000)
}

function resetToStep1() {
  mfaToken.value = null
  mfaCode.value = ''
  mfaSecondsLeft.value = 0
  if (mfaTimer) clearInterval(mfaTimer)
  error.value = ''
}

async function handleLogin() {
  loading.value = true
  error.value = ''
  try {
    const result = await auth.login(username.value, password.value)
    if (result?.mfa_required) {
      mfaToken.value = result.mfa_token
      startMfaCountdown(result.expires_in_seconds || 300)
    } else {
      router.push('/')
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function handleMfa() {
  loading.value = true
  error.value = ''
  try {
    await auth.loginMfa(mfaToken.value, mfaCode.value.trim())
    router.push('/')
  } catch (e) {
    error.value = e.message
    mfaCode.value = ''
  } finally {
    loading.value = false
  }
}
</script>

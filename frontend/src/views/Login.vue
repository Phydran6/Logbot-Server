<!-- ==============================================================================
     Name:        Phydran6
     Kontakt:     Phydran6
     Version:     2026.08.02.14.00.00
     Changelog:   ../../../CHANGELOG/frontend.md
     Beschreibung: LogBot - Anmeldung (Passwort + optional MFA-Code)
     ============================================================================== -->

<template>
  <div class="login-page">
    <!-- Linke Haelfte: Marke. Auf schmalen Schirmen ausgeblendet. -->
    <section class="login-brand">
      <div class="login-brand-inner">
        <div class="brand-mark">
          <img v-if="logoUrl" :src="logoUrl" :alt="companyName" class="brand-logo">
          <span v-else>{{ brandInitial }}</span>
        </div>
        <h1 class="login-brand-title">{{ companyName }}</h1>
        <p class="login-brand-tagline">{{ tagline }}</p>

        <ul class="login-points">
          <li v-for="point in points" :key="point">
            <AppIcon name="check" :size="16" />
            <span>{{ point }}</span>
          </li>
        </ul>
      </div>
    </section>

    <!-- Rechte Haelfte: Formular -->
    <section class="login-form-side">
      <div class="login-card">
        <!-- Marke klein, wenn die linke Haelfte fehlt -->
        <div class="login-card-brand lg:hidden">
          <div class="brand-mark">
            <img v-if="logoUrl" :src="logoUrl" :alt="companyName" class="brand-logo">
            <span v-else>{{ brandInitial }}</span>
          </div>
          <div>
            <p class="font-semibold" style="color: var(--color-text-primary)">{{ companyName }}</p>
            <p class="text-xs" style="color: var(--color-text-muted)">{{ tagline }}</p>
          </div>
        </div>

        <h2 class="login-title">{{ mfaToken ? 'Bestätigung' : 'Anmelden' }}</h2>
        <p class="login-subtitle">
          {{ mfaToken
            ? 'Gib den Code aus deiner Authenticator-App oder einen Backup-Code ein.'
            : 'Melde dich mit deinem Konto an.' }}
        </p>

        <transition name="slide">
          <div v-if="error" class="login-error" role="alert">
            <AppIcon name="warning" :size="18" class="shrink-0" />
            <span>{{ error }}</span>
          </div>
        </transition>

        <!-- Schritt 1: Benutzername + Passwort -->
        <form v-if="!mfaToken" class="space-y-4" @submit.prevent="handleLogin">
          <div>
            <label for="login-username" class="label">Benutzername</label>
            <input
              id="login-username"
              v-model="username"
              type="text"
              class="input"
              autocomplete="username"
              required
              autofocus
            >
          </div>

          <div>
            <label for="login-password" class="label">Passwort</label>
            <div class="password-wrap">
              <input
                id="login-password"
                v-model="password"
                :type="showPassword ? 'text' : 'password'"
                class="input pr-11"
                autocomplete="current-password"
                required
              >
              <button
                type="button"
                class="password-toggle"
                :title="showPassword ? 'Passwort verbergen' : 'Passwort anzeigen'"
                :aria-label="showPassword ? 'Passwort verbergen' : 'Passwort anzeigen'"
                @click="showPassword = !showPassword"
              >
                <AppIcon :name="showPassword ? 'close' : 'lock'" :size="16" />
              </button>
            </div>
          </div>

          <button type="submit" class="btn btn-primary w-full" :disabled="loading">
            {{ loading ? 'Anmelden…' : 'Anmelden' }}
          </button>
        </form>

        <!-- Schritt 2: MFA-Code -->
        <form v-else class="space-y-4" @submit.prevent="handleMfa">
          <div>
            <label for="mfa-code" class="label">Code</label>
            <input
              id="mfa-code"
              v-model="mfaCode"
              type="text"
              inputmode="text"
              autocomplete="one-time-code"
              class="input code-input"
              placeholder="123456"
              required
              autofocus
            >
            <p class="hint">
              Gültig noch <strong>{{ formatCountdown(mfaSecondsLeft) }}</strong> — ein Backup-Code geht auch.
            </p>
          </div>

          <button type="submit" class="btn btn-primary w-full" :disabled="loading || mfaSecondsLeft <= 0">
            {{ loading ? 'Prüfe Code…' : 'Code bestätigen' }}
          </button>
          <button type="button" class="btn btn-ghost w-full" @click="resetToStep1">Abbrechen</button>
        </form>

        <div class="login-links">
          <router-link to="/impressum" class="hover:underline">Impressum</router-link>
          <span>·</span>
          <router-link to="/datenschutz" class="hover:underline">Datenschutz</router-link>
        </div>
      </div>

      <p class="login-version">v{{ appVersion }}</p>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useThemeStore } from '../stores/themeStore'
import { useBrandingStore } from '../stores/brandingStore'
import AppIcon from '../components/AppIcon.vue'
import pkg from '../../package.json'

const router = useRouter()
const auth = useAuthStore()
const themeStore = useThemeStore()
const brandingStore = useBrandingStore()

const appVersion = pkg.version

const username = ref('')
const password = ref('')
const showPassword = ref(false)
const loading = ref(false)
const error = ref('')

// MFA-Schritt 2
const mfaToken = ref(null)
const mfaCode = ref('')
const mfaSecondsLeft = ref(0)
let mfaTimer = null

const companyName = computed(() => brandingStore.config?.company_name || 'LogBot')
const tagline = computed(() => brandingStore.config?.tagline || 'Zentraler Log-Server')
const logoUrl = computed(() => brandingStore.getLogoUrl())
const brandInitial = computed(() => (companyName.value || 'L').trim().charAt(0).toUpperCase())

const points = [
  'Logs aller Geräte an einer Stelle',
  'Filter nach Gerät, Schweregrad und Logtyp',
  'Verschlüsselter Empfang über HTTPS-Agenten',
]

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

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 1fr;
  background-color: var(--color-bg);
}

@media (min-width: 1024px) {
  .login-page {
    grid-template-columns: 1.1fr 1fr;
  }
}

/* ------------------------------------------------------------------- Marke */
.login-brand {
  display: none;
  position: relative;
  overflow: hidden;
  padding: 3rem;
  align-items: center;
  background:
    radial-gradient(120% 120% at 0% 0%, var(--primary-soft-strong) 0%, transparent 55%),
    var(--color-surface);
  border-right: 1px solid var(--color-border);
}

@media (min-width: 1024px) {
  .login-brand {
    display: flex;
  }
}

.login-brand-inner {
  max-width: 26rem;
}

.login-brand-title {
  margin-top: 1.5rem;
  font-size: 2rem;
  font-weight: 700;
  color: var(--color-text-primary);
}

.login-brand-tagline {
  margin-top: 0.5rem;
  font-size: 1rem;
  color: var(--color-text-muted);
}

.login-points {
  margin-top: 2rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.login-points li {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  font-size: 0.875rem;
  color: var(--color-text-secondary);
}

.login-points svg {
  color: var(--color-accent);
  flex-shrink: 0;
}

.brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 3rem;
  height: 3rem;
  border-radius: var(--radius-lg);
  background-color: var(--primary-soft);
  color: var(--color-primary);
  font-size: 1.25rem;
  font-weight: 700;
  overflow: hidden;
  flex-shrink: 0;
}

.brand-logo {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

/* ---------------------------------------------------------------- Formular */
.login-form-side {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  padding: 2rem 1.25rem;
}

.login-card {
  width: 100%;
  max-width: 24rem;
  padding: 1.75rem;
  background-color: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
}

.login-card-brand {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}

.login-title {
  font-size: 1.375rem;
  font-weight: 700;
  color: var(--color-text-primary);
}

.login-subtitle {
  margin-top: 0.25rem;
  margin-bottom: 1.5rem;
  font-size: 0.875rem;
  color: var(--color-text-muted);
}

.login-error {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  margin-bottom: 1rem;
  padding: 0.75rem 0.875rem;
  border-radius: var(--radius);
  background-color: var(--danger-soft);
  color: var(--color-danger);
  font-size: 0.875rem;
}

.password-wrap {
  position: relative;
}

.password-toggle {
  position: absolute;
  top: 50%;
  right: 0.5rem;
  transform: translateY(-50%);
  padding: 0.375rem;
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
}

.password-toggle:hover {
  color: var(--color-text-primary);
  background-color: var(--hover-surface);
}

.code-input {
  text-align: center;
  letter-spacing: 0.35em;
  font-size: 1.125rem;
  font-family: var(--font-mono);
}

.login-links {
  display: flex;
  justify-content: center;
  gap: 0.5rem;
  margin-top: 1.5rem;
  font-size: 0.75rem;
  color: var(--color-text-muted);
}

.login-version {
  font-size: 0.6875rem;
  color: var(--color-text-muted);
  font-variant-numeric: tabular-nums;
}

/* ----------------------------------------------------------------- Übergang */
.slide-enter-active,
.slide-leave-active {
  transition: opacity var(--duration) var(--ease), transform var(--duration) var(--ease);
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  transform: translateY(-0.25rem);
}
</style>

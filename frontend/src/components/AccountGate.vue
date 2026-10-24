<!-- ==============================================================================
     Name:        Phydran6
     Kontakt:     Phydran6
     Changelog:   ../../../CHANGELOG/frontend.md
     Beschreibung: LogBot - Pflichtangaben vor der ersten Benutzung.

     Ab 2026.10.23 braucht jedes Konto eine E-Mail-Adresse: für den
     Passwort-Reset per Mail, die Anmeldung per Mail-Link in der App und für
     Meldungen. Und wer noch mit dem Auslieferungspasswort (admin/admin) oder
     einem vom Administrator vergebenen Passwort unterwegs ist, setzt zuerst
     ein eigenes. Solange das fehlt, liegt dieser Dialog über der Oberfläche.
     ============================================================================== -->
<template>
  <div v-if="visible" class="gate-backdrop" role="dialog" aria-modal="true" aria-labelledby="gate-title">
    <div class="card gate-card">
      <h2 id="gate-title" class="gate-title">
        {{ step === 'password' ? 'Eigenes Passwort festlegen' : 'E-Mail-Adresse hinterlegen' }}
      </h2>

      <!-- Schritt 1: Passwort -->
      <form v-if="step === 'password'" class="space-y-3" @submit.prevent="savePassword">
        <p class="gate-text">
          Dieses Konto nutzt noch ein vorgegebenes Passwort. Bevor es weitergeht, bitte ein
          eigenes festlegen – alle anderen Sitzungen werden dabei beendet.
        </p>
        <label class="gate-label">Aktuelles Passwort
          <input v-model="current" type="password" class="input" autocomplete="current-password" required>
        </label>
        <label class="gate-label">Neues Passwort
          <input v-model="next" type="password" class="input" autocomplete="new-password" minlength="8" required>
        </label>
        <label class="gate-label">Neues Passwort wiederholen
          <input v-model="repeat" type="password" class="input" autocomplete="new-password" minlength="8" required>
        </label>
        <p class="gate-hint">Mindestens 8 Zeichen, mit einem Großbuchstaben und einer Ziffer.</p>
        <p v-if="error" class="gate-error">{{ error }}</p>
        <button class="btn btn-primary w-full" :disabled="busy">{{ busy ? 'Wird gespeichert…' : 'Passwort speichern' }}</button>
      </form>

      <!-- Schritt 2: Adresse -->
      <form v-else-if="step === 'email'" class="space-y-3" @submit.prevent="saveEmail">
        <p class="gate-text">
          Ab jetzt hat jedes Konto eine E-Mail-Adresse. Darüber lässt sich ein vergessenes
          Passwort zurücksetzen, die Handy-App anmelden und – für Administratoren – über
          wichtige Ereignisse informieren.
        </p>
        <label class="gate-label">E-Mail-Adresse
          <input v-model="email" type="email" class="input" autocomplete="email" required placeholder="name@firma.de">
        </label>
        <p v-if="error" class="gate-error">{{ error }}</p>
        <button class="btn btn-primary w-full" :disabled="busy">{{ busy ? 'Wird gespeichert…' : 'Adresse speichern' }}</button>
      </form>

      <!-- Schritt 3: Code -->
      <form v-else-if="step === 'verify'" class="space-y-3" @submit.prevent="verify">
        <p class="gate-text">
          An <b>{{ account?.email || email }}</b> ist ein sechsstelliger Code unterwegs. Bitte hier eingeben.
        </p>
        <input v-model="code" class="input gate-code" inputmode="numeric" maxlength="6" pattern="[0-9]{6}"
               autocomplete="one-time-code" required aria-label="Bestätigungscode">
        <p v-if="info" class="gate-hint">{{ info }}</p>
        <p v-if="error" class="gate-error">{{ error }}</p>
        <button class="btn btn-primary w-full" :disabled="busy">{{ busy ? 'Wird geprüft…' : 'Bestätigen' }}</button>
        <div class="flex justify-between text-sm">
          <button type="button" class="btn btn-ghost btn-sm" :disabled="busy" @click="resend">Code erneut senden</button>
          <button type="button" class="btn btn-ghost btn-sm" @click="step = 'email'">Adresse ändern</button>
        </div>
      </form>

      <!-- Kein Mailversand: Adresse gespeichert, Bestätigung folgt später -->
      <div v-else-if="step === 'pending'" class="space-y-3">
        <p class="gate-text">
          Die Adresse ist gespeichert. Bestätigt wird sie per Code, sobald auf diesem Server der
          Mailversand eingerichtet ist.
        </p>
        <router-link v-if="auth.isAdmin" to="/notifications/mail" class="btn btn-primary w-full" @click="dismiss">
          Mailversand jetzt einrichten
        </router-link>
        <button class="btn btn-secondary w-full" @click="dismiss">Weiter</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()

const account = ref(null)
const step = ref('')
const dismissed = ref(false)
const busy = ref(false)
const error = ref('')
const info = ref('')
const current = ref('')
const next = ref('')
const repeat = ref('')
const email = ref('')
const code = ref('')

const visible = computed(() => !dismissed.value && !!step.value)

function decide() {
  const a = account.value
  if (!a) { step.value = ''; return }
  if (a.must_change_password && a.auth_source === 'local') step.value = 'password'
  else if (a.needs_email) step.value = 'email'
  else if (!a.email_verified && a.mail_ready) step.value = 'verify'
  else step.value = ''
}

async function load() {
  try {
    account.value = await auth.api('/api/auth/account')
    email.value = account.value.email || ''
    decide()
  } catch {
    account.value = null
  }
}

async function savePassword() {
  error.value = ''
  if (next.value !== repeat.value) { error.value = 'Die beiden neuen Passwörter stimmen nicht überein.'; return }
  busy.value = true
  try {
    const data = await auth.api('/api/auth/password/change', {
      method: 'POST', body: { current_password: current.value, new_password: next.value },
    })
    auth.setToken(data.access_token)
    current.value = next.value = repeat.value = ''
    await load()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function saveEmail() {
  error.value = ''
  busy.value = true
  try {
    const result = await auth.api('/api/auth/email', { method: 'POST', body: { email: email.value } })
    await load()
    if (!result.sent && !result.verified) {
      step.value = account.value?.mail_ready ? 'verify' : 'pending'
      info.value = result.message || ''
    }
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function verify() {
  error.value = ''
  busy.value = true
  try {
    await auth.api('/api/auth/email/verify', { method: 'POST', body: { code: code.value } })
    code.value = ''
    await load()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function resend() {
  error.value = ''
  info.value = ''
  try {
    const result = await auth.api('/api/auth/email/resend', { method: 'POST' })
    info.value = result.message || 'Ein neuer Code ist unterwegs.'
  } catch (e) {
    error.value = e.message
  }
}

function dismiss() {
  dismissed.value = true
}

onMounted(load)
// Nach dem Einrichten des Mailversands erneut prüfen (dann kann bestätigt werden).
watch(() => route.fullPath, () => { if (!step.value || step.value === 'pending') load() })
</script>

<style scoped>
.gate-backdrop {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  background-color: var(--overlay);
}

.gate-card {
  width: 100%;
  max-width: 28rem;
  padding: 1.5rem;
}

.gate-title {
  font-size: 1.125rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
  color: var(--color-text-primary);
}

.gate-text {
  font-size: 0.875rem;
  color: var(--color-text-secondary);
}

.gate-label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.8125rem;
  color: var(--color-text-secondary);
}

.gate-hint {
  font-size: 0.75rem;
  color: var(--color-text-muted);
}

.gate-error {
  font-size: 0.8125rem;
  color: var(--color-danger);
}

.gate-code {
  font-size: 1.5rem;
  letter-spacing: 0.5rem;
  text-align: center;
}
</style>

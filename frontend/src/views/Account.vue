<!-- ==============================================================================
     Name:        Phydran6
     Kontakt:     Phydran6
     Changelog:   ../../../CHANGELOG/frontend.md
     Beschreibung: LogBot - Mein Konto: E-Mail-Adresse und Passwort.
     ============================================================================== -->
<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2 class="page-title">E-Mail & Passwort</h2>
        <p class="page-subtitle">Die E-Mail-Adresse ist Pflicht: für den Passwort-Reset, die Anmeldung in der App und Meldungen.</p>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <!-- E-Mail -->
      <div class="card">
        <div class="card-header">
          <span class="card-title">E-Mail-Adresse</span>
          <span v-if="account" class="badge" :class="account.email_verified ? 'badge-success' : 'badge-warning'">
            {{ account.email_verified ? 'bestätigt' : (account.email ? 'nicht bestätigt' : 'fehlt') }}
          </span>
        </div>
        <div class="card-body space-y-3">
          <label class="label">Adresse<input v-model="email" type="email" class="input w-full" autocomplete="email"></label>
          <label v-if="account?.email_verified && account?.auth_source === 'local'" class="label">Aktuelles Passwort (zum Ändern einer bestätigten Adresse)
            <input v-model="emailPassword" type="password" class="input w-full" autocomplete="current-password">
          </label>
          <button class="btn btn-primary btn-sm" :disabled="busy" @click="saveEmail">Speichern und Code anfordern</button>
          <div v-if="account && account.email && !account.email_verified && account.mail_ready" class="flex gap-2 items-center flex-wrap">
            <input v-model="code" class="input" inputmode="numeric" maxlength="6" placeholder="6-stelliger Code" style="width: 10rem">
            <button class="btn btn-secondary btn-sm" :disabled="busy || code.length !== 6" @click="verify">Bestätigen</button>
            <button class="btn btn-ghost btn-sm" @click="resend">Code erneut senden</button>
          </div>
          <p v-if="account && !account.mail_ready" class="hint">Bestätigt wird per Code, sobald der Mailversand eingerichtet ist.</p>
          <p v-if="emailMessage" class="text-sm" :style="{ color: emailError ? 'var(--color-danger)' : 'var(--color-success)' }">{{ emailMessage }}</p>
        </div>
      </div>

      <!-- Passwort -->
      <div class="card">
        <div class="card-header"><span class="card-title">Passwort ändern</span></div>
        <div class="card-body">
          <p v-if="account && account.auth_source !== 'local'" class="text-sm" style="color: var(--color-text-muted)">
            Dieses Konto meldet sich über {{ account.auth_source === 'ldap' ? 'das Verzeichnis (LDAP)' : 'Single Sign-on' }} an – ein Passwort gibt es hier nicht.
          </p>
          <form v-else class="space-y-3" @submit.prevent="changePassword">
            <label class="label">Aktuelles Passwort<input v-model="current" type="password" class="input w-full" autocomplete="current-password" required></label>
            <label class="label">Neues Passwort<input v-model="next" type="password" class="input w-full" autocomplete="new-password" minlength="8" required></label>
            <label class="label">Wiederholen<input v-model="repeat" type="password" class="input w-full" autocomplete="new-password" minlength="8" required></label>
            <p class="hint">Mindestens 8 Zeichen, ein Großbuchstabe, eine Ziffer. Alle anderen Sitzungen werden beendet.</p>
            <button class="btn btn-primary btn-sm" :disabled="busy">Passwort ändern</button>
            <p v-if="pwMessage" class="text-sm" :style="{ color: pwError ? 'var(--color-danger)' : 'var(--color-success)' }">{{ pwMessage }}</p>
          </form>
        </div>
      </div>

      <!-- Sitzungen -->
      <div class="card">
        <div class="card-header"><span class="card-title">Sitzungen</span></div>
        <div class="card-body space-y-2">
          <p class="text-sm" style="color: var(--color-text-secondary)">
            Ein Handy verloren, an einem fremden Rechner angemeldet geblieben? Damit werden alle
            Anmeldungen dieses Kontos beendet – auch die App und dieses Fenster.
          </p>
          <button class="btn btn-danger btn-sm" @click="logoutAll">Überall abmelden</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const account = ref(null)
const email = ref('')
const emailPassword = ref('')
const code = ref('')
const current = ref('')
const next = ref('')
const repeat = ref('')
const busy = ref(false)
const emailMessage = ref('')
const emailError = ref(false)
const pwMessage = ref('')
const pwError = ref(false)

async function load() {
  account.value = await auth.api('/api/auth/account')
  email.value = account.value.email
}

async function saveEmail() {
  busy.value = true
  emailMessage.value = ''
  try {
    const result = await auth.api('/api/auth/email', { method: 'POST', body: { email: email.value, current_password: emailPassword.value } })
    emailMessage.value = result.message || 'Gespeichert.'
    emailError.value = false
    emailPassword.value = ''
    await load()
  } catch (e) { emailMessage.value = e.message; emailError.value = true } finally { busy.value = false }
}

async function verify() {
  busy.value = true
  try {
    await auth.api('/api/auth/email/verify', { method: 'POST', body: { code: code.value } })
    emailMessage.value = 'Adresse bestätigt.'
    emailError.value = false
    code.value = ''
    await load()
  } catch (e) { emailMessage.value = e.message; emailError.value = true } finally { busy.value = false }
}

async function resend() {
  try {
    const result = await auth.api('/api/auth/email/resend', { method: 'POST' })
    emailMessage.value = result.message || 'Neuer Code ist unterwegs.'
    emailError.value = false
  } catch (e) { emailMessage.value = e.message; emailError.value = true }
}

async function changePassword() {
  pwMessage.value = ''
  if (next.value !== repeat.value) { pwMessage.value = 'Die beiden neuen Passwörter stimmen nicht überein.'; pwError.value = true; return }
  busy.value = true
  try {
    const data = await auth.api('/api/auth/password/change', { method: 'POST', body: { current_password: current.value, new_password: next.value } })
    auth.setToken(data.access_token)
    current.value = next.value = repeat.value = ''
    pwMessage.value = 'Passwort geändert. Andere Sitzungen sind beendet.'
    pwError.value = false
  } catch (e) { pwMessage.value = e.message; pwError.value = true } finally { busy.value = false }
}

async function logoutAll() {
  if (!confirm('Wirklich auf allen Geräten abmelden?')) return
  await auth.api('/api/auth/logout-all', { method: 'POST' })
  auth.logout()
  router.push('/login')
}

onMounted(load)
</script>

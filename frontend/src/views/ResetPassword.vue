<!-- ==============================================================================
     Name:        Phydran6
     Kontakt:     Phydran6
     Changelog:   ../../../CHANGELOG/frontend.md
     Beschreibung: LogBot - Neues Passwort über den Link aus der Mail.
     ============================================================================== -->
<template>
  <div class="reset-page">
    <div class="card reset-card">
      <div class="card-body space-y-4">
        <h1 class="text-xl font-bold">Neues Passwort festlegen</h1>
        <form v-if="!done" class="space-y-3" @submit.prevent="submit">
          <label class="label">Neues Passwort<input v-model="password" type="password" class="input w-full" autocomplete="new-password" minlength="8" required></label>
          <label class="label">Wiederholen<input v-model="repeat" type="password" class="input w-full" autocomplete="new-password" minlength="8" required></label>
          <p class="hint">Mindestens 8 Zeichen, ein Großbuchstabe, eine Ziffer. Danach sind alle bisherigen Anmeldungen beendet.</p>
          <p v-if="error" class="text-sm" style="color: var(--color-danger)">{{ error }}</p>
          <button class="btn btn-primary w-full" :disabled="busy || !token">{{ busy ? 'Wird gespeichert…' : 'Passwort speichern' }}</button>
        </form>
        <div v-else class="space-y-3">
          <p class="text-sm" style="color: var(--color-success)">{{ done }}</p>
          <router-link to="/login" class="btn btn-primary w-full">Zur Anmeldung</router-link>
        </div>
        <p v-if="!token" class="text-sm" style="color: var(--color-danger)">Der Link ist unvollständig. Bitte den Link aus der Mail vollständig öffnen.</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const token = String(route.query.token || '')
const password = ref('')
const repeat = ref('')
const busy = ref(false)
const error = ref('')
const done = ref('')

async function submit() {
  error.value = ''
  if (password.value !== repeat.value) { error.value = 'Die beiden Passwörter stimmen nicht überein.'; return }
  busy.value = true
  try {
    const res = await fetch('/api/auth/password/reset', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, new_password: password.value }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      const detail = Array.isArray(data.detail) ? data.detail.map(d => d.msg).join(' ') : data.detail
      throw new Error(detail || `Fehler ${res.status}`)
    }
    done.value = data.message || 'Das Passwort ist geändert.'
    // Der Token steht in der Adresse - aus dem Verlauf nehmen.
    window.history.replaceState(null, '', '/reset-password')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.reset-page {
  min-height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  background-color: var(--color-bg);
}

.reset-card {
  width: 100%;
  max-width: 26rem;
}
</style>

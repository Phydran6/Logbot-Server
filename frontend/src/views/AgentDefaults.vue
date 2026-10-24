<!-- ==============================================================================
     Name:        Phydran6
     Kontakt:     Phydran6
     Changelog:   ../../../CHANGELOG/frontend.md
     Beschreibung: LogBot - Agents → Grenzen & Vorgaben.

     Was für jedes Gerät gilt, das keine eigenen Werte hat - auch für Geräte,
     die LogBot über die Netzwerksuche selbst eingebunden hat. Container erben
     die Werte ihrer VM. Eigene Werte je Gerät stellt man in der Geräteansicht ein.
     ============================================================================== -->
<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2 class="page-title">Grenzen & Vorgaben</h2>
        <p class="page-subtitle">Damit kein einzelnes System – oder ein geschwätziger Container – die Datenbank füllt.</p>
      </div>
    </div>
    <div class="card max-w-2xl">
      <div class="card-body space-y-4">
        <label class="label">Aufbewahrung pro Gerät (Tage)
          <input v-model.number="form.retention_days" type="number" min="1" max="3650" class="input w-40" placeholder="unbegrenzt">
          <span class="hint">Ältere Zeilen eines Geräts werden stündlich entfernt.</span>
        </label>
        <label class="label">Höchstens so viele Logzeilen pro Gerät
          <input v-model.number="form.retention_max_logs" type="number" min="1000" class="input w-40" placeholder="unbegrenzt">
          <span class="hint">Darüber verschwinden die ältesten zuerst. Gilt je Gerät und je Container.</span>
        </label>
        <label class="label">Drossel: höchstens Logzeilen pro Minute je System
          <input v-model.number="form.ingest_limit_per_minute" type="number" min="10" class="input w-40" placeholder="keine Drossel">
          <span class="hint">Zählt die VM samt ihrer Container zusammen. Was darüber geht, wird verworfen und im Systemtagebuch vermerkt (höchstens einmal pro Stunde).</span>
        </label>
        <p class="hint">Leer = keine Grenze. Eigene Werte je Gerät haben Vorrang (Geräte → Gerät → Aufbewahrung).</p>
        <button class="btn btn-primary btn-sm" :disabled="busy" @click="save">Speichern</button>
        <p v-if="message" class="text-sm" :style="{ color: isError ? 'var(--color-danger)' : 'var(--color-success)' }">{{ message }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const form = ref({ retention_days: null, retention_max_logs: null, ingest_limit_per_minute: null })
const busy = ref(false)
const message = ref('')
const isError = ref(false)

const clean = (v) => (v === '' || v === null || Number.isNaN(v) ? null : v)

async function save() {
  busy.value = true
  try {
    form.value = await auth.api('/api/agents/defaults', { method: 'PUT', body: {
      retention_days: clean(form.value.retention_days), retention_max_logs: clean(form.value.retention_max_logs),
      ingest_limit_per_minute: clean(form.value.ingest_limit_per_minute) } })
    message.value = 'Gespeichert.'
    isError.value = false
  } catch (e) { message.value = e.message; isError.value = true } finally { busy.value = false }
}

onMounted(async () => { form.value = await auth.api('/api/agents/defaults') })
</script>

<!-- ==============================================================================
     Name:        Phydran6
     Kontakt:     Phydran6
     Changelog:   ../../../CHANGELOG/frontend.md
     Beschreibung: LogBot - Agents → Agent-Updates.

     Kommt mit einem Server-Update eine neue Agent-Fassung, entscheidet hier
     die Regel: von Hand ("Jetzt aktualisieren") oder automatisch im
     Wartungsfenster. Jedes Paket ist vom Server unterschrieben, der Agent
     prüft die Unterschrift vor dem Einspielen und fällt bei Problemen auf
     die alte Fassung zurück.
     ============================================================================== -->
<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2 class="page-title">Agent-Updates</h2>
        <p class="page-subtitle">Neue Agent-Fassungen kommen mit jedem Server-Update. Wann sie auf die Geräte gehen, bestimmst du.</p>
      </div>
      <button class="btn btn-ghost btn-sm" :disabled="loading" @click="load"><AppIcon name="refresh" :size="16" /></button>
    </div>

    <p v-if="banner" class="card card-body mb-4 text-sm" :style="{ color: bannerError ? 'var(--color-danger)' : 'var(--color-success)' }">{{ banner }}</p>

    <!-- Kennzahlen -->
    <div v-if="data" class="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-4">
      <div class="stat-card"><span class="stat-label">Aktuelle Fassung</span>
        <span class="text-sm mt-1 block font-mono">Linux {{ data.packages.linux?.version || '–' }}<br>Windows {{ data.packages.windows?.version || '–' }}</span></div>
      <div class="stat-card"><span class="stat-label">Aktuell</span><span class="stat-value" style="color: var(--color-success)">{{ data.counts.current }}</span></div>
      <div class="stat-card"><span class="stat-label">Update verfügbar</span><span class="stat-value" style="color: var(--color-warning)">{{ data.counts.outdated }}</span></div>
      <div class="stat-card"><span class="stat-label">Läuft gerade</span><span class="stat-value">{{ data.counts.running }}</span></div>
      <div class="stat-card"><span class="stat-label">Alte Agents ohne Selbst-Update</span><span class="stat-value">{{ data.counts.legacy }}</span></div>
    </div>

    <!-- Regel -->
    <div v-if="config" class="card mb-4">
      <div class="card-header">
        <span class="card-title">Regel</span>
        <span v-if="config.paused" class="badge badge-danger">angehalten: {{ config.paused_reason || 'von Hand' }}</span>
        <span v-else-if="config.mode === 'auto'" class="badge" :class="data?.in_window_now ? 'badge-success' : 'badge-neutral'">
          {{ data?.in_window_now ? 'Wartungsfenster jetzt offen' : 'außerhalb des Wartungsfensters' }}</span>
      </div>
      <div class="card-body space-y-4">
        <div class="flex flex-wrap gap-2">
          <button v-for="m in MODES" :key="m.id" class="btn btn-sm" :class="config.mode === m.id ? 'btn-primary' : 'btn-secondary'" @click="config.mode = m.id">
            {{ m.label }}
          </button>
        </div>
        <p class="hint">{{ MODES.find(m => m.id === config.mode)?.hint }}</p>
        <div v-if="config.mode === 'auto'" class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="label">Wochentage</label>
            <div class="flex flex-wrap gap-2">
              <label v-for="(day, i) in DAYS" :key="day" class="chip">
                <input type="checkbox" :checked="config.window_days.includes(i)" @change="toggleDay(i)"> {{ day }}
              </label>
            </div>
          </div>
          <div class="flex gap-3 items-end flex-wrap">
            <label class="label">von<input v-model="config.window_start" type="time" class="input"></label>
            <label class="label">bis<input v-model="config.window_end" type="time" class="input"></label>
            <label class="label">Zeitzone<input v-model="config.timezone" class="input" style="width: 11rem"></label>
          </div>
          <label class="label">Höchstens gleichzeitig<input v-model.number="config.max_parallel" type="number" min="1" max="100" class="input w-28"></label>
          <label class="label">Anhalten nach Fehlschlägen<input v-model.number="config.pause_after_failures" type="number" min="0" max="50" class="input w-28">
            <span class="hint">So viele gescheiterte Geräte mit derselben Fassung, dann stoppt die Verteilung und meldet sich (0 = nie).</span></label>
        </div>
        <div class="flex gap-2 flex-wrap">
          <button class="btn btn-primary btn-sm" :disabled="busy" @click="saveConfig">Regel speichern</button>
          <button v-if="config.paused" class="btn btn-secondary btn-sm" @click="resume">Verteilung fortsetzen</button>
        </div>
        <p class="hint">Unterschrift der Pakete: {{ data?.signing_key_fingerprint }}</p>
      </div>
    </div>

    <!-- Geräte -->
    <div class="card">
      <div class="card-header">
        <span class="card-title">Geräte</span>
        <div class="flex gap-2">
          <button class="btn btn-secondary btn-sm" :disabled="!selected.length || busy" @click="request(selected)">Auswahl aktualisieren</button>
          <button class="btn btn-primary btn-sm" :disabled="!data?.counts.outdated || busy" @click="requestAll">Alle veralteten jetzt</button>
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="table w-full">
          <thead><tr><th></th><th>Gerät</th><th>Fassung</th><th>Regel</th><th>Zustand</th><th></th></tr></thead>
          <tbody>
            <tr v-for="a in items" :key="a.id">
              <td><input v-model="selected" type="checkbox" :value="a.id" :disabled="!a.self_update || !a.outdated"></td>
              <td>
                <b>{{ a.hostname }}</b>
                <span class="badge badge-neutral ml-1">{{ a.device_type === 'linux_agent' ? 'Linux' : 'Windows' }}</span>
                <span v-if="!a.is_online" class="badge badge-warning ml-1">offline</span>
              </td>
              <td class="font-mono text-xs">
                {{ a.version || 'unbekannt' }}
                <span v-if="a.outdated" style="color: var(--color-warning)"> → {{ a.target_version }}</span>
              </td>
              <td>
                <select class="select select-sm" :value="a.policy || ''" @change="setPolicy(a, $event.target.value)">
                  <option value="">Vorgabe ({{ POLICY_LABELS[a.effective_policy] }})</option>
                  <option value="manual">immer von Hand</option>
                  <option value="auto">automatisch</option>
                  <option value="never">nie</option>
                </select>
              </td>
              <td class="text-xs">
                <span v-if="!a.self_update" style="color: var(--color-warning)" title="Agent einmal neu installieren - danach aktualisiert er sich selbst.">
                  alte Fassung ohne Selbst-Update – einmal neu installieren
                </span>
                <span v-else-if="!a.remote_update">auf dem Gerät gesperrt</span>
                <span v-else-if="a.requested">angestoßen – beim nächsten Lebenszeichen</span>
                <span v-else :style="{ color: stateColor(a.state.state) }">{{ stateText(a) }}</span>
              </td>
              <td>
                <button v-if="a.self_update && a.outdated && !a.requested" class="btn btn-ghost btn-sm" @click="request([a.id])">Jetzt</button>
                <button v-if="a.requested" class="btn btn-ghost btn-sm" @click="cancel(a.id)">Abbrechen</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import AppIcon from '../components/AppIcon.vue'

const auth = useAuthStore()
const data = ref(null)
const config = ref(null)
const selected = ref([])
const loading = ref(false)
const busy = ref(false)
const banner = ref('')
const bannerError = ref(false)
let timer = null

const MODES = [
  { id: 'manual', label: 'Von Hand', hint: 'Neue Fassungen werden angezeigt; aktualisiert wird erst, wenn du „Jetzt aktualisieren“ klickst.' },
  { id: 'auto', label: 'Automatisch im Wartungsfenster', hint: 'Geräte aktualisieren sich selbst – nur zu den eingestellten Zeiten, gestaffelt, mit Notbremse.' },
  { id: 'off', label: 'Aus', hint: 'Keine Agent-Updates über den Server.' },
]
const DAYS = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
const POLICY_LABELS = { manual: 'von Hand', auto: 'automatisch', never: 'nie' }
const items = computed(() => data.value?.items || [])

function say(text, isError = false) { banner.value = text; bannerError.value = isError }

async function load() {
  loading.value = true
  try {
    data.value = await auth.api('/api/agents/updates')
    if (!busy.value) config.value = { ...data.value.config, window_days: [...data.value.config.window_days] }
  } catch (e) { say(e.message, true) } finally { loading.value = false }
}

function toggleDay(i) {
  const days = config.value.window_days
  config.value.window_days = days.includes(i) ? days.filter(d => d !== i) : [...days, i].sort()
}

async function saveConfig() {
  busy.value = true
  try {
    const { paused_reason, ...body } = config.value
    await auth.api('/api/agents/updates/config', { method: 'PUT', body })
    say('Regel gespeichert.')
  } catch (e) { say(e.message, true) } finally { busy.value = false; load() }
}

async function resume() {
  config.value.paused = false
  await saveConfig()
}

async function request(ids) {
  busy.value = true
  try {
    const result = await auth.api('/api/agents/updates/request', { method: 'POST', body: { agent_ids: ids } })
    const skipped = result.skipped.map(s => `${s.hostname}: ${s.reason}`).join(' · ')
    say(result.message + (skipped ? ` Übersprungen: ${skipped}` : ''))
    selected.value = []
  } catch (e) { say(e.message, true) } finally { busy.value = false; load() }
}

async function requestAll() {
  busy.value = true
  try {
    const result = await auth.api('/api/agents/updates/request', { method: 'POST', body: { all_outdated: true } })
    say(result.message)
  } catch (e) { say(e.message, true) } finally { busy.value = false; load() }
}

async function cancel(id) {
  await auth.api('/api/agents/updates/cancel', { method: 'POST', body: { agent_ids: [id] } })
  load()
}

async function setPolicy(agent, value) {
  try {
    await auth.api(`/api/agents/${agent.id}/update-policy`, { method: 'PUT', body: { policy: value || null } })
    load()
  } catch (e) { say(e.message, true) }
}

const STATE_TEXT = { offered: 'Paket angeboten', downloading: 'lädt', installing: 'installiert', done: 'aktuell', failed: 'gescheitert', pending: 'wartet' }
function stateText(a) {
  const s = a.state || {}
  if (!a.outdated && (!s.state || s.state === 'done')) return s.message || 'aktuell'
  const base = STATE_TEXT[s.state] || ''
  return [base, s.message || s.reason].filter(Boolean).join(' – ') || 'Update verfügbar'
}
const stateColor = (s) => ({ failed: 'var(--color-danger)', done: 'var(--color-success)' }[s] || 'var(--color-text-secondary)')

onMounted(() => {
  load()
  timer = setInterval(load, 15000)
})
onBeforeUnmount(() => clearInterval(timer))
</script>

<style scoped>
.chip {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.125rem 0.5rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  font-size: 0.8125rem;
}

.select-sm {
  padding-top: 0.25rem;
  padding-bottom: 0.25rem;
  font-size: 0.8125rem;
}
</style>

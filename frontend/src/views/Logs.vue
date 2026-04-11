<!-- ==============================================================================
     Name:        Philipp Fischer
     Kontakt:     p.fischer@itconex.de
     Version:     2026.04.11.00.00.00
     Beschreibung: LogBot - Logs Ansicht mit erweitertem Filter-Panel
     ============================================================================== -->

<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-4">
      <h1 class="text-2xl font-bold" :style="{ color: 'var(--color-text-primary)' }">Logs</h1>
      <div class="flex gap-2">
        <button @click="exportLogs('csv')" class="text-sm px-3 py-1 rounded" :style="buttonSecondaryStyle">CSV</button>
        <button @click="exportLogs('json')" class="text-sm px-3 py-1 rounded" :style="buttonSecondaryStyle">JSON</button>
      </div>
    </div>

    <!-- ================================================================
         FILTER-PANEL
         ================================================================ -->
    <div class="rounded-lg shadow mb-4" :style="cardStyle">
      <!-- Header -->
      <div
        class="flex items-center justify-between px-4 py-3 cursor-pointer select-none border-b"
        :style="{ borderColor: 'var(--color-border)' }"
        @click="filterOpen = !filterOpen"
      >
        <span class="font-semibold text-sm" :style="{ color: 'var(--color-text-primary)' }">
          Filter
          <span v-if="activeFilterCount > 0" class="ml-2 px-2 py-0.5 rounded-full text-xs text-white" :style="{ backgroundColor: 'var(--color-primary)' }">
            {{ activeFilterCount }}
          </span>
        </span>
        <span :style="{ color: 'var(--color-text-muted)' }">{{ filterOpen ? '▲' : '▼' }}</span>
      </div>

      <!-- Felder -->
      <div v-show="filterOpen" class="p-4 space-y-4">
        <!-- Zeile 1: Host, Source, Level, Suche -->
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <!-- Hostname -->
          <div class="flex flex-col gap-1">
            <label class="text-xs font-medium" :style="{ color: 'var(--color-text-muted)' }">Host</label>
            <select v-model="filters.hostname" class="rounded px-3 py-2 text-sm" :style="inputStyle" @change="applyFilters">
              <option value="">Alle Hosts</option>
              <option v-for="h in filterOptions.hostnames" :key="h" :value="h">{{ h }}</option>
            </select>
          </div>

          <!-- Source -->
          <div class="flex flex-col gap-1">
            <label class="text-xs font-medium" :style="{ color: 'var(--color-text-muted)' }">Source / Dienst</label>
            <input
              v-model="filters.source"
              type="text"
              list="source-options"
              placeholder="z.B. sshd, kernel…"
              class="rounded px-3 py-2 text-sm"
              :style="inputStyle"
              @keyup.enter="applyFilters"
            >
            <datalist id="source-options">
              <option v-for="s in filterOptions.sources" :key="s" :value="s" />
            </datalist>
          </div>

          <!-- Level -->
          <div class="flex flex-col gap-1">
            <label class="text-xs font-medium" :style="{ color: 'var(--color-text-muted)' }">Level</label>
            <select v-model="filters.level" class="rounded px-3 py-2 text-sm" :style="inputStyle" @change="applyFilters">
              <option value="">Alle Level</option>
              <option v-for="l in filterOptions.levels" :key="l" :value="l">{{ l }}</option>
            </select>
          </div>

          <!-- Volltextsuche -->
          <div class="flex flex-col gap-1">
            <label class="text-xs font-medium" :style="{ color: 'var(--color-text-muted)' }">Nachricht enthält</label>
            <input
              v-model="filters.search"
              type="text"
              placeholder="Suchbegriff…"
              class="rounded px-3 py-2 text-sm"
              :style="inputStyle"
              @keyup.enter="applyFilters"
            >
          </div>
        </div>

        <!-- Zeile 2: Zeitraum -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div class="flex flex-col gap-1">
            <label class="text-xs font-medium" :style="{ color: 'var(--color-text-muted)' }">Von (Datum & Uhrzeit)</label>
            <input
              v-model="filters.start_date"
              type="datetime-local"
              class="rounded px-3 py-2 text-sm"
              :style="inputStyle"
            >
          </div>
          <div class="flex flex-col gap-1">
            <label class="text-xs font-medium" :style="{ color: 'var(--color-text-muted)' }">Bis (Datum & Uhrzeit)</label>
            <input
              v-model="filters.end_date"
              type="datetime-local"
              class="rounded px-3 py-2 text-sm"
              :style="inputStyle"
            >
          </div>
        </div>

        <!-- Schnellauswahl Zeitraum -->
        <div class="flex flex-wrap gap-2">
          <span class="text-xs" :style="{ color: 'var(--color-text-muted)' }">Schnell:</span>
          <button
            v-for="q in quickRanges" :key="q.label"
            @click="applyQuickRange(q)"
            class="text-xs px-2 py-1 rounded"
            :style="buttonSecondaryStyle"
          >{{ q.label }}</button>
          <button
            v-if="filters.start_date || filters.end_date"
            @click="filters.start_date = ''; filters.end_date = ''"
            class="text-xs px-2 py-1 rounded"
            :style="{ ...buttonSecondaryStyle, color: 'var(--color-danger)' }"
          >Zeitraum löschen</button>
        </div>

        <!-- Aktions-Buttons -->
        <div class="flex gap-2 justify-end pt-1 border-t" :style="{ borderColor: 'var(--color-border)' }">
          <button @click="resetFilters" class="text-sm px-4 py-2 rounded" :style="buttonSecondaryStyle">
            Zurücksetzen
          </button>
          <button
            @click="applyFilters"
            class="text-sm px-4 py-2 rounded text-white"
            :style="{ backgroundColor: 'var(--color-primary)' }"
          >
            Filtern
          </button>
        </div>
      </div>
    </div>

    <!-- Aktive Filter als Chips -->
    <div v-if="activeFilterChips.length" class="flex flex-wrap gap-2 mb-4">
      <span
        v-for="chip in activeFilterChips"
        :key="chip.key"
        class="inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm"
        :style="chipStyle"
      >
        <span class="font-medium">{{ chip.label }}:</span>
        <span>{{ chip.value }}</span>
        <button @click="clearFilter(chip.key)" class="ml-1 leading-none hover:opacity-70 font-bold">✕</button>
      </span>
    </div>

    <!-- Fehler -->
    <div v-if="error" class="rounded px-4 py-3 mb-4 text-sm" :style="errorStyle">{{ error }}</div>

    <!-- ================================================================
         TABELLE
         ================================================================ -->
    <div class="rounded-lg shadow" :style="cardStyle">
      <!-- Tabellen-Header -->
      <div class="px-4 py-3 border-b flex flex-wrap items-center justify-between gap-2" :style="{ borderColor: 'var(--color-border)' }">
        <span class="text-sm" :style="{ color: 'var(--color-text-secondary)' }">
          <template v-if="loading">Lade…</template>
          <template v-else>{{ total.toLocaleString('de-DE') }} Einträge</template>
        </span>
        <div class="flex items-center gap-2">
          <label class="text-xs" :style="{ color: 'var(--color-text-muted)' }">Zeilen:</label>
          <select v-model.number="pageSize" class="rounded px-2 py-1 text-sm" :style="inputStyle" @change="page = 1; loadLogs()">
            <option :value="50">50</option>
            <option :value="100">100</option>
            <option :value="250">250</option>
            <option :value="500">500</option>
          </select>
        </div>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full">
          <thead :style="{ backgroundColor: 'var(--color-surface-elevated)' }">
            <tr>
              <th class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide" :style="{ color: 'var(--color-text-muted)' }">Zeit</th>
              <th class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide" :style="{ color: 'var(--color-text-muted)' }">Host</th>
              <th class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide" :style="{ color: 'var(--color-text-muted)' }">Level</th>
              <th class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide" :style="{ color: 'var(--color-text-muted)' }">Source</th>
              <th class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide" :style="{ color: 'var(--color-text-muted)' }">Nachricht</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="log in logs"
              :key="log.id"
              class="border-t hover-row cursor-pointer"
              :style="{ borderColor: 'var(--color-border)' }"
              @click="showDetail(log)"
            >
              <td class="px-4 py-2.5 text-xs whitespace-nowrap font-mono" :style="{ color: 'var(--color-text-muted)' }">
                {{ formatTime(log.timestamp) }}
              </td>
              <td class="px-4 py-2.5 text-sm font-medium" :style="{ color: 'var(--color-text-primary)' }">
                {{ log.hostname || '–' }}
              </td>
              <td class="px-4 py-2.5">
                <span class="px-2 py-0.5 text-xs rounded-full font-medium" :class="levelBadge(log.level)">
                  {{ log.level || '–' }}
                </span>
              </td>
              <td class="px-4 py-2.5 text-xs" :style="{ color: 'var(--color-text-secondary)' }">
                {{ log.source || '–' }}
              </td>
              <td class="px-4 py-2.5 text-sm" :style="{ color: 'var(--color-text-secondary)', maxWidth: '40vw' }">
                <span class="block truncate">{{ log.message }}</span>
              </td>
            </tr>

            <tr v-if="loading">
              <td colspan="5" class="px-4 py-10 text-center text-sm" :style="{ color: 'var(--color-text-muted)' }">
                <span class="animate-pulse">Lade Logs…</span>
              </td>
            </tr>
            <tr v-else-if="!logs.length">
              <td colspan="5" class="px-4 py-10 text-center text-sm" :style="{ color: 'var(--color-text-muted)' }">
                Keine Logs gefunden – Filter anpassen?
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <div class="px-4 py-3 border-t flex flex-wrap items-center justify-between gap-2" :style="{ borderColor: 'var(--color-border)' }">
        <span class="text-sm" :style="{ color: 'var(--color-text-secondary)' }">
          Seite {{ page }} von {{ Math.max(1, Math.ceil(total / pageSize)) }}
        </span>
        <div class="flex gap-1">
          <button @click="goToPage(1)" :disabled="page <= 1" class="px-2 py-1 rounded text-sm disabled:opacity-40" :style="buttonSecondaryStyle">«</button>
          <button @click="goToPage(page - 1)" :disabled="page <= 1" class="px-3 py-1 rounded text-sm disabled:opacity-40" :style="buttonSecondaryStyle">‹ Zurück</button>
          <button @click="goToPage(page + 1)" :disabled="page * pageSize >= total" class="px-3 py-1 rounded text-sm disabled:opacity-40" :style="buttonSecondaryStyle">Weiter ›</button>
          <button @click="goToPage(Math.ceil(total / pageSize))" :disabled="page * pageSize >= total" class="px-2 py-1 rounded text-sm disabled:opacity-40" :style="buttonSecondaryStyle">»</button>
        </div>
      </div>
    </div>

    <!-- ================================================================
         DETAIL-MODAL
         ================================================================ -->
    <div
      v-if="selectedLog"
      class="fixed inset-0 flex items-center justify-center p-4 z-50"
      style="background: rgba(0,0,0,0.6)"
      @click.self="selectedLog = null"
    >
      <div class="rounded-lg shadow-xl w-full max-w-2xl max-h-[85vh] overflow-auto" :style="cardStyle">
        <div class="sticky top-0 px-5 py-4 border-b flex items-center justify-between" :style="{ backgroundColor: 'var(--color-surface)', borderColor: 'var(--color-border)' }">
          <div class="flex items-center gap-3">
            <span class="px-2 py-0.5 text-xs rounded-full font-medium" :class="levelBadge(selectedLog.level)">{{ selectedLog.level }}</span>
            <span class="font-semibold" :style="{ color: 'var(--color-text-primary)' }">{{ selectedLog.source }}</span>
            <span class="text-sm" :style="{ color: 'var(--color-text-muted)' }">@ {{ selectedLog.hostname }}</span>
          </div>
          <button @click="selectedLog = null" class="text-xl leading-none hover:opacity-60" :style="{ color: 'var(--color-text-muted)' }">✕</button>
        </div>

        <div class="p-5 space-y-4">
          <!-- Meta-Grid -->
          <div class="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
            <div>
              <p class="text-xs mb-0.5" :style="{ color: 'var(--color-text-muted)' }">Zeitstempel</p>
              <p class="font-mono" :style="{ color: 'var(--color-text-primary)' }">{{ formatTimeFull(selectedLog.timestamp) }}</p>
            </div>
            <div>
              <p class="text-xs mb-0.5" :style="{ color: 'var(--color-text-muted)' }">IP-Adresse</p>
              <p class="font-mono" :style="{ color: 'var(--color-text-primary)' }">{{ selectedLog.ip_address || '–' }}</p>
            </div>
            <div>
              <p class="text-xs mb-0.5" :style="{ color: 'var(--color-text-muted)' }">Facility</p>
              <p :style="{ color: 'var(--color-text-primary)' }">{{ facilityName(selectedLog.facility) }}</p>
            </div>
            <div>
              <p class="text-xs mb-0.5" :style="{ color: 'var(--color-text-muted)' }">Log-ID</p>
              <p class="font-mono" :style="{ color: 'var(--color-text-primary)' }">#{{ selectedLog.id }}</p>
            </div>
          </div>

          <!-- Nachricht -->
          <div>
            <p class="text-xs mb-1" :style="{ color: 'var(--color-text-muted)' }">Nachricht</p>
            <pre class="p-3 rounded text-sm whitespace-pre-wrap break-all font-mono leading-relaxed" :style="codeBlockStyle">{{ selectedLog.message }}</pre>
          </div>

          <!-- Raw Message (nur wenn unterschiedlich) -->
          <div v-if="selectedLog.raw_message && selectedLog.raw_message !== selectedLog.message">
            <p class="text-xs mb-1" :style="{ color: 'var(--color-text-muted)' }">Raw (original)</p>
            <pre class="p-3 rounded text-xs whitespace-pre-wrap break-all font-mono leading-relaxed overflow-x-auto" :style="codeBlockStyle">{{ selectedLog.raw_message }}</pre>
          </div>

          <!-- Extra-Daten -->
          <div v-if="selectedLog.extra_data && Object.keys(selectedLog.extra_data).length">
            <p class="text-xs mb-1" :style="{ color: 'var(--color-text-muted)' }">Zusatzdaten</p>
            <pre class="p-3 rounded text-xs font-mono whitespace-pre-wrap" :style="codeBlockStyle">{{ JSON.stringify(selectedLog.extra_data, null, 2) }}</pre>
          </div>

          <!-- Schnell-Filter Buttons -->
          <div class="flex flex-wrap gap-2 pt-2 border-t" :style="{ borderColor: 'var(--color-border)' }">
            <button @click="filterByHost(selectedLog.hostname)" class="text-xs px-3 py-1 rounded" :style="buttonSecondaryStyle">
              Nur Host: {{ selectedLog.hostname }}
            </button>
            <button v-if="selectedLog.source" @click="filterBySource(selectedLog.source)" class="text-xs px-3 py-1 rounded" :style="buttonSecondaryStyle">
              Nur Source: {{ selectedLog.source }}
            </button>
            <button v-if="selectedLog.level" @click="filterByLevel(selectedLog.level)" class="text-xs px-3 py-1 rounded" :style="buttonSecondaryStyle">
              Nur Level: {{ selectedLog.level }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const route = useRoute()

const logs = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(100)
const loading = ref(false)
const selectedLog = ref(null)
const error = ref('')
const filterOpen = ref(true)

const filters = ref({
  hostname: '',
  source: '',
  level: '',
  search: '',
  start_date: '',
  end_date: '',
})

const filterOptions = ref({ hostnames: [], sources: [], levels: [] })

// Schnell-Zeitraum-Auswahl
const quickRanges = [
  { label: 'Letzte 15 Min', minutes: 15 },
  { label: 'Letzte Stunde', minutes: 60 },
  { label: 'Letzte 6 h', minutes: 360 },
  { label: 'Letzte 24 h', minutes: 1440 },
  { label: 'Letzte 7 Tage', minutes: 10080 },
]

// ── Computed ─────────────────────────────────────────────────────────────────

const cardStyle = computed(() => ({
  backgroundColor: 'var(--color-surface)',
  borderColor: 'var(--color-border)',
}))
const inputStyle = computed(() => ({
  backgroundColor: 'var(--color-surface-elevated)',
  border: '1px solid var(--color-border)',
  color: 'var(--color-text-primary)',
}))
const buttonSecondaryStyle = computed(() => ({
  backgroundColor: 'var(--color-surface-elevated)',
  border: '1px solid var(--color-border)',
  color: 'var(--color-text-primary)',
}))
const codeBlockStyle = computed(() => ({
  backgroundColor: 'var(--color-surface-elevated)',
  color: 'var(--color-text-primary)',
}))
const chipStyle = computed(() => ({
  backgroundColor: 'var(--color-surface-elevated)',
  border: '1px solid var(--color-primary)',
  color: 'var(--color-text-primary)',
}))
const errorStyle = computed(() => ({
  backgroundColor: 'var(--color-surface-elevated)',
  border: '1px solid var(--color-danger)',
  color: 'var(--color-danger)',
}))

const activeFilterChips = computed(() => {
  const chips = []
  const f = filters.value
  if (f.hostname) chips.push({ key: 'hostname', label: 'Host', value: f.hostname })
  if (f.source)   chips.push({ key: 'source',   label: 'Source', value: f.source })
  if (f.level)    chips.push({ key: 'level',     label: 'Level', value: f.level })
  if (f.search)   chips.push({ key: 'search',    label: 'Suche', value: f.search })
  if (f.start_date) chips.push({ key: 'start_date', label: 'Von', value: f.start_date.replace('T', ' ') })
  if (f.end_date)   chips.push({ key: 'end_date',   label: 'Bis', value: f.end_date.replace('T', ' ') })
  return chips
})

const activeFilterCount = computed(() => activeFilterChips.value.length)

// ── Lifecycle ────────────────────────────────────────────────────────────────

onMounted(() => {
  // URL-Parameter übernehmen (z.B. von Agent-Karte)
  if (route.query.hostname) filters.value.hostname = route.query.hostname
  loadFilterOptions()
  loadLogs()
})

// ── Methoden ─────────────────────────────────────────────────────────────────

async function loadFilterOptions() {
  try {
    filterOptions.value = await authStore.api('/api/logs/filter-options')
  } catch {}
}

function applyFilters() {
  page.value = 1
  loadLogs()
}

function resetFilters() {
  filters.value = { hostname: '', source: '', level: '', search: '', start_date: '', end_date: '' }
  page.value = 1
  loadLogs()
}

function clearFilter(key) {
  filters.value[key] = ''
  applyFilters()
}

function goToPage(n) {
  page.value = n
  loadLogs()
}

function applyQuickRange(q) {
  const now = new Date()
  const from = new Date(now.getTime() - q.minutes * 60_000)
  filters.value.start_date = toLocalDatetimeInput(from)
  filters.value.end_date   = toLocalDatetimeInput(now)
  applyFilters()
}

function toLocalDatetimeInput(d) {
  // Gibt "YYYY-MM-DDTHH:MM" in Lokalzeit zurück (für datetime-local input)
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadLogs() {
  loading.value = true
  error.value = ''
  try {
    const p = new URLSearchParams({ page: page.value, page_size: pageSize.value })
    const f = filters.value
    if (f.hostname)   p.append('hostname', f.hostname)
    if (f.source)     p.append('source', f.source)
    if (f.level)      p.append('level', f.level)
    if (f.search)     p.append('search', f.search)
    if (f.start_date) p.append('start_date', new Date(f.start_date).toISOString())
    if (f.end_date)   p.append('end_date', new Date(f.end_date).toISOString())

    const data = await authStore.api(`/api/logs?${p}`)
    logs.value  = data.items
    total.value = data.total
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function showDetail(log) {
  try {
    selectedLog.value = await authStore.api(`/api/logs/${log.id}`)
  } catch {}
}

function filterByHost(hostname) {
  selectedLog.value = null
  filters.value.hostname = hostname
  applyFilters()
}
function filterBySource(source) {
  selectedLog.value = null
  filters.value.source = source
  applyFilters()
}
function filterByLevel(level) {
  selectedLog.value = null
  filters.value.level = level
  applyFilters()
}

function exportLogs(format) {
  const p = new URLSearchParams({ format })
  const f = filters.value
  if (f.hostname) p.append('hostname', f.hostname)
  if (f.source)   p.append('source', f.source)
  if (f.level)    p.append('level', f.level)
  if (f.search)   p.append('search', f.search)
  window.open(`/api/logs/export?${p}`, '_blank')
}

// ── Formatierung ─────────────────────────────────────────────────────────────

function formatTime(ts) {
  if (!ts) return '–'
  return new Date(ts).toLocaleString('de-DE', {
    day: '2-digit', month: '2-digit', year: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

function formatTimeFull(ts) {
  if (!ts) return '–'
  return new Date(ts).toLocaleString('de-DE', {
    weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

const FACILITY_NAMES = {
  0: 'kern', 1: 'user', 2: 'mail', 3: 'daemon', 4: 'auth', 5: 'syslog',
  6: 'lpr', 7: 'news', 8: 'uucp', 9: 'cron', 10: 'authpriv', 11: 'ftp',
  16: 'local0', 17: 'local1', 18: 'local2', 19: 'local3',
  20: 'local4', 21: 'local5', 22: 'local6', 23: 'local7',
}
function facilityName(f) {
  if (f == null) return '–'
  return FACILITY_NAMES[f] ? `${FACILITY_NAMES[f]} (${f})` : String(f)
}

function levelBadge(level) {
  const map = {
    emergency: 'bg-red-700 text-white',
    alert:     'bg-red-600 text-white',
    critical:  'bg-red-500 text-white',
    error:     'bg-orange-500 text-white',
    warning:   'bg-yellow-500 text-black',
    notice:    'bg-cyan-500 text-white',
    info:      'bg-blue-500 text-white',
    debug:     'bg-gray-500 text-white',
  }
  return map[(level || '').toLowerCase()] || 'bg-gray-400 text-white'
}
</script>

<style scoped>
.hover-row:hover {
  background-color: var(--color-surface-elevated);
}
</style>

<!-- ==============================================================================
     Name:        Philipp Fischer
     Kontakt:     p.fischer@itconex.de
     Version:     2026.01.30.19.02.15
     Beschreibung: LogBot - Logs Ansicht mit Theme-Support
     ============================================================================== -->

<template>
  <div class="p-6">
    <h1 class="text-2xl font-bold mb-6" :style="{ color: 'var(--color-text-primary)' }">Logs</h1>
    
    <!-- Filter -->
    <div class="rounded-lg shadow p-4 mb-6" :style="cardStyle">
      <div class="grid grid-cols-1 md:grid-cols-6 gap-4">
        <select
          v-model="selectedHostname"
          class="rounded px-3 py-2"
          :style="inputStyle"
          @change="applyFilters"
        >
          <option value="">Alle bekannten Hosts</option>
          <option v-for="h in filterOptions.hostnames" :key="h" :value="h">{{ h }}</option>
        </select>
        <input
          v-model="filters.hostname"
          type="text"
          placeholder="Eigener Host (optional)…"
          class="rounded px-3 py-2"
          :style="inputStyle"
          @keyup.enter="applyFilters"
        >
        <input
          v-model="filters.source"
          type="text"
          list="source-options"
          placeholder="Alle Sources..."
          class="rounded px-3 py-2"
          :style="inputStyle"
          @keyup.enter="applyFilters"
        >
        <datalist id="source-options">
          <option v-for="s in filterOptions.sources" :key="s" :value="s" />
        </datalist>
        <select v-model="filters.level" class="rounded px-3 py-2" :style="inputStyle" @change="applyFilters">
          <option value="">Alle Level</option>
          <option v-for="l in filterOptions.levels" :key="l" :value="l">{{ l }}</option>
        </select>
        <input
          v-model="filters.search"
          type="text"
          placeholder="Suche in Nachricht..."
          class="rounded px-3 py-2"
          :style="inputStyle"
          @keyup.enter="applyFilters"
        >
        <button
          @click="applyFilters"
          class="text-white rounded px-4 py-2 hover:opacity-90"
          :style="{ backgroundColor: 'var(--color-primary)' }"
        >
          Filtern
        </button>
      </div>
    </div>
    
    <!-- Fehlermeldung -->
    <div v-if="error" class="rounded-lg shadow p-4 mb-6 bg-red-100 border border-red-400 text-red-700">
      {{ error }}
    </div>

    <!-- Logs Tabelle -->
    <div class="rounded-lg shadow" :style="cardStyle">
      <div class="p-4 border-b flex justify-between items-center" :style="{ borderColor: 'var(--color-border)' }">
        <span :style="{ color: 'var(--color-text-secondary)' }">{{ total.toLocaleString() }} Logs gefunden</span>
        <div class="flex gap-2">
          <button
            @click="exportLogs('csv')"
            class="text-sm px-3 py-1 rounded"
            :style="buttonSecondaryStyle"
          >
            CSV Export
          </button>
          <button
            @click="exportLogs('json')"
            class="text-sm px-3 py-1 rounded"
            :style="buttonSecondaryStyle"
          >
            JSON Export
          </button>
        </div>
      </div>
      
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead :style="{ backgroundColor: 'var(--color-surface-elevated)' }">
            <tr>
              <th class="px-4 py-3 text-left text-xs font-medium uppercase" :style="{ color: 'var(--color-text-muted)' }">Zeit</th>
              <th class="px-4 py-3 text-left text-xs font-medium uppercase" :style="{ color: 'var(--color-text-muted)' }">Host</th>
              <th class="px-4 py-3 text-left text-xs font-medium uppercase" :style="{ color: 'var(--color-text-muted)' }">Level</th>
              <th class="px-4 py-3 text-left text-xs font-medium uppercase" :style="{ color: 'var(--color-text-muted)' }">Source</th>
              <th class="px-4 py-3 text-left text-xs font-medium uppercase" :style="{ color: 'var(--color-text-muted)' }">Nachricht</th>
            </tr>
          </thead>
          <tbody class="divide-y" :style="{ borderColor: 'var(--color-border)' }">
            <tr 
              v-for="log in logs" 
              :key="log.id" 
              class="hover-row cursor-pointer"
              @click="showDetail(log)"
            >
              <td class="px-4 py-3 text-sm whitespace-nowrap" :style="{ color: 'var(--color-text-secondary)' }">{{ formatTime(log.timestamp) }}</td>
              <td class="px-4 py-3 text-sm" :style="{ color: 'var(--color-text-primary)' }">{{ log.hostname }}</td>
              <td class="px-4 py-3">
                <span class="px-2 py-1 text-xs rounded-full" :class="levelBadge(log.level)">
                  {{ log.level }}
                </span>
              </td>
              <td class="px-4 py-3 text-sm" :style="{ color: 'var(--color-text-secondary)' }">{{ log.source }}</td>
              <td class="px-4 py-3 text-sm truncate max-w-lg" :style="{ color: 'var(--color-text-secondary)' }">{{ log.message }}</td>
            </tr>
            <tr v-if="loading">
              <td colspan="5" class="px-4 py-8 text-center" :style="{ color: 'var(--color-text-muted)' }">
                Laden...
              </td>
            </tr>
            <tr v-else-if="!logs.length">
              <td colspan="5" class="px-4 py-8 text-center" :style="{ color: 'var(--color-text-muted)' }">
                Keine Logs gefunden
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      
      <!-- Pagination -->
      <div class="p-4 border-t flex justify-between items-center" :style="{ borderColor: 'var(--color-border)' }">
        <span class="text-sm" :style="{ color: 'var(--color-text-secondary)' }">
          Seite {{ page }} von {{ Math.ceil(total / pageSize) || 1 }}
        </span>
        <div class="flex gap-2">
          <button
            @click="page--; loadLogs()"
            :disabled="page <= 1"
            class="px-3 py-1 rounded disabled:opacity-50"
            :style="buttonSecondaryStyle"
          >
            ← Zurück
          </button>
          <button
            @click="page++; loadLogs()"
            :disabled="page * pageSize >= total"
            class="px-3 py-1 rounded disabled:opacity-50"
            :style="buttonSecondaryStyle"
          >
            Weiter →
          </button>
        </div>
      </div>
    </div>
    
    <!-- Detail Modal -->
    <div 
      v-if="selectedLog" 
      class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50"
      @click.self="selectedLog = null"
    >
      <div class="rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-auto" :style="cardStyle">
        <div class="p-4 border-b flex justify-between items-center" :style="{ borderColor: 'var(--color-border)' }">
          <h2 class="text-lg font-semibold" :style="{ color: 'var(--color-text-primary)' }">Log Details</h2>
          <button @click="selectedLog = null" class="hover:opacity-70" :style="{ color: 'var(--color-text-muted)' }">✕</button>
        </div>
        <div class="p-4 space-y-4">
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="text-sm" :style="{ color: 'var(--color-text-muted)' }">ID</label>
              <p class="font-mono" :style="{ color: 'var(--color-text-primary)' }">{{ selectedLog.id }}</p>
            </div>
            <div>
              <label class="text-sm" :style="{ color: 'var(--color-text-muted)' }">Zeitstempel</label>
              <p :style="{ color: 'var(--color-text-primary)' }">{{ formatTime(selectedLog.timestamp) }}</p>
            </div>
            <div>
              <label class="text-sm" :style="{ color: 'var(--color-text-muted)' }">Hostname</label>
              <p :style="{ color: 'var(--color-text-primary)' }">{{ selectedLog.hostname }}</p>
            </div>
            <div>
              <label class="text-sm" :style="{ color: 'var(--color-text-muted)' }">IP-Adresse</label>
              <p :style="{ color: 'var(--color-text-primary)' }">{{ selectedLog.ip_address }}</p>
            </div>
            <div>
              <label class="text-sm" :style="{ color: 'var(--color-text-muted)' }">Level</label>
              <p>
                <span :class="levelBadge(selectedLog.level)" class="px-2 py-1 text-xs rounded-full">
                  {{ selectedLog.level }}
                </span>
              </p>
            </div>
            <div>
              <label class="text-sm" :style="{ color: 'var(--color-text-muted)' }">Source</label>
              <p :style="{ color: 'var(--color-text-primary)' }">{{ selectedLog.source }}</p>
            </div>
          </div>
          <div>
            <label class="text-sm" :style="{ color: 'var(--color-text-muted)' }">Nachricht</label>
            <p class="p-3 rounded font-mono text-sm whitespace-pre-wrap" :style="codeBlockStyle">{{ selectedLog.message }}</p>
          </div>
          <div v-if="selectedLog.raw_message">
            <label class="text-sm" :style="{ color: 'var(--color-text-muted)' }">Raw Message</label>
            <p class="p-3 rounded font-mono text-xs whitespace-pre-wrap overflow-x-auto" :style="codeBlockStyle">{{ selectedLog.raw_message }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()

const logs = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 100
const loading = ref(false)
const selectedLog = ref(null)
const error = ref('')

const filters = ref({
  hostname: '',
  source: '',
  level: '',
  search: ''
})

// Auswahlliste bekannter Hosts (zusätzlich zur freien Eingabe)
const selectedHostname = ref('')

const filterOptions = ref({
  hostnames: [],
  sources: [],
  levels: []
})

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

const buttonSecondaryStyle = computed(() => ({
  backgroundColor: 'var(--color-surface-elevated)',
  color: 'var(--color-text-primary)',
  border: '1px solid var(--color-border)'
}))

const codeBlockStyle = computed(() => ({
  backgroundColor: 'var(--color-surface-elevated)',
  color: 'var(--color-text-primary)'
}))

onMounted(() => {
  loadFilterOptions()
  loadLogs()
})

async function loadFilterOptions() {
  try {
    const data = await authStore.api('/api/logs/filter-options')
    filterOptions.value = data
  } catch (e) {
    console.error('Filter-Optionen laden fehlgeschlagen:', e)
  }
}

function applyFilters() {
  page.value = 1
  loadLogs()
}

async function loadLogs() {
  loading.value = true
  error.value = ''
  try {
    const params = new URLSearchParams({
      page: page.value,
      page_size: pageSize
    })
    const hostname = filters.value.hostname || selectedHostname.value
    if (hostname) params.append('hostname', hostname)
    if (filters.value.source) params.append('source', filters.value.source)
    if (filters.value.level) params.append('level', filters.value.level)
    if (filters.value.search) params.append('search', filters.value.search)

    console.log('Log-Filter Request:', `/api/logs?${params}`)
    const data = await authStore.api(`/api/logs?${params}`)
    console.log('Log-Filter Response:', data.total, 'Treffer, Seite', data.page)
    logs.value = data.items
    total.value = data.total
  } catch (e) {
    console.error('Fehler:', e)
    error.value = `Fehler beim Laden: ${e.message}`
  } finally {
    loading.value = false
  }
}

async function showDetail(log) {
  try {
    selectedLog.value = await authStore.api(`/api/logs/${log.id}`)
  } catch (e) {
    console.error('Fehler:', e)
  }
}

function exportLogs(format) {
  const params = new URLSearchParams({ format })
  const hostname = filters.value.hostname || selectedHostname.value
  if (hostname) params.append('hostname', hostname)
  if (filters.value.source) params.append('source', filters.value.source)
  if (filters.value.level) params.append('level', filters.value.level)
  
  window.open(`/api/logs/export?${params}`, '_blank')
}

function formatTime(timestamp) {
  if (!timestamp) return '-'
  return new Date(timestamp).toLocaleString('de-DE')
}

function levelBadge(level) {
  const badges = {
    emergency: 'bg-red-600 text-white',
    alert: 'bg-red-600 text-white',
    critical: 'bg-red-500 text-white',
    error: 'bg-orange-500 text-white',
    warning: 'bg-yellow-500 text-white',
    notice: 'bg-cyan-500 text-white',
    info: 'bg-blue-500 text-white',
    debug: 'bg-gray-500 text-white'
  }
  return badges[level] || 'bg-gray-500 text-white'
}
</script>

<style scoped>
.hover-row:hover {
  background-color: var(--color-surface-elevated);
}

.divide-y > tr {
  border-color: var(--color-border);
}
</style>

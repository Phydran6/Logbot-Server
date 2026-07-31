<!-- ==============================================================================
     Name:        Phydran6
     Kontakt:     Phydran6
     Version:     2026.07.18.16.00.00
     Beschreibung: LogBot - Agents/Geräte Übersicht mit Theme-Support
     ============================================================================== -->

<template>
  <div class="p-6">
    <h1 class="text-2xl font-bold mb-6" :style="{ color: 'var(--color-text-primary)' }">Agents / Geräte</h1>
    
    <!-- Suche -->
    <div class="rounded-lg shadow p-4 mb-6" :style="cardStyle">
      <div class="flex gap-4">
        <input
          v-model="search"
          type="text"
          placeholder="Suche nach Hostname, IP oder MAC..."
          class="flex-1 rounded px-3 py-2"
          :style="inputStyle"
          @keyup.enter="loadAgents"
        >
        <select v-model="deviceType" class="rounded px-3 py-2" :style="inputStyle">
          <option value="">Alle Typen</option>
          <option value="unifi_ap">UniFi AP</option>
          <option value="linux">Linux</option>
          <option value="windows">Windows</option>
          <option value="syslog">Syslog</option>
          <option value="windows_agent">Windows-Agent</option>
          <option value="linux_agent">Linux-Agent</option>
          <option value="unknown">Unbekannt</option>
        </select>
        <button
          @click="loadAgents"
          class="text-white rounded px-4 py-2 hover:opacity-90"
          :style="{ backgroundColor: 'var(--color-primary)' }"
        >
          Suchen
        </button>
      </div>
    </div>
    
    <!-- Agents Grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <!-- Klick auf die Karte oeffnet die Log-Ansicht dieses Geraets -->
      <div
        v-for="agent in agents"
        :key="agent.id"
        class="rounded-lg shadow p-6 hover:shadow-lg transition-shadow cursor-pointer"
        :style="cardStyle"
        :title="`Logs von ${agent.hostname} anzeigen`"
        @click="openDevice(agent)"
      >
        <div class="flex justify-between items-start mb-4">
          <div>
            <h3 class="font-semibold text-lg" :style="{ color: 'var(--color-text-primary)' }">{{ agent.hostname }}</h3>
            <p class="text-sm" :style="{ color: 'var(--color-text-muted)' }">{{ agent.ip_address }}</p>
          </div>
          <span 
            class="px-2 py-1 text-xs rounded-full"
            :class="isOnline(agent) ? 'bg-green-500 text-white' : 'bg-gray-500 text-white'"
          >
            {{ isOnline(agent) ? 'Online' : 'Offline' }}
          </span>
        </div>
        
        <div class="space-y-2 text-sm">
          <div class="flex justify-between">
            <span :style="{ color: 'var(--color-text-muted)' }">Typ:</span>
            <span :style="{ color: 'var(--color-text-primary)' }">{{ typeLabel(agent.device_type) }}</span>
          </div>
          <div v-if="agent.mac_address" class="flex justify-between">
            <span :style="{ color: 'var(--color-text-muted)' }">MAC:</span>
            <span class="font-mono" :style="{ color: 'var(--color-text-primary)' }">{{ agent.mac_address }}</span>
          </div>
          <div class="flex justify-between">
            <span :style="{ color: 'var(--color-text-muted)' }">Zuletzt gesehen:</span>
            <span :style="{ color: 'var(--color-text-primary)' }">{{ formatTime(agent.last_seen) }}</span>
          </div>
          <div class="flex justify-between">
            <span :style="{ color: 'var(--color-text-muted)' }">Erstmals gesehen:</span>
            <span :style="{ color: 'var(--color-text-primary)' }">{{ formatTime(agent.first_seen) }}</span>
          </div>
        </div>
        
        <!-- Metadata wenn vorhanden -->
        <div v-if="agent.metadata && Object.keys(agent.metadata).length" class="mt-4 pt-4 border-t" :style="{ borderColor: 'var(--color-border)' }">
          <p class="text-xs mb-2" :style="{ color: 'var(--color-text-muted)' }">Metadata:</p>
          <div class="text-xs space-y-1">
            <div v-for="(value, key) in agent.metadata" :key="key" class="flex justify-between">
              <span :style="{ color: 'var(--color-text-muted)' }">{{ key }}:</span>
              <span :style="{ color: 'var(--color-text-primary)' }">{{ value }}</span>
            </div>
          </div>
        </div>
        
        <!-- Retention-Anzeige -->
        <div v-if="agent.retention_max_logs || agent.retention_days" class="mt-3 pt-3 border-t text-xs" :style="{ borderColor: 'var(--color-border)', color: 'var(--color-text-muted)' }">
          <span v-if="agent.retention_max_logs">Max {{ agent.retention_max_logs.toLocaleString('de-DE') }} Logs</span>
          <span v-if="agent.retention_max_logs && agent.retention_days"> · </span>
          <span v-if="agent.retention_days">{{ agent.retention_days }} Tage</span>
        </div>

        <!-- Actions -->
        <div class="mt-4 pt-4 border-t flex justify-between items-center" :style="{ borderColor: 'var(--color-border)' }">
          <router-link
            :to="{ name: 'DeviceLogs', params: { hostname: agent.hostname } }"
            class="hover:underline text-sm"
            :style="{ color: 'var(--color-primary)' }"
            @click.stop
          >
            Logs anzeigen →
          </router-link>
          <div class="flex gap-3">
            <button
              @click.stop="openRetention(agent)"
              class="text-xs hover:opacity-70"
              :style="{ color: 'var(--color-text-muted)' }"
              title="Retention-Policy einstellen"
            >⚙ Retention</button>
            <button
              @click.stop="deleteAgent(agent)"
              class="text-sm hover:opacity-70"
              :style="{ color: 'var(--color-danger)' }"
            >Löschen</button>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Leer-Zustand -->
    <div v-if="!loading && !agents.length" class="rounded-lg shadow p-12 text-center" :style="cardStyle">
       <p :style="{ color: 'var(--color-text-muted)' }">Keine Agents gefunden</p>
       <p class="text-sm mt-2" :style="{ color: 'var(--color-text-muted)' }">Agents werden automatisch erstellt wenn Logs empfangen werden</p>
    </div>
    
    <!-- Retention Modal -->
    <div
      v-if="retentionModal.open"
      class="fixed inset-0 flex items-center justify-center p-4 z-50"
      style="background: rgba(0,0,0,0.6)"
      @click.self="retentionModal.open = false"
    >
      <div class="rounded-lg shadow-xl w-full max-w-md" :style="cardStyle">
        <div class="px-5 py-4 border-b flex justify-between items-center" :style="{ borderColor: 'var(--color-border)' }">
          <h2 class="font-semibold" :style="{ color: 'var(--color-text-primary)' }">
            Retention – {{ retentionModal.hostname }}
          </h2>
          <button @click="retentionModal.open = false" :style="{ color: 'var(--color-text-muted)' }">✕</button>
        </div>
        <div class="p-5 space-y-4">
          <p class="text-sm" :style="{ color: 'var(--color-text-muted)' }">
            Leer lassen = kein Limit. Die Policy wird stündlich automatisch durchgesetzt.
          </p>
          <div class="flex flex-col gap-1">
            <label class="text-sm font-medium" :style="{ color: 'var(--color-text-secondary)' }">Max. Logs gesamt</label>
            <input
              v-model.number="retentionModal.max_logs"
              type="number"
              min="1000"
              placeholder="z.B. 50000"
              class="rounded px-3 py-2"
              :style="inputStyle"
            >
          </div>
          <div class="flex flex-col gap-1">
            <label class="text-sm font-medium" :style="{ color: 'var(--color-text-secondary)' }">Logs älter als X Tage löschen</label>
            <input
              v-model.number="retentionModal.days"
              type="number"
              min="1"
              placeholder="z.B. 30"
              class="rounded px-3 py-2"
              :style="inputStyle"
            >
          </div>
          <div v-if="retentionModal.error" class="text-sm px-3 py-2 rounded" :style="{ backgroundColor: 'var(--color-surface-elevated)', color: 'var(--color-danger)', border: '1px solid var(--color-danger)' }">
            {{ retentionModal.error }}
          </div>
          <div class="flex gap-2 justify-end pt-2 border-t" :style="{ borderColor: 'var(--color-border)' }">
            <button @click="retentionModal.open = false" class="px-4 py-2 rounded text-sm" :style="buttonSecondaryStyle">Abbrechen</button>
            <button @click="executeRetention" class="px-4 py-2 rounded text-sm text-white" :style="{ backgroundColor: 'var(--color-warning, #f59e0b)' }">Jetzt bereinigen</button>
            <button @click="saveRetention" class="px-4 py-2 rounded text-sm text-white" :style="{ backgroundColor: 'var(--color-primary)' }">Speichern</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Pagination -->
    <div v-if="total > pageSize" class="mt-6 flex justify-center gap-2">
      <button
        @click="page--; loadAgents()"
        :disabled="page <= 1"
        class="px-4 py-2 rounded disabled:opacity-50"
        :style="buttonSecondaryStyle"
      >
         <- Zurueck
      </button>
      <span class="px-4 py-2" :style="{ color: 'var(--color-text-secondary)' }">Seite {{ page }} von {{ Math.ceil(total / pageSize) }}</span>
      <button
        @click="page++; loadAgents()"
        :disabled="page * pageSize >= total"
        class="px-4 py-2 rounded disabled:opacity-50"
        :style="buttonSecondaryStyle"
      >
         Weiter ->
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const router = useRouter()

const agents = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const loading = ref(false)
const search = ref('')
const deviceType = ref('')
const offlineTimeout = ref(300)

const retentionModal = ref({
  open: false,
  agentId: null,
  hostname: '',
  max_logs: null,
  days: null,
  error: '',
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

onMounted(async () => {
  await loadSettings()
  await loadAgents()
})

async function loadSettings() {
  try {
    const data = await authStore.api('/api/settings')
    if (data.settings?.agent_offline_timeout) {
      offlineTimeout.value = data.settings.agent_offline_timeout
    }
  } catch (e) {
    console.error('Settings laden fehlgeschlagen:', e)
  }
}

async function loadAgents() {
  loading.value = true
  try {
    const params = new URLSearchParams({
      page: page.value,
      page_size: pageSize
    })
    if (search.value) params.append('search', search.value)
    if (deviceType.value) params.append('device_type', deviceType.value)

    const data = await authStore.api(`/api/agents?${params}`)
    agents.value = data.items
    total.value = data.total
  } catch (e) {
    console.error('Fehler:', e)
  } finally {
    loading.value = false
  }
}

  async function deleteAgent(agent) {
  if (!confirm(`Agent "${agent.hostname}" wirklich löschen?`)) return

  try {
    await authStore.api(`/api/agents/${agent.id}`, { method: 'DELETE' })
    loadAgents()
  } catch (e) {
    alert('Fehler: ' + e.message)
  }
}

function openDevice(agent) {
  if (!agent?.hostname) return
  router.push({ name: 'DeviceLogs', params: { hostname: agent.hostname } })
}

function typeLabel(t) {
  const map = {
    syslog: 'Syslog',
    windows_agent: 'Windows-Agent',
    linux_agent: 'Linux-Agent',
    unifi_ap: 'UniFi AP',
    linux: 'Linux',
    windows: 'Windows',
    unknown: 'Unbekannt'
  }
  return map[t] || t || 'Unbekannt'
}

function isOnline(agent) {
  // Bevorzugt Server-Flag; wenn false, erlauben wir einen Client-Fallback (Toleranz bei Zeitdrift)
  if (agent && agent.is_online === true) return true
  const lastSeen = agent?.last_seen
  if (!lastSeen) return false
  const timeoutMs = offlineTimeout.value * 1000
  const cutoff = Date.now() - timeoutMs

  let ts = String(lastSeen).trim()
  // SQLAlchemy liefert oft 'YYYY-MM-DD HH:MM:SS' (ohne 'T' / TZ)
  if (ts.includes(' ')) ts = ts.replace(' ', 'T')
  const hasTZ = /[zZ]|[+-]\d{2}:?\d{2}$/.test(ts)
  if (!hasTZ) ts = `${ts}Z`

  const time = Date.parse(ts)
  if (!Number.isFinite(time)) return false
  const computedOnline = time > cutoff
  return agent?.is_online === false ? computedOnline : computedOnline
}

function formatTime(timestamp) {
  if (!timestamp) return '-'
  return new Date(timestamp).toLocaleString('de-DE')
}

function openRetention(agent) {
  retentionModal.value = {
    open: true,
    agentId: agent.id,
    hostname: agent.hostname,
    max_logs: agent.retention_max_logs || null,
    days: agent.retention_days || null,
    error: '',
  }
}

async function saveRetention() {
  retentionModal.value.error = ''
  try {
    await authStore.api(`/api/agents/${retentionModal.value.agentId}/retention`, {
      method: 'PUT',
      body: {
        retention_max_logs: retentionModal.value.max_logs || null,
        retention_days: retentionModal.value.days || null,
      },
    })
    retentionModal.value.open = false
    loadAgents()
  } catch (e) {
    retentionModal.value.error = e.message
  }
}

async function executeRetention() {
  retentionModal.value.error = ''
  try {
    // Erst speichern, dann sofort ausführen
    await authStore.api(`/api/agents/${retentionModal.value.agentId}/retention`, {
      method: 'PUT',
      body: {
        retention_max_logs: retentionModal.value.max_logs || null,
        retention_days: retentionModal.value.days || null,
      },
    })
    const result = await authStore.api(
      `/api/agents/${retentionModal.value.agentId}/retention/execute`,
      { method: 'POST' }
    )
    retentionModal.value.open = false
    loadAgents()
    alert(`Bereinigung abgeschlossen: ${result.deleted_count} Logs gelöscht.`)
  } catch (e) {
    retentionModal.value.error = e.message
  }
}
</script>




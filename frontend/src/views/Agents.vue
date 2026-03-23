<!-- ==============================================================================
     Name:        Philipp Fischer
     Kontakt:     p.fischer@itconex.de
     Version:     2026.01.30.19.05.33
     Beschreibung: LogBot - Agents/GerÃ¤te Ãœbersicht mit Theme-Support
     ============================================================================== -->

<template>
  <div class="p-6">
    <h1 class="text-2xl font-bold mb-6" :style="{ color: 'var(--color-text-primary)' }">Agents / Geraete</h1>
    
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
      <div 
        v-for="agent in agents"
        :key="agent.id"
        class="rounded-lg shadow p-6 hover:shadow-lg transition-shadow"
        :style="cardStyle"
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
        
        <!-- Actions -->
        <div class="mt-4 pt-4 border-t flex justify-between" :style="{ borderColor: 'var(--color-border)' }">
          <router-link 
            :to="`/logs?hostname=${agent.hostname}`"
            class="hover:underline text-sm"
            :style="{ color: 'var(--color-primary)' }"
          >
            Logs anzeigen ->
          </router-link>
          <button
            @click="deleteAgent(agent)"
            class="text-sm hover:opacity-70"
            :style="{ color: 'var(--color-danger)' }"
          >
             Loeschen
          </button>
        </div>
      </div>
    </div>
    
    <!-- Leer-Zustand -->
    <div v-if="!loading && !agents.length" class="rounded-lg shadow p-12 text-center" :style="cardStyle">
       <p :style="{ color: 'var(--color-text-muted)' }">Keine Agents gefunden</p>
       <p class="text-sm mt-2" :style="{ color: 'var(--color-text-muted)' }">Agents werden automatisch erstellt wenn Logs empfangen werden</p>
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
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()

const agents = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const loading = ref(false)
const search = ref('')
const deviceType = ref('')
const offlineTimeout = ref(300)

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
  if (!confirm(`Agent "${agent.hostname}" wirklich lÃ¶schen?`)) return

  try {
    await authStore.api(`/api/agents/${agent.id}`, { method: 'DELETE' })
    loadAgents()
  } catch (e) {
    alert('Fehler: ' + e.message)
  }
}

function typeLabel(t) {
  const map = {
    syslog: 'Syslog',
    windows_agent: 'Windows-Agent',
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
</script>




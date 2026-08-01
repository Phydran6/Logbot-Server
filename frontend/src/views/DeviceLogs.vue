<!-- ==============================================================================
     Name:        Phydran6
     Kontakt:     Phydran6
     Version:     2026.07.31.21.10.00
     Beschreibung: LogBot - Log-Ansicht fuer EIN Geraet (Kopfdaten + Logliste).
                   Aufruf ueber /devices/<hostname> aus Agents-Uebersicht,
                   Dashboard oder der allgemeinen Logliste.
     ============================================================================== -->

<template>
  <div class="p-6">
    <!-- Kopfzeile -->
    <div class="flex items-center justify-between mb-4 gap-3 flex-wrap">
      <div class="flex items-center gap-3 min-w-0">
        <router-link
          to="/agents"
          class="text-sm hover:underline whitespace-nowrap"
          :style="{ color: 'var(--color-primary)' }"
        >← Geräte</router-link>
        <h1 class="text-2xl font-bold truncate" :style="{ color: 'var(--color-text-primary)' }">{{ hostname }}</h1>
        <span
          v-if="agent"
          class="px-2 py-1 text-xs rounded-full"
          :class="agent.is_online ? 'bg-green-500 text-white' : 'bg-gray-500 text-white'"
        >{{ agent.is_online ? 'Online' : 'Offline' }}</span>
      </div>
      <router-link
        to="/logs"
        class="text-sm hover:underline"
        :style="{ color: 'var(--color-primary)' }"
      >Alle Logs →</router-link>
    </div>

    <!-- Geraete-Steckbrief -->
    <div v-if="agent" class="rounded-lg shadow p-4 mb-4" :style="cardStyle">
      <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 text-sm">
        <div>
          <p class="text-xs mb-0.5" :style="{ color: 'var(--color-text-muted)' }">IP-Adresse</p>
          <p class="font-mono" :style="{ color: 'var(--color-text-primary)' }">{{ agent.ip_address || '–' }}</p>
        </div>
        <div>
          <p class="text-xs mb-0.5" :style="{ color: 'var(--color-text-muted)' }">MAC</p>
          <p class="font-mono" :style="{ color: 'var(--color-text-primary)' }">{{ agent.mac_address || '–' }}</p>
        </div>
        <div>
          <p class="text-xs mb-0.5" :style="{ color: 'var(--color-text-muted)' }">Typ</p>
          <p :style="{ color: 'var(--color-text-primary)' }">{{ typeLabel(agent.device_type) }}</p>
        </div>
        <div>
          <p class="text-xs mb-0.5" :style="{ color: 'var(--color-text-muted)' }">Zuletzt gesehen</p>
          <p :style="{ color: 'var(--color-text-primary)' }">{{ formatTime(agent.last_seen) }}</p>
        </div>
        <div>
          <p class="text-xs mb-0.5" :style="{ color: 'var(--color-text-muted)' }">Erstmals gesehen</p>
          <p :style="{ color: 'var(--color-text-primary)' }">{{ formatTime(agent.first_seen) }}</p>
        </div>
        <div>
          <p class="text-xs mb-0.5" :style="{ color: 'var(--color-text-muted)' }">Logs gespeichert</p>
          <p :style="{ color: 'var(--color-text-primary)' }">
            {{ agent.log_count != null ? agent.log_count.toLocaleString('de-DE') : '–' }}
          </p>
        </div>
      </div>

      <div
        v-if="agent.retention_max_logs || agent.retention_days"
        class="mt-3 pt-3 border-t text-xs"
        :style="{ borderColor: 'var(--color-border)', color: 'var(--color-text-muted)' }"
      >
        Retention:
        <span v-if="agent.retention_max_logs">max. {{ agent.retention_max_logs.toLocaleString('de-DE') }} Logs</span>
        <span v-if="agent.retention_max_logs && agent.retention_days"> · </span>
        <span v-if="agent.retention_days">älter als {{ agent.retention_days }} Tage werden gelöscht</span>
      </div>
    </div>

    <!-- Kein Agent-Eintrag (z.B. Logs von einem inzwischen geloeschten Geraet) -->
    <div v-else-if="!loadingAgent" class="rounded-lg shadow p-4 mb-4 text-sm" :style="cardStyle">
      <p :style="{ color: 'var(--color-text-muted)' }">
        Zu diesem Hostnamen gibt es keinen Agent-Eintrag (mehr). Die gespeicherten Logs werden trotzdem angezeigt.
      </p>
    </div>

    <!-- Logliste, fest auf dieses Geraet -->
    <LogTable :locked-hostname="hostname" />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import LogTable from '../components/LogTable.vue'

const route = useRoute()
const authStore = useAuthStore()

const agent = ref(null)
const loadingAgent = ref(true)

const hostname = computed(() => String(route.params.hostname || ''))

const cardStyle = computed(() => ({
  backgroundColor: 'var(--color-surface)',
  borderColor: 'var(--color-border)',
}))

onMounted(loadAgent)
watch(hostname, loadAgent)

async function loadAgent() {
  loadingAgent.value = true
  agent.value = null
  try {
    // Die Suche liefert Teiltreffer -> exakten Hostnamen selbst heraussuchen.
    const params = new URLSearchParams({ search: hostname.value, page_size: '200' })
    const data = await authStore.api(`/api/agents?${params}`)
    const match = (data.items || []).find(
      a => (a.hostname || '').toLowerCase() === hostname.value.toLowerCase()
    )
    // Detail-Endpoint liefert zusaetzlich log_count und Retention.
    agent.value = match ? await authStore.api(`/api/agents/${match.id}`) : null
  } catch {
    agent.value = null
  } finally {
    loadingAgent.value = false
  }
}

function typeLabel(t) {
  const map = {
    syslog: 'Syslog',
    windows_agent: 'Windows-Agent',
    linux_agent: 'Linux-Agent',
    unifi_ap: 'UniFi AP',
    fritzbox: 'FRITZ!Box',
    linux: 'Linux',
    windows: 'Windows',
    unknown: 'Unbekannt',
  }
  return map[t] || t || 'Unbekannt'
}

function formatTime(ts) {
  if (!ts) return '–'
  return new Date(ts).toLocaleString('de-DE')
}
</script>

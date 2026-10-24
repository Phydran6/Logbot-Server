<!-- ==============================================================================
     Name:        Phydran6
     Kontakt:     Phydran6
     Version:     2026.10.23.12.00.00
     Changelog:   ../../../CHANGELOG/frontend.md
     Beschreibung: LogBot - Log-Ansicht fuer EIN Geraet (Steckbrief + Logliste).
                   Aufruf ueber /devices/<hostname> aus der Geräteliste,
                   dem Dashboard oder der allgemeinen Logliste.
     ============================================================================== -->

<template>
  <div class="page">
    <!-- Kopfzeile -->
    <div class="page-header">
      <div class="min-w-0">
        <!-- Pfad im Baum: Geräte › VM › Container -->
        <nav class="crumbs text-sm" aria-label="Pfad">
          <router-link to="/agents" class="link inline-flex items-center gap-1"><AppIcon name="chevronLeft" :size="14" /> Geräte</router-link>
          <template v-if="isContainer">
            <span>›</span>
            <router-link :to="{ name: 'DeviceLogs', params: { hostname: parentName } }" class="link">{{ parentName }}</router-link>
            <span v-if="container?.compose_project">› {{ container.compose_project }}</span>
          </template>
        </nav>
        <div class="flex items-center gap-3 mt-1">
          <h2 class="page-title truncate">
            <template v-if="isContainer"><span class="kind-tag">Container</span> {{ containerName }}</template>
            <template v-else>{{ hostname }}</template>
          </h2>
          <span v-if="agent" class="badge" :class="agent.is_online ? 'badge-success' : 'badge-neutral'">
            <span class="status-dot" :class="agent.is_online ? 'status-dot-online' : 'status-dot-offline'" />
            {{ agent.is_online ? 'Online' : 'Offline' }}
          </span>
        </div>
      </div>
      <div class="flex gap-2 items-center">
        <label v-if="!isContainer && childrenCount" class="flex items-center gap-2 text-sm">
          <input v-model="withChildren" type="checkbox"> mit Logs der {{ childrenCount }} Container
        </label>
        <router-link to="/logs" class="btn btn-secondary btn-sm">Alle Logs →</router-link>
      </div>
    </div>

    <!-- Container: zu welcher VM gehört er? -->
    <div v-if="isContainer" class="card mb-4 parent-note">
      <div class="card-body text-sm">
        Läuft auf <router-link :to="{ name: 'DeviceLogs', params: { hostname: parentName } }" class="link font-semibold">{{ parentName }}</router-link>
        – die VM ist die liefernde Instanz, dieser Container eine eigene Log-Instanz darunter.
        <span v-if="container?.image"> Image <code>{{ container.image }}</code>.</span>
        <span v-if="container?.compose_service"> Dienst „{{ container.compose_service }}“ im Compose-Projekt „{{ container.compose_project }}“.</span>
      </div>
    </div>

    <!-- Steckbrief -->
    <div v-if="agent" class="card mb-4">
      <div class="card-body">
        <dl class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <div v-for="fact in facts" :key="fact.label">
            <dt class="fact-label">{{ fact.label }}</dt>
            <dd class="fact-value" :class="fact.mono ? 'font-mono' : ''">{{ fact.value }}</dd>
          </div>
        </dl>

        <p v-if="agent.retention_max_logs || agent.retention_days" class="retention-note">
          <AppIcon name="trash" :size="13" />
          Aufbewahrung:
          <span v-if="agent.retention_max_logs">max. {{ agent.retention_max_logs.toLocaleString('de-DE') }} Logs</span>
          <span v-if="agent.retention_max_logs && agent.retention_days">·</span>
          <span v-if="agent.retention_days">älter als {{ agent.retention_days }} Tage werden gelöscht</span>
        </p>
      </div>
    </div>

    <!-- Kein Agent-Eintrag (z.B. Logs eines inzwischen geloeschten Geraets) -->
    <div v-else-if="!loadingAgent" class="card mb-4">
      <div class="card-body text-sm" style="color: var(--color-text-muted)">
        Zu diesem Hostnamen gibt es keinen Geräte-Eintrag (mehr). Die gespeicherten Logs werden trotzdem angezeigt.
      </div>
    </div>

    <!-- Logliste, fest auf dieses Geraet -->
    <LogTable :locked-hostname="hostname" :with-children="withChildren" />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import LogTable from '../components/LogTable.vue'
import AppIcon from '../components/AppIcon.vue'

const route = useRoute()
const authStore = useAuthStore()

const agent = ref(null)
const loadingAgent = ref(true)

const hostname = computed(() => {
  const raw = route.params.hostname
  return Array.isArray(raw) ? raw.join('/') : String(raw || '')
})
const isContainer = computed(() => hostname.value.includes('/'))
const parentName = computed(() => hostname.value.split('/')[0])
const containerName = computed(() => hostname.value.split('/').slice(1).join('/'))
const container = computed(() => agent.value?.extra_data?.container || null)
const childrenCount = computed(() => agent.value?.children_count || 0)
const withChildren = ref(false)

const facts = computed(() => {
  const a = agent.value
  if (!a) return []
  return [
    { label: 'IP-Adresse', value: a.ip_address || '–', mono: true },
    { label: 'MAC', value: a.mac_address || '–', mono: true },
    { label: 'Art', value: typeLabel(a.device_type) },
    { label: 'Zuletzt gesehen', value: formatTime(a.last_seen) },
    { label: 'Erstmals gesehen', value: formatTime(a.first_seen) },
    { label: 'Logs gespeichert', value: a.log_count != null ? a.log_count.toLocaleString('de-DE') : '–' },
    ...(a.agent_version ? [{ label: 'Agent-Fassung', value: a.agent_version, mono: true }] : []),
    ...(a.extra_data?.docker?.installed ? [{ label: 'Docker', value: `${a.extra_data.docker.engine || 'ja'}${a.extra_data.docker.compose ? ' · Compose ' + a.extra_data.docker.compose : ''}` }] : []),
    ...(a.extra_data?.container ? [
      { label: 'Zustand', value: [a.extra_data.container.state, a.extra_data.container.health].filter(Boolean).join(' · ') || '–' },
      { label: 'Neustarts', value: String(a.extra_data.container.restart_count ?? '–') },
    ] : []),
  ]
})

onMounted(loadAgent)
watch(hostname, loadAgent)

async function loadAgent() {
  loadingAgent.value = true
  agent.value = null
  try {
    // Die Suche liefert Teiltreffer -> exakten Hostnamen selbst heraussuchen.
    const params = new URLSearchParams({ search: hostname.value, page_size: '200', include_children: 'true' })
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
    container: 'Docker-Container',
    unknown: 'Unbekannt',
  }
  return map[t] || t || 'Unbekannt'
}

function formatTime(ts) {
  if (!ts) return '–'
  const value = /[zZ]|[+-]\d{2}:?\d{2}$/.test(ts) ? ts : `${ts}Z`
  return new Date(value).toLocaleString('de-DE')
}
</script>

<style scoped>
.crumbs {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  color: var(--color-text-muted);
}

.kind-tag {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.125rem 0.5rem;
  border-radius: var(--radius-full);
  background-color: var(--primary-soft);
  color: var(--color-primary);
  vertical-align: middle;
}

.parent-note {
  border-left: 4px solid var(--color-primary);
}

.fact-label {
  font-size: 0.6875rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--color-text-muted);
  margin-bottom: 0.125rem;
}

.fact-value {
  font-size: 0.875rem;
  color: var(--color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.retention-note {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  margin-top: 1rem;
  padding-top: 0.875rem;
  border-top: 1px solid var(--color-border);
  font-size: 0.75rem;
  color: var(--color-text-muted);
}
</style>

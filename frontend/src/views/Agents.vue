<!-- ==============================================================================
     Name:        Phydran6
     Kontakt:     Phydran6
     Version:     2026.10.23.12.00.00
     Changelog:   ../../../CHANGELOG/frontend.md
     Beschreibung: LogBot - Geräte als Baum: VM → Compose-Projekt → Container.

     Die VM (bzw. der Rechner) bleibt die eigentliche Instanz - mit Hostnamen,
     IP und Schlüssel. Laufen darauf Docker-Container, hängen sie darunter, je
     Compose-Projekt zusammengefasst. Jeder Container ist eine eigene, lesbare
     Log-Instanz ("docker01/nextcloud-app-1") - Klick öffnet seine Logs.
     ============================================================================== -->

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2 class="page-title">Geräte</h2>
        <p class="page-subtitle">
          {{ hosts.length.toLocaleString('de-DE') }} Systeme · {{ onlineCount }} online ·
          {{ containerCount }} Container
        </p>
      </div>
      <div class="flex gap-2">
        <button class="btn btn-ghost btn-sm" @click="setAll(true)">Alle aufklappen</button>
        <button class="btn btn-ghost btn-sm" @click="setAll(false)">Alle zuklappen</button>
        <button class="btn btn-secondary btn-sm" :disabled="loading" @click="load">
          <AppIcon name="refresh" :size="16" /> Aktualisieren
        </button>
      </div>
    </div>

    <!-- Suche & Filter -->
    <div class="card mb-4">
      <div class="card-body flex flex-col sm:flex-row gap-3">
        <div class="search-wrap flex-1">
          <AppIcon name="search" :size="16" class="search-icon" />
          <input v-model="search" type="text" placeholder="Hostname, IP, Container oder Image…" class="input pl-9">
        </div>
        <select v-model="deviceType" class="select sm:w-56">
          <option value="">Alle Gerätearten</option>
          <option v-for="(label, key) in TYPE_LABELS" :key="key" :value="key">{{ label }}</option>
        </select>
        <label class="flex items-center gap-2 text-sm whitespace-nowrap">
          <input v-model="onlyDocker" type="checkbox"> nur mit Containern
        </label>
      </div>
    </div>

    <div v-if="loading && !hosts.length" class="space-y-3">
      <div v-for="n in 4" :key="n" class="card p-5"><div class="skeleton h-5 w-1/3" /></div>
    </div>

    <div v-else-if="filtered.length" class="space-y-3">
      <article v-for="host in filtered" :key="host.id" class="card host">
        <!-- VM / Rechner -->
        <div class="host-row">
          <button class="expander" :class="{ 'is-open': isOpen(host) }" :disabled="!host.children_count"
                  :aria-label="isOpen(host) ? 'Container zuklappen' : 'Container aufklappen'" @click="toggle(host)">
            <AppIcon name="chevronRight" :size="16" />
          </button>
          <span class="status-dot" :class="host.is_online ? 'status-dot-online' : 'status-dot-offline'" :title="host.is_online ? 'online' : 'offline'" />
          <div class="min-w-0 flex-1">
            <router-link :to="deviceRoute(host.hostname)" class="host-name">{{ host.hostname }}</router-link>
            <p class="host-meta">
              <span class="font-mono">{{ host.ip_address || 'keine IP' }}</span>
              · {{ typeLabel(host.device_type) }}
              <span v-if="host.agent_version"> · Agent {{ host.agent_version }}</span>
              · zuletzt {{ formatTime(host.last_seen) }}
            </p>
          </div>
          <span v-if="host.docker?.installed" class="badge badge-primary" :title="dockerTitle(host)">
            <AppIcon name="container" :size="13" /> Docker {{ host.docker.engine || '' }}
            <template v-if="host.docker.compose"> · Compose</template>
          </span>
          <span v-if="host.children_count" class="badge badge-neutral">{{ runningOf(host) }}/{{ host.children_count }} Container laufen</span>
          <span v-if="host.decommissioned" class="badge badge-warning">abgemeldet</span>
          <div class="flex items-center gap-1">
            <button class="btn-icon" title="Aufbewahrung & Drossel" @click="openRetention(host)"><AppIcon name="settings" :size="16" /></button>
            <button v-if="authStore.isAdmin" class="btn-icon device-delete" title="Gerät löschen" @click="deleteAgent(host)"><AppIcon name="trash" :size="16" /></button>
          </div>
        </div>

        <!-- Container: nach Compose-Projekt -->
        <div v-if="isOpen(host) && host.children_count" class="children">
          <div v-for="project in host.projects" :key="project.name" class="project">
            <p class="project-head">
              <AppIcon name="stacks" :size="14" />
              <b>{{ project.name }}</b>
              <span class="project-meta">Compose-Projekt · {{ project.containers.length }} Container
                <span v-if="project.dir" class="font-mono"> · {{ project.dir }}</span></span>
            </p>
            <ContainerRow v-for="c in project.containers" :key="c.id" :c="c" :route="deviceRoute(c.hostname)" />
          </div>
          <div v-if="host.standalone.length" class="project">
            <p class="project-head"><AppIcon name="container" :size="14" /><b>Einzelne Container</b></p>
            <ContainerRow v-for="c in host.standalone" :key="c.id" :c="c" :route="deviceRoute(c.hostname)" />
          </div>
        </div>
      </article>
    </div>

    <div v-else class="card">
      <div class="empty-state">
        <AppIcon name="agents" :size="30" />
        <p class="empty-state-title">Keine Geräte gefunden</p>
        <p class="text-sm">{{ search || deviceType || onlyDocker ? 'Für diese Suche gibt es keinen Treffer.' : 'Geräte erscheinen automatisch, sobald sie Logs senden.' }}</p>
      </div>
    </div>

    <!-- Aufbewahrung (Modal) -->
    <div v-if="retentionModal.open" class="modal-backdrop" @click.self="retentionModal.open = false">
      <div class="modal max-w-md">
        <div class="card-header">
          <span class="card-title">Aufbewahrung – {{ retentionModal.hostname }}</span>
          <button class="btn-icon" aria-label="Schließen" @click="retentionModal.open = false"><AppIcon name="close" :size="18" /></button>
        </div>
        <div class="card-body space-y-4 overflow-y-auto">
          <p class="text-sm" style="color: var(--color-text-muted)">
            Leer = Vorgabe aus „Agents → Grenzen & Vorgaben“. Container dieses Systems erben die Werte.
          </p>
          <div><label class="label">Höchstzahl gespeicherter Logs</label>
            <input v-model.number="retentionModal.max_logs" type="number" min="1000" placeholder="z. B. 50000" class="input"></div>
          <div><label class="label">Logs löschen, die älter sind als (Tage)</label>
            <input v-model.number="retentionModal.days" type="number" min="1" placeholder="z. B. 30" class="input"></div>
          <div><label class="label">Drossel: höchstens Logzeilen pro Minute (VM + Container)</label>
            <input v-model.number="retentionModal.limit" type="number" min="10" placeholder="Vorgabe" class="input"></div>
          <div v-if="retentionModal.error" class="login-error text-sm">{{ retentionModal.error }}</div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-ghost" @click="retentionModal.open = false">Abbrechen</button>
          <button v-if="authStore.isAdmin" class="btn btn-secondary" @click="executeRetention">Jetzt bereinigen</button>
          <button v-if="authStore.isAdmin" class="btn btn-primary" @click="saveRetention">Speichern</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, ref, resolveComponent } from 'vue'
import { useAuthStore } from '../stores/auth'
import AppIcon from '../components/AppIcon.vue'

const authStore = useAuthStore()

const TYPE_LABELS = {
  linux_agent: 'Linux-Agent', windows_agent: 'Windows-Agent', syslog: 'Syslog', fritzbox: 'FRITZ!Box',
  unifi_ap: 'UniFi AP', linux: 'Linux', windows: 'Windows', unknown: 'Unbekannt',
}
const OPEN_KEY = 'logbot.devicesOpen'

const hosts = ref([])
const loading = ref(false)
const search = ref('')
const deviceType = ref('')
const onlyDocker = ref(false)
const open = ref(readOpen())
const retentionModal = ref({ open: false, agentId: null, hostname: '', max_logs: null, days: null, limit: null, error: '' })

function readOpen() {
  try { return new Set(JSON.parse(localStorage.getItem(OPEN_KEY) || '[]')) } catch { return new Set() }
}
function storeOpen() {
  try { localStorage.setItem(OPEN_KEY, JSON.stringify([...open.value])) } catch { /* nur für diese Sitzung */ }
}

// Eine Zeile für einen Container - klein genug für eine Render-Funktion.
const ContainerRow = defineComponent({
  props: { c: Object, route: Object },
  setup(props) {
    const RouterLink = resolveComponent('router-link')
    return () => {
      const c = props.c
      const state = c.removed ? 'entfernt' : (c.state || 'unbekannt')
      const ok = c.state === 'running'
      return h('div', { class: ['container-row', { 'is-removed': c.removed }] }, [
        h('span', { class: ['status-dot', ok ? 'status-dot-online' : 'status-dot-offline'], title: state }),
        h(RouterLink, { to: props.route, class: 'container-name' }, () => c.name),
        c.compose_service ? h('span', { class: 'badge badge-neutral' }, c.compose_service) : null,
        h('span', { class: 'container-image font-mono', title: c.image }, c.image || ''),
        h('span', { class: 'container-state' }, [state, c.health ? ` · ${c.health}` : '']),
        c.excluded ? h('span', { class: 'badge badge-neutral', title: 'Label de.logbot.collect=false oder LogBot selbst' }, 'nicht erfasst')
          : (!c.logs_readable ? h('span', { class: 'badge badge-warning', title: 'Log-Treiber ohne Lesezugriff' }, 'Logs nicht lesbar') : null),
      ])
    }
  },
})

const containerCount = computed(() => hosts.value.reduce((n, hst) => n + (hst.children_count || 0), 0))
const onlineCount = computed(() => hosts.value.filter(hst => hst.is_online).length)

const filtered = computed(() => {
  const term = search.value.trim().toLowerCase()
  return hosts.value.filter(hst => {
    if (deviceType.value && hst.device_type !== deviceType.value) return false
    if (onlyDocker.value && !hst.children_count) return false
    if (!term) return true
    const containers = [...hst.projects.flatMap(p => p.containers), ...hst.standalone]
    return [hst.hostname, hst.ip_address].some(v => (v || '').toLowerCase().includes(term))
      || containers.some(c => [c.name, c.image, c.compose_service].some(v => (v || '').toLowerCase().includes(term)))
      || hst.projects.some(p => p.name.toLowerCase().includes(term))
  })
})

async function load() {
  loading.value = true
  try {
    hosts.value = (await authStore.api('/api/agents/tree')).items
  } catch (e) {
    console.error('Geräte laden fehlgeschlagen:', e)
  } finally {
    loading.value = false
  }
}

const isOpen = (hst) => open.value.has(hst.id) || (search.value.trim() && hst.children_count)
function toggle(hst) {
  const next = new Set(open.value)
  next.has(hst.id) ? next.delete(hst.id) : next.add(hst.id)
  open.value = next
  storeOpen()
}
function setAll(value) {
  open.value = new Set(value ? hosts.value.filter(hst => hst.children_count).map(hst => hst.id) : [])
  storeOpen()
}

function runningOf(hst) {
  return [...hst.projects.flatMap(p => p.containers), ...hst.standalone].filter(c => c.state === 'running').length
}

function dockerTitle(hst) {
  const d = hst.docker || {}
  return [d.podman ? 'Podman' : 'Docker', d.engine, d.compose ? `Compose ${d.compose}` : 'ohne Compose'].filter(Boolean).join(' · ')
}

const deviceRoute = (hostname) => ({ name: 'DeviceLogs', params: { hostname } })
const typeLabel = (t) => TYPE_LABELS[t] || t || 'Unbekannt'
function formatTime(ts) {
  if (!ts) return '–'
  const value = /[zZ]|[+-]\d{2}:?\d{2}$/.test(ts) ? ts : `${ts}Z`
  return new Date(value).toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' })
}

async function deleteAgent(hst) {
  const extra = hst.children_count ? ` samt ${hst.children_count} Container-Einträgen` : ''
  if (!confirm(`Gerät "${hst.hostname}"${extra} wirklich löschen? Die Logs bleiben erhalten.`)) return
  try {
    await authStore.api(`/api/agents/${hst.id}`, { method: 'DELETE' })
    load()
  } catch (e) {
    alert('Fehler: ' + e.message)
  }
}

async function openRetention(hst) {
  const detail = await authStore.api(`/api/agents/${hst.id}`)
  retentionModal.value = {
    open: true, agentId: hst.id, hostname: hst.hostname, max_logs: detail.retention_max_logs || null,
    days: detail.retention_days || null, limit: detail.ingest_limit_per_minute || null, error: '',
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
        ingest_limit_per_minute: retentionModal.value.limit || null,
      },
    })
    retentionModal.value.open = false
    load()
  } catch (e) {
    retentionModal.value.error = e.message
  }
}

async function executeRetention() {
  retentionModal.value.error = ''
  try {
    await saveRetention()
    const result = await authStore.api(`/api/agents/${retentionModal.value.agentId}/retention/execute`, { method: 'POST' })
    alert(`Bereinigung abgeschlossen: ${result.deleted_count} Logs gelöscht.`)
  } catch (e) {
    retentionModal.value.error = e.message
  }
}

onMounted(load)
</script>

<style scoped>
.search-wrap { position: relative; }

.search-icon {
  position: absolute;
  top: 50%;
  left: 0.75rem;
  transform: translateY(-50%);
  color: var(--color-text-muted);
  pointer-events: none;
}

.host-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.625rem;
  padding: 0.875rem 1rem;
}

.expander {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.75rem;
  height: 1.75rem;
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  transition: transform var(--duration) var(--ease);
}

.expander:disabled { opacity: 0.25; cursor: default; }
.expander.is-open { transform: rotate(90deg); }

.host-name {
  font-weight: 600;
  font-size: 1rem;
  color: var(--color-text-primary);
}

.host-name:hover { color: var(--color-primary); }

.host-meta {
  font-size: 0.75rem;
  color: var(--color-text-muted);
}

.children {
  border-top: 1px solid var(--color-border);
  padding: 0.5rem 1rem 0.875rem 2.75rem;
}

.project + .project { margin-top: 0.625rem; }

.project-head {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.375rem 0;
  font-size: 0.8125rem;
  color: var(--color-text-primary);
}

.project-meta {
  font-size: 0.75rem;
  color: var(--color-text-muted);
}

:deep(.container-row) {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-left: 0.5rem;
  padding: 0.375rem 0.625rem;
  border-left: 2px solid var(--color-border);
  font-size: 0.8125rem;
}

:deep(.container-row:hover) { background-color: var(--hover-surface); }
:deep(.container-row.is-removed) { opacity: 0.55; }

:deep(.container-name) {
  font-weight: 600;
  color: var(--color-text-primary);
}

:deep(.container-name:hover) { color: var(--color-primary); }

:deep(.container-image) {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.75rem;
  color: var(--color-text-muted);
}

:deep(.container-state) {
  font-size: 0.75rem;
  color: var(--color-text-secondary);
}

.device-delete:hover {
  background-color: var(--danger-soft);
  color: var(--color-danger);
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  padding: 0.875rem 1.25rem;
  border-top: 1px solid var(--color-border);
}

.login-error {
  display: flex;
  gap: 0.5rem;
  padding: 0.625rem 0.75rem;
  border-radius: var(--radius);
  background-color: var(--danger-soft);
  color: var(--color-danger);
}
</style>

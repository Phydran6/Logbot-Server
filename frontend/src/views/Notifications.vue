<!-- ==============================================================================
     Name:        Phydran6
     Kontakt:     Phydran6
     Changelog:   ../../../CHANGELOG/frontend.md
     Beschreibung: LogBot - Meldungen: der Eingang.

     Jede Meldung, die LogBot auslöst, landet hier - auch wenn Mail oder
     Telegram sie gerade nicht zustellen konnten. Dieselbe Liste sieht die
     Handy-App (/api/app/notifications), der Gelesen-Stand ist pro Konto.
     ============================================================================== -->
<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2 class="page-title">Meldungen</h2>
        <p class="page-subtitle">
          Was LogBot gemeldet hat – kritische Logzeilen, Fehler von LogBot selbst, Geräte, die
          verstummt sind. Dieselbe Liste erscheint in der App.
        </p>
      </div>
      <div class="flex gap-2 flex-wrap">
        <select v-model="severity" class="select" aria-label="Schweregrad" @change="reload">
          <option value="">Alle</option>
          <option value="critical">Nur kritisch</option>
          <option value="error">Fehler und kritisch</option>
          <option value="warning">Warnungen und dringender</option>
        </select>
        <label class="flex items-center gap-2 text-sm">
          <input v-model="onlyUnread" type="checkbox" @change="reload"> nur ungelesene
        </label>
        <button class="btn btn-secondary btn-sm" :disabled="!unreadCount" @click="markAllRead">
          <AppIcon name="check" :size="16" /> Alle gelesen
        </button>
        <button class="btn btn-ghost btn-sm" :disabled="loading" @click="reload">
          <AppIcon name="refresh" :size="16" />
        </button>
      </div>
    </div>

    <div v-if="error" class="card mb-4" style="border-color: var(--color-danger)">
      <div class="card-body text-sm" style="color: var(--color-danger)">{{ error }}</div>
    </div>

    <div v-if="!items.length && !loading" class="card">
      <div class="card-body text-sm" style="color: var(--color-text-muted)">
        Keine Meldungen. <router-link v-if="auth.isAdmin" to="/notifications/rules" class="link">Regeln ansehen</router-link>
      </div>
    </div>

    <ul class="space-y-2">
      <li v-for="item in items" :key="item.id" class="card notice" :class="{ 'is-unread': !item.read }"
          :style="{ borderLeftColor: color(item.severity) }">
        <button class="notice-head" :aria-expanded="open === item.id" @click="toggle(item)">
          <span class="badge" :class="badgeClass(item.severity)">{{ severityLabel(item.severity) }}</span>
          <span class="notice-title">{{ item.title }}</span>
          <span v-if="item.count > 1" class="badge badge-neutral">×{{ item.count }}</span>
          <span class="notice-time">{{ formatDate(item.created_at) }}</span>
        </button>
        <div v-if="open === item.id" class="notice-body">
          <p v-if="item.hostname" class="text-sm mb-1">
            <span style="color: var(--color-text-muted)">Gerät:</span>
            <router-link :to="deviceLink(item.hostname)" class="link font-mono">{{ item.hostname }}</router-link>
          </p>
          <pre class="notice-text">{{ item.body }}</pre>
          <div v-if="item.delivery && Object.keys(item.delivery).length" class="flex flex-wrap gap-2 mt-2">
            <span v-for="(d, channel) in item.delivery" :key="channel" class="badge"
                  :class="d.ok ? 'badge-success' : (d.skipped ? 'badge-neutral' : 'badge-danger')"
                  :title="d.error || d.skipped || ''">
              {{ channelLabel(channel) }}: {{ d.ok ? 'zugestellt' : (d.skipped ? 'nicht eingerichtet' : 'Fehler') }}
            </span>
          </div>
          <router-link v-if="item.log_id" :to="`/logs?search=&hostname=${encodeURIComponent(item.hostname || '')}`"
                       class="btn btn-ghost btn-sm mt-2">Logs dieses Geräts</router-link>
        </div>
      </li>
    </ul>

    <div v-if="hasMore" class="mt-4 text-center">
      <button class="btn btn-secondary" :disabled="loading" @click="more">Ältere laden</button>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import AppIcon from '../components/AppIcon.vue'

const auth = useAuthStore()
const route = useRoute()
const items = ref([])
const loading = ref(false)
const error = ref('')
const hasMore = ref(false)
const nextBefore = ref(null)
const unreadCount = ref(0)
const newest = ref(0)
const open = ref(null)
const severity = ref('')
const onlyUnread = ref(false)

async function fetchPage(before) {
  loading.value = true
  error.value = ''
  try {
    const params = new URLSearchParams({ limit: '50' })
    if (before) params.set('before_id', before)
    if (severity.value) params.set('severity', severity.value)
    if (onlyUnread.value) params.set('only_unread', 'true')
    const data = await auth.api(`/api/notifications?${params}`)
    items.value = before ? [...items.value, ...data.items] : data.items
    hasMore.value = data.has_more
    nextBefore.value = data.next_before_id
    unreadCount.value = data.unread_count
    if (!before && data.items.length) newest.value = data.items[0].id
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function reload() { fetchPage(null) }
function more() { fetchPage(nextBefore.value) }

async function markRead(upTo) {
  try {
    const data = await auth.api('/api/notifications/read', { method: 'POST', body: { up_to_id: upTo } })
    unreadCount.value = data.unread_count
    items.value = items.value.map(i => ({ ...i, read: i.id <= data.last_read_id }))
    window.dispatchEvent(new Event('logbot:notifications-read'))
  } catch (e) {
    error.value = e.message
  }
}

function markAllRead() {
  if (newest.value) markRead(newest.value)
}

function toggle(item) {
  open.value = open.value === item.id ? null : item.id
}

const LABELS = { critical: 'Kritisch', error: 'Fehler', warning: 'Warnung', info: 'Info' }
const severityLabel = (s) => LABELS[s] || s
const badgeClass = (s) => ({ critical: 'badge-danger', error: 'badge-danger', warning: 'badge-warning' }[s] || 'badge-neutral')
const color = (s) => ({ critical: 'var(--color-danger)', error: 'var(--color-danger)', warning: 'var(--color-warning)' }[s] || 'var(--color-border)')
const channelLabel = (c) => ({ mail: 'E-Mail', telegram: 'Telegram', app: 'App' }[c] || c)
const deviceLink = (host) => `/devices/${host.split('/').map(encodeURIComponent).join('/')}`

function formatDate(value) {
  if (!value) return ''
  return new Date(value).toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' })
}

onMounted(async () => {
  await fetchPage(null)
  const wanted = Number(route.query.id)
  if (wanted) open.value = wanted
})
</script>

<style scoped>
.notice {
  border-left-width: 4px;
}

.notice.is-unread .notice-title {
  font-weight: 700;
}

.notice-head {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  width: 100%;
  padding: 0.75rem 1rem;
  text-align: left;
}

.notice-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-text-primary);
}

.notice-time {
  font-size: 0.75rem;
  color: var(--color-text-muted);
  white-space: nowrap;
}

.notice-body {
  padding: 0 1rem 0.875rem;
}

.notice-text {
  white-space: pre-wrap;
  word-break: break-word;
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  color: var(--color-text-secondary);
}

.link {
  color: var(--color-primary);
}
</style>

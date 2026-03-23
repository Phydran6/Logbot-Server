<template>
  <div class="p-6">
    <h1 class="text-2xl font-bold mb-6" :style="{ color: 'var(--color-text-primary)' }">Dashboard</h1>
    <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
      <div class="rounded-lg shadow p-6" :style="cardStyle">
        <div class="text-sm" :style="{ color: 'var(--color-text-muted)' }">Gesamt Logs</div>
        <div class="text-3xl font-bold mt-2" :style="{ color: 'var(--color-text-primary)' }">{{ stats?.total_logs?.toLocaleString() || 0 }}</div>
      </div>
      <div class="rounded-lg shadow p-6" :style="cardStyle">
        <div class="text-sm" :style="{ color: 'var(--color-text-muted)' }">Hosts</div>
        <div class="text-3xl font-bold mt-2" :style="{ color: 'var(--color-text-primary)' }">{{ stats?.unique_hosts || 0 }}</div>
      </div>
      <div class="rounded-lg shadow p-6" :style="cardStyle">
        <div class="text-sm" :style="{ color: 'var(--color-text-muted)' }">Fehler</div>
        <div class="text-3xl font-bold mt-2" :style="{ color: 'var(--color-danger, #ef4444)' }">{{ (stats?.logs_by_level?.error || 0) + (stats?.logs_by_level?.critical || 0) }}</div>
      </div>
      <div class="rounded-lg shadow p-6" :style="cardStyle">
        <div class="text-sm" :style="{ color: 'var(--color-text-muted)' }">Heute</div>
        <div class="text-3xl font-bold mt-2" :style="{ color: 'var(--color-text-primary)' }">{{ stats?.logs_today?.toLocaleString() || 0 }}</div>
      </div>
    </div>
    <div class="rounded-lg shadow" :style="cardStyle">
      <div class="p-4 border-b flex justify-between items-center" :style="{ borderColor: 'var(--color-border)' }">
        <h2 class="text-lg font-semibold" :style="{ color: 'var(--color-text-primary)' }">Neueste Logs</h2>
        <router-link to="/logs" class="hover:underline text-sm" :style="{ color: 'var(--color-primary)' }">Alle →</router-link>
      </div>
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
          <tr v-for="log in logs" :key="log.id" class="hover-row">
            <td class="px-4 py-3 text-sm whitespace-nowrap" :style="{ color: 'var(--color-text-secondary)' }">{{ formatTime(log.timestamp) }}</td>
            <td class="px-4 py-3 text-sm" :style="{ color: 'var(--color-text-primary)' }">{{ log.hostname }}</td>
            <td class="px-4 py-3"><span class="px-2 py-1 text-xs rounded-full" :class="levelClass(log.level)">{{ log.level }}</span></td>
            <td class="px-4 py-3 text-sm" :style="{ color: 'var(--color-text-secondary)' }">{{ log.source }}</td>
            <td class="px-4 py-3 text-sm truncate max-w-md" :style="{ color: 'var(--color-text-secondary)' }">{{ log.message }}</td>
          </tr>
          <tr v-if="!logs.length"><td colspan="5" class="px-4 py-8 text-center" :style="{ color: 'var(--color-text-muted)' }">Keine Logs</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const stats = ref(null)
const logs = ref([])

// Card Style mit CSS-Variablen
const cardStyle = computed(() => ({
  backgroundColor: 'var(--color-surface)',
  borderColor: 'var(--color-border)'
}))

onMounted(async () => {
  try {
    stats.value = await auth.api('/api/logs/stats')
    logs.value = await auth.api('/api/logs/recent?limit=10')
  } catch (e) { console.error(e) }
})

function formatTime(ts) { 
  return ts ? new Date(ts).toLocaleString('de-DE') : '-' 
}

function levelClass(level) {
  const c = { 
    error: 'bg-red-500 text-white', 
    critical: 'bg-red-600 text-white', 
    warning: 'bg-yellow-500 text-white', 
    info: 'bg-blue-500 text-white', 
    debug: 'bg-gray-500 text-white',
    notice: 'bg-cyan-500 text-white'
  }
  return c[level] || 'bg-gray-500 text-white'
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
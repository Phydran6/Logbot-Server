<!-- ==============================================================================
     Name:        Philipp Fischer
     Kontakt:     p.fischer@itconex.de
     Version:     2026.01.30.19.18.22
     Beschreibung: LogBot - System Health mit Theme-Support
     ============================================================================== -->

<template>
  <div class="p-6">
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold" :style="{ color: 'var(--color-text-primary)' }">System Health</h1>
      <button
        @click="loadHealth"
        class="px-4 py-2 rounded flex items-center gap-2 hover:opacity-80"
        :style="buttonSecondaryStyle"
      >
        🔄 Aktualisieren
      </button>
    </div>
    
    <!-- Status Banner -->
    <div 
      class="rounded-lg p-6 mb-6"
      :style="health?.status === 'healthy' ? healthyBannerStyle : warningBannerStyle"
    >
      <div class="flex items-center gap-4">
        <span class="text-4xl">{{ health?.status === 'healthy' ? '💚' : '⚠️' }}</span>
        <div>
          <h2 class="text-2xl font-bold" :style="{ color: health?.status === 'healthy' ? 'var(--color-success)' : 'var(--color-warning)' }">
            {{ health?.status === 'healthy' ? 'System läuft normal' : 'System eingeschränkt' }}
          </h2>
          <p :style="{ color: 'var(--color-text-secondary)' }">Version {{ health?.version }} | Uptime: {{ formatUptime(health?.uptime_seconds) }}</p>
        </div>
      </div>
    </div>
    
    <!-- Metriken Grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
      <!-- CPU -->
      <div class="rounded-lg shadow p-6" :style="cardStyle">
        <div class="flex justify-between items-start mb-4">
          <div>
            <p class="text-sm" :style="{ color: 'var(--color-text-muted)' }">CPU Auslastung</p>
            <p class="text-3xl font-bold" :style="{ color: 'var(--color-text-primary)' }">{{ health?.cpu_percent?.toFixed(1) || 0 }}%</p>
          </div>
          <span class="text-2xl">🔲</span>
        </div>
        <div class="w-full rounded-full h-2" :style="{ backgroundColor: 'var(--color-surface-elevated)' }">
          <div 
            class="h-2 rounded-full transition-all"
            :class="getUsageColor(health?.cpu_percent)"
            :style="{ width: (health?.cpu_percent || 0) + '%' }"
          ></div>
        </div>
      </div>
      
      <!-- RAM -->
      <div class="rounded-lg shadow p-6" :style="cardStyle">
        <div class="flex justify-between items-start mb-4">
          <div>
            <p class="text-sm" :style="{ color: 'var(--color-text-muted)' }">RAM Auslastung</p>
            <p class="text-3xl font-bold" :style="{ color: 'var(--color-text-primary)' }">{{ health?.memory_percent?.toFixed(1) || 0 }}%</p>
          </div>
          <span class="text-2xl">🧠</span>
        </div>
        <div class="w-full rounded-full h-2" :style="{ backgroundColor: 'var(--color-surface-elevated)' }">
          <div 
            class="h-2 rounded-full transition-all"
            :class="getUsageColor(health?.memory_percent)"
            :style="{ width: (health?.memory_percent || 0) + '%' }"
          ></div>
        </div>
      </div>
      
      <!-- Disk -->
      <div class="rounded-lg shadow p-6" :style="cardStyle">
        <div class="flex justify-between items-start mb-4">
          <div>
            <p class="text-sm" :style="{ color: 'var(--color-text-muted)' }">Festplatte</p>
            <p class="text-3xl font-bold" :style="{ color: 'var(--color-text-primary)' }">{{ health?.disk_percent?.toFixed(1) || 0 }}%</p>
          </div>
          <span class="text-2xl">💾</span>
        </div>
        <div class="w-full rounded-full h-2" :style="{ backgroundColor: 'var(--color-surface-elevated)' }">
          <div 
            class="h-2 rounded-full transition-all"
            :class="getUsageColor(health?.disk_percent)"
            :style="{ width: (health?.disk_percent || 0) + '%' }"
          ></div>
        </div>
      </div>
      
      <!-- Database -->
      <div class="rounded-lg shadow p-6" :style="cardStyle">
        <div class="flex justify-between items-start mb-4">
          <div>
            <p class="text-sm" :style="{ color: 'var(--color-text-muted)' }">Datenbank</p>
            <p class="text-3xl font-bold" :style="{ color: health?.database_connected ? 'var(--color-success)' : 'var(--color-danger)' }">
              {{ health?.database_connected ? 'OK' : 'Fehler' }}
            </p>
          </div>
          <span class="text-2xl">🗄️</span>
        </div>
        <p class="text-sm" :style="{ color: 'var(--color-text-muted)' }">
          {{ health?.database_connected ? 'Verbunden' : 'Nicht verbunden' }}
        </p>
      </div>
    </div>
    
    <!-- Log Statistiken -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <div class="rounded-lg shadow p-6" :style="cardStyle">
        <h3 class="text-lg font-semibold mb-4" :style="{ color: 'var(--color-text-primary)' }">Log Statistiken</h3>
        <div class="space-y-4">
          <div class="flex justify-between items-center">
            <span :style="{ color: 'var(--color-text-secondary)' }">Gesamt Logs</span>
            <span class="text-xl font-bold" :style="{ color: 'var(--color-text-primary)' }">{{ health?.logs_total?.toLocaleString() || 0 }}</span>
          </div>
          <div class="flex justify-between items-center">
            <span :style="{ color: 'var(--color-text-secondary)' }">Logs (24h)</span>
            <span class="text-xl font-bold" :style="{ color: 'var(--color-text-primary)' }">{{ health?.logs_last_24h?.toLocaleString() || 0 }}</span>
          </div>
          <div class="flex justify-between items-center">
            <span :style="{ color: 'var(--color-text-secondary)' }">Logs/Minute (Ø)</span>
            <span class="text-xl font-bold" :style="{ color: 'var(--color-text-primary)' }">{{ logsPerMinute }}</span>
          </div>
        </div>
      </div>
      
      <div class="rounded-lg shadow p-6" :style="cardStyle">
        <h3 class="text-lg font-semibold mb-4" :style="{ color: 'var(--color-text-primary)' }">Agent Status</h3>
        <div class="space-y-4">
          <div class="flex justify-between items-center">
            <span :style="{ color: 'var(--color-text-secondary)' }">Gesamt Agents</span>
            <span class="text-xl font-bold" :style="{ color: 'var(--color-text-primary)' }">{{ health?.agents_total || 0 }}</span>
          </div>
          <div class="flex justify-between items-center">
            <span :style="{ color: 'var(--color-text-secondary)' }">Online</span>
            <span class="text-xl font-bold" :style="{ color: 'var(--color-success)' }">{{ health?.agents_online || 0 }}</span>
          </div>
          <div class="flex justify-between items-center">
            <span :style="{ color: 'var(--color-text-secondary)' }">Offline</span>
            <span class="text-xl font-bold" :style="{ color: 'var(--color-text-muted)' }">{{ (health?.agents_total || 0) - (health?.agents_online || 0) }}</span>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Auto-Refresh Info -->
    <p class="text-center text-sm mt-6" :style="{ color: 'var(--color-text-muted)' }">
      Daten werden nicht automatisch aktualisiert. Klicke auf "Aktualisieren" für aktuelle Werte.
    </p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const health = ref(null)

// Computed Styles
const cardStyle = computed(() => ({
  backgroundColor: 'var(--color-surface)',
  borderColor: 'var(--color-border)'
}))

const buttonSecondaryStyle = computed(() => ({
  backgroundColor: 'var(--color-surface-elevated)',
  color: 'var(--color-text-primary)',
  border: '1px solid var(--color-border)'
}))

const healthyBannerStyle = computed(() => ({
  backgroundColor: 'var(--color-surface-elevated)',
  border: '1px solid var(--color-success)'
}))

const warningBannerStyle = computed(() => ({
  backgroundColor: 'var(--color-surface-elevated)',
  border: '1px solid var(--color-warning)'
}))

onMounted(() => loadHealth())

async function loadHealth() {
  try {
    health.value = await authStore.api('/api/health/detailed')
  } catch (e) {
    console.error('Fehler:', e)
  }
}

const logsPerMinute = computed(() => {
  if (!health.value?.logs_last_24h) return 0
  return Math.round(health.value.logs_last_24h / (24 * 60))
})

function getUsageColor(percent) {
  if (!percent) return 'bg-gray-400'
  if (percent < 60) return 'bg-green-500'
  if (percent < 80) return 'bg-yellow-500'
  return 'bg-red-500'
}

function formatUptime(seconds) {
  if (!seconds) return '-'
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  
  if (days > 0) return `${days}d ${hours}h ${minutes}m`
  if (hours > 0) return `${hours}h ${minutes}m`
  return `${minutes}m`
}
</script>
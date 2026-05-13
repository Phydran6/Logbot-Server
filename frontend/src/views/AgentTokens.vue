<!-- ==============================================================================
     Name:        Phydran6
     Kontakt:     Phydran6
     Version:     2026.05.13.20.58.33
     Beschreibung: LogBot - Agent Token Verwaltung (HTTPS Agents)
     ============================================================================= -->

<template>
  <div class="p-6">
    <h1 class="text-2xl font-bold mb-6" :style="{ color: 'var(--color-text-primary)' }">Agent Tokens</h1>

    <!-- Neuer Token -->
    <div class="rounded-lg shadow p-4 mb-6" :style="cardStyle">
      <div class="flex flex-col gap-3">
        <div class="flex flex-col md:flex-row gap-3 items-start md:items-end">
          <div class="flex-1 w-full">
            <label class="block text-sm mb-1" :style="{ color: 'var(--color-text-secondary)' }">Token-Name</label>
            <input
              v-model="newTokenName"
              type="text"
              placeholder="z.B. linux-agent-prod oder windows-agent-prod"
              class="w-full rounded px-3 py-2"
              :style="inputStyle"
              @keyup.enter="createToken"
            >
          </div>
          <button
            @click="createToken"
            class="text-white rounded px-4 py-2 hover:opacity-90"
            :style="{ backgroundColor: 'var(--color-primary)' }"
            :disabled="creating || !newTokenName.trim()"
          >
            {{ creating ? 'Erstelle…' : 'Token erstellen' }}
          </button>
        </div>

        <div class="flex flex-wrap gap-2">
          <button
            class="px-3 py-2 rounded text-sm text-white hover:opacity-90"
            :style="{ backgroundColor: 'var(--color-primary)' }"
            :disabled="creating"
            @click="quickCreate('linux-agent')"
          >
            {{ creating && pendingPreset === 'linux-agent' ? 'Erstelle Linux-Token…' : 'Linux-Token erstellen' }}
          </button>
          <button
            class="px-3 py-2 rounded text-sm text-white hover:opacity-90"
            :style="{ backgroundColor: 'var(--color-primary)' }"
            :disabled="creating"
            @click="quickCreate('windows-agent')"
          >
            {{ creating && pendingPreset === 'windows-agent' ? 'Erstelle Windows-Token…' : 'Windows-Token erstellen' }}
          </button>
          <span v-if="statusMessage" class="text-sm" :style="{ color: statusColor }">
            {{ statusMessage }}
          </span>
        </div>
      </div>
    </div>

    <!-- Token-Liste -->
    <div class="rounded-lg shadow p-4" :style="cardStyle">
      <div class="overflow-x-auto">
        <table class="min-w-full text-sm">
          <thead :style="{ color: 'var(--color-text-secondary)' }">
            <tr>
              <th class="text-left py-2 pr-4">Name</th>
              <th class="text-left py-2 pr-4">OS</th>
              <th class="text-left py-2 pr-4">Token</th>
              <th class="text-left py-2 pr-4">Status</th>
              <th class="text-left py-2 pr-4">Erstellt</th>
              <th class="text-left py-2">Aktionen</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="token in tokens" :key="token.id" class="border-t" :style="{ borderColor: 'var(--color-border)' }">
              <td class="py-2 pr-4" :style="{ color: 'var(--color-text-primary)' }">{{ token.name }}</td>
              <td class="py-2 pr-4" :style="{ color: 'var(--color-text-primary)' }">{{ token.device_type || '—' }}</td>
              <td class="py-2 pr-4 font-mono break-all" :style="{ color: 'var(--color-text-primary)' }">{{ token.token }}</td>
              <td class="py-2 pr-4">
                <span
                  class="px-2 py-1 text-xs rounded-full"
                  :class="token.is_active ? 'bg-green-500 text-white' : 'bg-gray-500 text-white'"
                >
                  {{ token.is_active ? 'Aktiv' : 'Inaktiv' }}
                </span>
              </td>
              <td class="py-2 pr-4" :style="{ color: 'var(--color-text-secondary)' }">{{ formatTime(token.created_at) }}</td>
              <td class="py-2 flex flex-wrap gap-2">
                <button class="text-xs px-3 py-1 rounded bg-slate-200 hover:bg-slate-300" @click="copyToken(token.token)">
                  Kopieren
                </button>
                <button class="text-xs px-3 py-1 rounded bg-amber-200 hover:bg-amber-300" @click="regenerateToken(token)">
                  Regenerieren
                </button>
                <button class="text-xs px-3 py-1 rounded bg-rose-200 hover:bg-rose-300" @click="deleteToken(token)">
                  Löschen
                </button>
              </td>
            </tr>
            <tr v-if="!loading && !tokens.length">
              <td class="py-4 text-center text-sm" :colspan="5" :style="{ color: 'var(--color-text-secondary)' }">Keine Tokens vorhanden</td>
            </tr>
            <tr v-if="loading">
              <td class="py-4 text-center text-sm" :colspan="5" :style="{ color: 'var(--color-text-secondary)' }">Lade…</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()

const tokens = ref([])
const loading = ref(false)
const creating = ref(false)
const newTokenName = ref('')
const statusMessage = ref('')
const statusColor = ref('var(--color-text-secondary)')
const pendingPreset = ref('')

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

onMounted(() => {
  loadTokens()
})

async function loadTokens() {
  loading.value = true
  try {
    tokens.value = await authStore.api('/api/agent-tokens')
  } catch (e) {
    console.error('Token-Liste fehlgeschlagen', e)
  } finally {
    loading.value = false
  }
}

async function createToken(deviceTypeOverride = null) {
  if (!newTokenName.value.trim()) return
  creating.value = true
  statusMessage.value = ''
  try {
    const token = await authStore.api('/api/agent-tokens', {
      method: 'POST',
      body: {
        name: newTokenName.value.trim(),
        device_type: deviceTypeOverride || null
      }
    })
    tokens.value = [token, ...tokens.value]
    newTokenName.value = ''
    statusMessage.value = `Token "${token.name}" erstellt`
    statusColor.value = 'var(--color-success, #16a34a)'
  } catch (e) {
    alert('Erstellen fehlgeschlagen: ' + (e?.message || e))
    statusMessage.value = 'Fehler beim Erstellen: ' + (e?.message || '')
    statusColor.value = 'var(--color-danger, #dc2626)'
  } finally {
    creating.value = false
    pendingPreset.value = ''
  }
}

async function quickCreate(presetName) {
  pendingPreset.value = presetName
  newTokenName.value = presetName
  const device = presetName.startsWith('linux') ? 'linux' : presetName.startsWith('windows') ? 'windows' : null
  await createToken(device)
}

async function regenerateToken(token) {
  if (!confirm(`Token "${token.name}" regenerieren?`)) return
  try {
    const updated = await authStore.api(`/api/agent-tokens/${token.id}/regenerate`, { method: 'POST' })
    tokens.value = tokens.value.map(t => t.id === token.id ? updated : t)
    statusMessage.value = `Token "${updated.name}" regeneriert`
    statusColor.value = 'var(--color-success, #16a34a)'
  } catch (e) {
    alert('Regeneration fehlgeschlagen: ' + e.message)
    statusMessage.value = 'Fehler bei Regeneration'
    statusColor.value = 'var(--color-danger, #dc2626)'
  }
}

async function deleteToken(token) {
  if (!confirm(`Token "${token.name}" löschen?`)) return
  try {
    await authStore.api(`/api/agent-tokens/${token.id}`, { method: 'DELETE' })
    tokens.value = tokens.value.filter(t => t.id !== token.id)
    statusMessage.value = `Token "${token.name}" gelöscht`
    statusColor.value = 'var(--color-success, #16a34a)'
  } catch (e) {
    alert('Löschen fehlgeschlagen: ' + e.message)
    statusMessage.value = 'Fehler beim Löschen'
    statusColor.value = 'var(--color-danger, #dc2626)'
  }
}

async function copyToken(value) {
  try {
    await navigator.clipboard.writeText(value)
    statusMessage.value = 'Token kopiert'
    statusColor.value = 'var(--color-success, #16a34a)'
  } catch (e) {
    console.warn('Clipboard fehlgeschlagen', e)
    statusMessage.value = 'Kopieren fehlgeschlagen'
    statusColor.value = 'var(--color-danger, #dc2626)'
  }
}

function formatTime(ts) {
  if (!ts) return '-'
  return new Date(ts).toLocaleString('de-DE')
}
</script>

<!-- ==============================================================================
     Name:        Philipp Fischer
     Kontakt:     p.fischer@itconex.de
     Version:     2026.01.30.19.12.45
     Beschreibung: LogBot - Benutzer-Verwaltung mit Theme-Support
     ============================================================================== -->

<template>
  <div class="p-6">
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold" :style="{ color: 'var(--color-text-primary)' }">Benutzer</h1>
      <button
        @click="showCreateModal = true"
        class="text-white px-4 py-2 rounded hover:opacity-90"
        :style="{ backgroundColor: 'var(--color-primary)' }"
      >
        + Neuer Benutzer
      </button>
    </div>
    
    <!-- Users Tabelle -->
    <div class="rounded-lg shadow" :style="cardStyle">
      <table class="w-full">
        <thead :style="{ backgroundColor: 'var(--color-surface-elevated)' }">
          <tr>
            <th class="px-6 py-3 text-left text-xs font-medium uppercase" :style="{ color: 'var(--color-text-muted)' }">Benutzername</th>
            <th class="px-6 py-3 text-left text-xs font-medium uppercase" :style="{ color: 'var(--color-text-muted)' }">E-Mail</th>
            <th class="px-6 py-3 text-left text-xs font-medium uppercase" :style="{ color: 'var(--color-text-muted)' }">Rolle</th>
            <th class="px-6 py-3 text-left text-xs font-medium uppercase" :style="{ color: 'var(--color-text-muted)' }">Status</th>
            <th class="px-6 py-3 text-left text-xs font-medium uppercase" :style="{ color: 'var(--color-text-muted)' }">Erstellt</th>
            <th class="px-6 py-3 text-right text-xs font-medium uppercase" :style="{ color: 'var(--color-text-muted)' }">Aktionen</th>
          </tr>
        </thead>
        <tbody class="divide-y" :style="{ borderColor: 'var(--color-border)' }">
          <tr v-for="user in users" :key="user.id" class="hover-row">
            <td class="px-6 py-4 font-medium" :style="{ color: 'var(--color-text-primary)' }">{{ user.username }}</td>
            <td class="px-6 py-4" :style="{ color: 'var(--color-text-muted)' }">{{ user.email || '-' }}</td>
            <td class="px-6 py-4">
              <span 
                class="px-2 py-1 text-xs rounded-full text-white"
                :class="user.role === 'admin' ? 'bg-purple-500' : 'bg-gray-500'"
              >
                {{ user.role }}
              </span>
            </td>
            <td class="px-6 py-4">
              <span 
                class="px-2 py-1 text-xs rounded-full text-white"
                :class="user.is_active ? 'bg-green-500' : 'bg-red-500'"
              >
                {{ user.is_active ? 'Aktiv' : 'Deaktiviert' }}
              </span>
            </td>
            <td class="px-6 py-4 text-sm" :style="{ color: 'var(--color-text-muted)' }">{{ formatDate(user.created_at) }}</td>
            <td class="px-6 py-4 text-right">
              <button
                @click="editUser(user)"
                class="hover:underline mr-4"
                :style="{ color: 'var(--color-primary)' }"
              >
                Bearbeiten
              </button>
              <button
                v-if="user.id !== authStore.user?.id"
                @click="deleteUser(user)"
                class="hover:underline"
                :style="{ color: 'var(--color-danger)' }"
              >
                Löschen
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    
    <!-- Create/Edit Modal -->
    <div 
      v-if="showCreateModal || editingUser" 
      class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50"
      @click.self="closeModal"
    >
      <div class="rounded-lg shadow-xl w-full max-w-md" :style="cardStyle">
        <div class="p-4 border-b" :style="{ borderColor: 'var(--color-border)' }">
          <h2 class="text-lg font-semibold" :style="{ color: 'var(--color-text-primary)' }">
            {{ editingUser ? 'Benutzer bearbeiten' : 'Neuer Benutzer' }}
          </h2>
        </div>
        <form @submit.prevent="saveUser" class="p-4 space-y-4">
          <div>
            <label class="block text-sm font-medium mb-1" :style="{ color: 'var(--color-text-secondary)' }">Benutzername</label>
            <input
              v-model="form.username"
              type="text"
              required
              :disabled="!!editingUser"
              class="w-full rounded px-3 py-2 disabled:opacity-50"
              :style="inputStyle"
            >
          </div>
          <div>
            <label class="block text-sm font-medium mb-1" :style="{ color: 'var(--color-text-secondary)' }">E-Mail</label>
            <input
              v-model="form.email"
              type="email"
              class="w-full rounded px-3 py-2"
              :style="inputStyle"
            >
          </div>
          <div>
            <label class="block text-sm font-medium mb-1" :style="{ color: 'var(--color-text-secondary)' }">
              {{ editingUser ? 'Neues Passwort (leer lassen um nicht zu ändern)' : 'Passwort' }}
            </label>
            <input
              v-model="form.password"
              type="password"
              :required="!editingUser"
              minlength="6"
              class="w-full rounded px-3 py-2"
              :style="inputStyle"
            >
          </div>
          <div>
            <label class="block text-sm font-medium mb-1" :style="{ color: 'var(--color-text-secondary)' }">Rolle</label>
            <select v-model="form.role" class="w-full rounded px-3 py-2" :style="inputStyle">
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <div v-if="editingUser" class="flex items-center">
            <input
              v-model="form.is_active"
              type="checkbox"
              id="is_active"
              class="mr-2"
            >
            <label for="is_active" :style="{ color: 'var(--color-text-secondary)' }">Benutzer aktiv</label>
          </div>
          
          <div class="flex justify-end gap-2 pt-4 border-t" :style="{ borderColor: 'var(--color-border)' }">
            <button
              type="button"
              @click="closeModal"
              class="px-4 py-2 rounded hover:opacity-80"
              :style="buttonSecondaryStyle"
            >
              Abbrechen
            </button>
            <button
              type="submit"
              class="px-4 py-2 text-white rounded hover:opacity-90"
              :style="{ backgroundColor: 'var(--color-primary)' }"
            >
              Speichern
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()

const users = ref([])
const showCreateModal = ref(false)
const editingUser = ref(null)
const form = ref({
  username: '',
  email: '',
  password: '',
  role: 'user',
  is_active: true
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

onMounted(() => loadUsers())

async function loadUsers() {
  try {
    users.value = await authStore.api('/api/users')
  } catch (e) {
    console.error('Fehler:', e)
  }
}

function editUser(user) {
  editingUser.value = user
  form.value = {
    username: user.username,
    email: user.email || '',
    password: '',
    role: user.role,
    is_active: user.is_active
  }
}

function closeModal() {
  showCreateModal.value = false
  editingUser.value = null
  form.value = { username: '', email: '', password: '', role: 'user', is_active: true }
}

async function saveUser() {
  try {
    if (editingUser.value) {
      const data = {
        email: form.value.email,
        role: form.value.role,
        is_active: form.value.is_active
      }
      if (form.value.password) {
        data.password = form.value.password
      }
      await authStore.api(`/api/users/${editingUser.value.id}`, {
        method: 'PUT',
        body: data
      })
    } else {
      await authStore.api('/api/users', {
        method: 'POST',
        body: form.value
      })
    }
    closeModal()
    loadUsers()
  } catch (e) {
    alert('Fehler: ' + e.message)
  }
}

async function deleteUser(user) {
  if (!confirm(`Benutzer "${user.username}" wirklich löschen?`)) return
  
  try {
    await authStore.api(`/api/users/${user.id}`, { method: 'DELETE' })
    loadUsers()
  } catch (e) {
    alert('Fehler: ' + e.message)
  }
}

function formatDate(timestamp) {
  if (!timestamp) return '-'
  return new Date(timestamp).toLocaleDateString('de-DE')
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
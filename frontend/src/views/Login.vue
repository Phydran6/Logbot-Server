<!-- ==============================================================================
     Name:        Philipp Fischer
     Kontakt:     p.fischer@itconex.de
     Version:     2026.01.30.19.20.45
     Beschreibung: LogBot - Login mit Theme-Support
     ============================================================================== -->

<template>
  <div class="min-h-screen flex items-center justify-center" :style="{ backgroundColor: 'var(--color-bg)' }">
    <div class="p-8 rounded-lg shadow-md w-full max-w-md" :style="cardStyle">
      <h1 class="text-3xl font-bold text-center mb-2" :style="{ color: 'var(--color-text-primary)' }">📋 LogBot</h1>
      <p class="text-center mb-6" :style="{ color: 'var(--color-text-muted)' }">Zentraler Log-Server</p>
      
      <div v-if="error" class="px-4 py-3 rounded mb-4" :style="errorStyle">
        {{ error }}
      </div>
      
      <form @submit.prevent="handleLogin">
        <div class="mb-4">
          <label class="block text-sm font-bold mb-2" :style="{ color: 'var(--color-text-secondary)' }">Benutzername</label>
          <input 
            v-model="username" 
            type="text" 
            class="w-full px-3 py-2 rounded focus:outline-none"
            :style="inputStyle"
            required 
            autofocus
          >
        </div>
        <div class="mb-6">
          <label class="block text-sm font-bold mb-2" :style="{ color: 'var(--color-text-secondary)' }">Passwort</label>
          <input 
            v-model="password" 
            type="password" 
            class="w-full px-3 py-2 rounded focus:outline-none"
            :style="inputStyle"
            required
          >
        </div>
        <button 
          type="submit" 
          :disabled="loading" 
          class="w-full text-white font-bold py-2 px-4 rounded disabled:opacity-50 hover:opacity-90"
          :style="{ backgroundColor: 'var(--color-primary)' }"
        >
          {{ loading ? 'Anmelden...' : 'Anmelden' }}
        </button>
      </form>
      
      <p class="text-center text-sm mt-6" :style="{ color: 'var(--color-text-muted)' }">Standard: admin / admin</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useThemeStore } from '../stores/themeStore'

const router = useRouter()
const auth = useAuthStore()
const themeStore = useThemeStore()

const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

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

const errorStyle = computed(() => ({
  backgroundColor: 'var(--color-surface-elevated)',
  border: '1px solid var(--color-danger)',
  color: 'var(--color-danger)'
}))

// Theme beim Login initialisieren falls noch nicht geschehen
onMounted(() => {
  if (!document.documentElement.getAttribute('data-theme')) {
    themeStore.initTheme('dark')
  }
})

async function handleLogin() {
  loading.value = true
  error.value = ''
  try {
    await auth.login(username.value, password.value)
    router.push('/')
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>
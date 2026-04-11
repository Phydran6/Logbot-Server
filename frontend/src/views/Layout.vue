<!-- ==============================================================================
     Name:        Philipp Fischer
     Kontakt:     p.fischer@itconex.de
     Version:     2026.04.11.13.38.42
     Beschreibung: LogBot - Hauptlayout mit Sidebar/Navigation
     ============================================================================== -->

<template>
  <div class="flex h-screen" :style="{ backgroundColor: 'var(--color-bg, #f3f4f6)' }">
    <!-- Mobile Overlay -->
    <div
      v-if="sidebarOpen"
      class="fixed inset-0 z-20 bg-black bg-opacity-50 md:hidden"
      @click="sidebarOpen = false"
    />

    <!-- Sidebar -->
    <aside
      class="fixed inset-y-0 left-0 z-30 w-64 flex flex-col transform transition-transform duration-200 md:relative md:translate-x-0"
      :class="sidebarOpen ? 'translate-x-0' : '-translate-x-full'"
      :style="{ backgroundColor: 'var(--color-surface, #1f2937)', color: 'var(--color-text-primary, #fff)' }"
    >
      <div class="p-4 border-b" :style="{ borderColor: 'var(--color-border, #374151)' }">
        <h1 class="text-xl font-bold">📄 {{ companyName }}</h1>
        <p class="text-sm" :style="{ color: 'var(--color-text-muted, #9ca3af)' }">v2026.04.11.13.38.42</p>
      </div>

      <nav class="flex-1 p-4">
        <ul class="space-y-2">
          <li><router-link to="/" class="nav-link" :class="{ active: $route.name === 'Dashboard' }" @click="sidebarOpen = false">📈 Dashboard</router-link></li>
          <li><router-link to="/logs" class="nav-link" :class="{ active: $route.name === 'Logs' }" @click="sidebarOpen = false">📃 Logs</router-link></li>
          <li><router-link to="/agents" class="nav-link" :class="{ active: $route.name === 'Agents' }" @click="sidebarOpen = false">🛡️ Agents</router-link></li>
          <li><router-link to="/webhooks" class="nav-link" :class="{ active: $route.name === 'Webhooks' }" @click="sidebarOpen = false">🔗 Webhooks</router-link></li>
          <li v-if="auth.isAdmin"><router-link to="/users" class="nav-link" :class="{ active: $route.name === 'Users' }" @click="sidebarOpen = false">👥 Benutzer</router-link></li>
          <li><router-link to="/settings" class="nav-link" :class="{ active: $route.name === 'Settings' }" @click="sidebarOpen = false">⚙️ Einstellungen</router-link></li>
          <li><router-link to="/settings/branding" class="nav-link" :class="{ active: $route.name === 'BrandingSettings' }" @click="sidebarOpen = false">🎨 Branding</router-link></li>
          <li><router-link to="/health" class="nav-link" :class="{ active: $route.name === 'Health' }" @click="sidebarOpen = false">💚 Health</router-link></li>
          <li><router-link to="/app-login" class="nav-link" :class="{ active: $route.name === 'AppLogin' }" @click="sidebarOpen = false">📱 App-Login</router-link></li>
        </ul>
      </nav>

      <!-- Theme Toggle + User Info -->
      <div class="p-4 border-t" :style="{ borderColor: 'var(--color-border, #374151)' }">
        <!-- Theme Toggle -->
        <div class="flex items-center justify-between mb-3">
          <span class="text-sm" :style="{ color: 'var(--color-text-muted, #9ca3af)' }">Theme</span>
          <button @click="toggleTheme" class="theme-toggle-btn" :title="isDark ? 'Light Mode' : 'Dark Mode'">
            <!-- Sonne -->
            <svg v-if="!isDark" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <circle cx="12" cy="12" r="5"></circle>
              <line x1="12" y1="1" x2="12" y2="3"></line>
              <line x1="12" y1="21" x2="12" y2="23"></line>
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
              <line x1="1" y1="12" x2="3" y2="12"></line>
              <line x1="21" y1="12" x2="23" y2="12"></line>
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
            </svg>
            <!-- Mond -->
            <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
            </svg>
          </button>
        </div>

        <!-- User Info -->
        <div class="flex items-center justify-between">
          <div>
            <p class="font-medium">{{ auth.user?.username }}</p>
            <p class="text-sm" :style="{ color: 'var(--color-text-muted, #9ca3af)' }">{{ auth.user?.role }}</p>
          </div>
          <button @click="handleLogout" class="logout-btn" title="Abmelden">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
              <polyline points="16 17 21 12 16 7"></polyline>
              <line x1="21" y1="12" x2="9" y2="12"></line>
            </svg>
          </button>
        </div>
      </div>
    </aside>

    <!-- Main Content -->
    <main class="flex-1 overflow-auto min-w-0" :style="{ backgroundColor: 'var(--color-bg, #f3f4f6)' }">
      <!-- Mobile Header with Hamburger -->
      <div
        class="flex items-center gap-3 p-3 border-b md:hidden"
        :style="{ backgroundColor: 'var(--color-surface, #1f2937)', borderColor: 'var(--color-border, #374151)' }"
      >
        <button @click="sidebarOpen = true" class="hamburger-btn" aria-label="Menü öffnen">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <line x1="3" y1="6" x2="21" y2="6"></line>
            <line x1="3" y1="12" x2="21" y2="12"></line>
            <line x1="3" y1="18" x2="21" y2="18"></line>
          </svg>
        </button>
        <span class="font-bold text-lg" :style="{ color: 'var(--color-text-primary, #fff)' }">📄 {{ companyName }}</span>
      </div>

      <router-view />

      <!-- Footer -->
      <footer class="px-6 py-3 text-xs border-t flex gap-4" :style="{ borderColor: 'var(--color-border)', color: 'var(--color-text-muted)', backgroundColor: 'var(--color-surface)' }">
        <router-link to="/impressum" class="hover:underline">Impressum</router-link>
        <router-link to="/datenschutz" class="hover:underline">Datenschutz</router-link>
      </footer>
    </main>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useThemeStore } from '../stores/themeStore'
import { useBrandingStore } from '../stores/brandingStore'

const router = useRouter()
const auth = useAuthStore()
const themeStore = useThemeStore()
const brandingStore = useBrandingStore()

const sidebarOpen = ref(false)

// Computed
const isDark = computed(() => themeStore.currentTheme === 'dark')
const companyName = computed(() => brandingStore.config?.company_name || 'LogBot')

// Methods
function toggleTheme() {
  themeStore.toggleTheme()
}

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.nav-link {
  display: flex;
  align-items: center;
  padding: 0.5rem 1rem;
  border-radius: 0.375rem;
  transition: background-color 0.2s;
}

.nav-link:hover {
  background-color: var(--color-surface-elevated, #374151);
}

.nav-link.active {
  background-color: var(--color-surface-elevated, #374151);
}

.theme-toggle-btn {
  padding: 0.5rem;
  border-radius: 0.375rem;
  background-color: var(--color-surface-elevated, #374151);
  color: var(--color-text-secondary, #d1d5db);
  transition: all 0.2s;
}

.theme-toggle-btn:hover {
  background-color: var(--color-primary, #3b82f6);
  color: white;
}

.theme-toggle-btn svg {
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.logout-btn {
  padding: 0.5rem;
  border-radius: 0.375rem;
  background-color: var(--color-surface-elevated, #374151);
  color: var(--color-text-secondary, #d1d5db);
  transition: all 0.2s;
}

.logout-btn:hover {
  background-color: #ef4444;
  color: white;
}

.logout-btn svg,
.logout-btn path,
.logout-btn polyline,
.logout-btn line {
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.hamburger-btn {
  padding: 0.375rem;
  border-radius: 0.375rem;
  color: var(--color-text-secondary, #d1d5db);
  transition: background-color 0.2s;
}

.hamburger-btn:hover {
  background-color: var(--color-surface-elevated, #374151);
}

.hamburger-btn svg {
  stroke-width: 2;
  stroke-linecap: round;
}
</style>

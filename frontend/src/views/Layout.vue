<!-- ==============================================================================
     Name:        Phydran6
     Kontakt:     Phydran6
     Version:     2026.07.31.21.10.00
     Beschreibung: LogBot - Hauptlayout mit ein-/ausklappbarer Sidebar/Navigation
     ============================================================================== -->

<template>
  <!-- h-full statt h-screen: die Hoehe gibt der App-Rahmen vor (App.vue),
       damit ein eingeblendeter Hinweis-Balken oben nicht ueberlaeuft. -->
  <div class="flex h-full" :style="{ backgroundColor: 'var(--color-bg, #f3f4f6)' }">
    <!-- Mobile Overlay -->
    <div
      v-if="sidebarOpen"
      class="fixed inset-0 z-20 bg-black bg-opacity-50 md:hidden"
      @click="sidebarOpen = false"
    />

    <!-- Sidebar -->
    <aside
      class="fixed inset-y-0 left-0 z-30 w-64 flex flex-col transform transition-all duration-200 md:relative md:translate-x-0"
      :class="[
        sidebarOpen ? 'translate-x-0' : '-translate-x-full',
        collapsed ? 'md:w-16' : 'md:w-64',
      ]"
      :style="{ backgroundColor: 'var(--color-surface, #1f2937)', color: 'var(--color-text-primary, #fff)' }"
    >
      <!-- Kopfbereich: Titel + Ein-/Ausklappen -->
      <div
        class="flex items-center gap-2 p-4 border-b"
        :class="collapsed ? 'md:justify-center md:px-2' : ''"
        :style="{ borderColor: 'var(--color-border, #374151)' }"
      >
        <div class="flex-1 min-w-0" :class="collapsed ? 'md:hidden' : ''">
          <h1 class="text-xl font-bold truncate">📄 {{ companyName }}</h1>
          <p class="text-sm" :style="{ color: 'var(--color-text-muted, #9ca3af)' }">v{{ appVersion }}</p>
        </div>
        <span v-if="collapsed" class="hidden md:block text-xl" :title="companyName">📄</span>

        <!-- Desktop: Menü ein-/ausklappen -->
        <button
          class="collapse-btn hidden md:flex"
          :title="collapsed ? 'Menü einblenden' : 'Menü ausblenden'"
          :aria-label="collapsed ? 'Menü einblenden' : 'Menü ausblenden'"
          :aria-expanded="!collapsed"
          @click="toggleCollapsed"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <polyline v-if="collapsed" points="9 18 15 12 9 6"></polyline>
            <polyline v-else points="15 18 9 12 15 6"></polyline>
          </svg>
        </button>

        <!-- Mobile: Menü schließen -->
        <button
          class="collapse-btn md:hidden"
          title="Menü schließen"
          aria-label="Menü schließen"
          @click="sidebarOpen = false"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>

      <nav class="flex-1 overflow-y-auto p-4" :class="collapsed ? 'md:px-2' : ''">
        <ul class="space-y-2">
          <li v-for="item in navItems" :key="item.to">
            <router-link
              :to="item.to"
              class="nav-link"
              :class="[{ active: $route.name === item.name }, collapsed ? 'md:justify-center md:px-2' : '']"
              :title="collapsed ? item.label : null"
              @click="sidebarOpen = false"
            >
              <span class="nav-icon">{{ item.icon }}</span>
              <span class="nav-label" :class="collapsed ? 'md:hidden' : ''">{{ item.label }}</span>
            </router-link>
          </li>
        </ul>
      </nav>

      <!-- Theme Toggle + User Info -->
      <div class="p-4 border-t" :class="collapsed ? 'md:px-2' : ''" :style="{ borderColor: 'var(--color-border, #374151)' }">
        <!-- Theme Toggle -->
        <div class="flex items-center justify-between mb-3" :class="collapsed ? 'md:justify-center' : ''">
          <span class="text-sm" :class="collapsed ? 'md:hidden' : ''" :style="{ color: 'var(--color-text-muted, #9ca3af)' }">Theme</span>
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
        <div class="flex items-center justify-between" :class="collapsed ? 'md:justify-center' : ''">
          <div class="min-w-0" :class="collapsed ? 'md:hidden' : ''">
            <p class="font-medium truncate">{{ auth.user?.username }}</p>
            <p class="text-sm" :style="{ color: 'var(--color-text-muted, #9ca3af)' }">{{ auth.user?.role }}</p>
          </div>
          <button @click="handleLogout" class="logout-btn" :title="collapsed ? `Abmelden (${auth.user?.username || ''})` : 'Abmelden'">
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
    <main class="flex-1 overflow-auto min-w-0 flex flex-col" :style="{ backgroundColor: 'var(--color-bg, #f3f4f6)' }">
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

      <div class="flex-1">
        <router-view />
      </div>

      <!-- Footer -->
      <footer class="px-6 py-3 text-xs border-t flex gap-4" :style="{ borderColor: 'var(--color-border)', color: 'var(--color-text-muted)', backgroundColor: 'var(--color-surface)' }">
        <router-link to="/impressum" class="hover:underline">Impressum</router-link>
        <router-link to="/datenschutz" class="hover:underline">Datenschutz</router-link>
      </footer>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useThemeStore } from '../stores/themeStore'
import { useBrandingStore } from '../stores/brandingStore'
import pkg from '../../package.json'

const router = useRouter()
const auth = useAuthStore()
const themeStore = useThemeStore()
const brandingStore = useBrandingStore()

// Release-Version kommt aus der package.json, damit sie nicht doppelt gepflegt wird.
const appVersion = pkg.version

// Mobile: Sidebar als Overlay. Desktop: eingeklappt (nur Icons) oder voll.
const sidebarOpen = ref(false)

const COLLAPSE_KEY = 'logbot.sidebarCollapsed'

function loadCollapsed() {
  try {
    return localStorage.getItem(COLLAPSE_KEY) === '1'
  } catch {
    return false
  }
}

const collapsed = ref(loadCollapsed())

watch(collapsed, (value) => {
  try {
    localStorage.setItem(COLLAPSE_KEY, value ? '1' : '0')
  } catch {
    // Kein localStorage (Privat-Modus o. ae.) - Zustand gilt nur fuer diese Sitzung.
  }
})

// Computed
const isDark = computed(() => themeStore.currentTheme === 'dark')
const companyName = computed(() => brandingStore.config?.company_name || 'LogBot')

const navItems = computed(() => [
  { to: '/', name: 'Dashboard', icon: '📈', label: 'Dashboard' },
  { to: '/logs', name: 'Logs', icon: '📃', label: 'Logs' },
  { to: '/agents', name: 'Agents', icon: '🛡️', label: 'Agents' },
  { to: '/webhooks', name: 'Webhooks', icon: '🔗', label: 'Webhooks' },
  ...(auth.isAdmin ? [{ to: '/users', name: 'Users', icon: '👥', label: 'Benutzer' }] : []),
  { to: '/settings', name: 'Settings', icon: '⚙️', label: 'Einstellungen' },
  { to: '/settings/branding', name: 'BrandingSettings', icon: '🎨', label: 'Branding' },
  { to: '/health', name: 'Health', icon: '💚', label: 'Health' },
])

// Methods
function toggleCollapsed() {
  collapsed.value = !collapsed.value
}

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
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border-radius: 0.375rem;
  white-space: nowrap;
  overflow: hidden;
  transition: background-color 0.2s;
}

.nav-link:hover {
  background-color: var(--color-surface-elevated, #374151);
}

.nav-link.active {
  background-color: var(--color-surface-elevated, #374151);
}

.nav-icon {
  flex-shrink: 0;
  line-height: 1;
}

.nav-label {
  overflow: hidden;
  text-overflow: ellipsis;
}

.collapse-btn {
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  padding: 0.375rem;
  border-radius: 0.375rem;
  color: var(--color-text-secondary, #d1d5db);
  transition: background-color 0.2s;
}

.collapse-btn:hover {
  background-color: var(--color-surface-elevated, #374151);
}

.collapse-btn svg {
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
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

<!-- ==============================================================================
     Name:        Phydran6
     Kontakt:     Phydran6
     Version:     2026.08.02.14.00.00
     Changelog:   ../../../CHANGELOG/frontend.md
     Beschreibung: LogBot - Hauptlayout: dockbare Sidebar, Kopfleiste, Inhalt.
     ============================================================================== -->

<template>
  <!-- h-full statt h-screen: die Hoehe gibt der App-Rahmen vor (App.vue),
       damit ein eingeblendeter Hinweis-Balken oben nicht ueberlaeuft. -->
  <div class="flex h-full" style="background-color: var(--color-bg)">
    <!-- Mobile: Overlay hinter der Sidebar -->
    <transition name="fade">
      <div
        v-if="sidebarOpen"
        class="fixed inset-0 z-20 md:hidden"
        style="background-color: var(--overlay)"
        @click="sidebarOpen = false"
      />
    </transition>

    <!-- ================================================================
         SIDEBAR
         ================================================================ -->
    <aside
      class="sidebar"
      :class="[sidebarOpen ? 'is-open' : '', collapsed ? 'is-collapsed' : '']"
    >
      <!-- Marke -->
      <div class="sidebar-brand">
        <router-link to="/" class="brand-mark" :title="companyName" @click="sidebarOpen = false">
          <img v-if="logoUrl" :src="logoUrl" :alt="companyName" class="brand-logo">
          <span v-else class="brand-initial">{{ brandInitial }}</span>
        </router-link>

        <div class="brand-text" :class="collapsed ? 'md:hidden' : ''">
          <p class="brand-name">{{ companyName }}</p>
          <p class="brand-version">v{{ appVersion }}</p>
        </div>

        <!-- Desktop: andocken / ausklappen -->
        <button
          class="btn-icon hidden md:flex"
          :class="collapsed ? 'md:hidden' : ''"
          :title="'Menü einklappen'"
          aria-label="Menü einklappen"
          :aria-expanded="!collapsed"
          @click="toggleCollapsed"
        >
          <AppIcon name="chevronLeft" :size="18" />
        </button>

        <!-- Mobile: schließen -->
        <button class="btn-icon md:hidden" title="Menü schließen" aria-label="Menü schließen" @click="sidebarOpen = false">
          <AppIcon name="close" :size="18" />
        </button>
      </div>

      <!-- Navigation -->
      <nav class="sidebar-nav">
        <template v-for="group in navGroups" :key="group.title">
          <p v-if="group.items.length" class="nav-group-title" :class="collapsed ? 'md:hidden' : ''">
            {{ group.title }}
          </p>
          <ul v-if="group.items.length" class="nav-list">
            <li v-for="item in group.items" :key="item.to">
              <router-link
                :to="item.to"
                class="nav-link"
                :class="[{ active: isActive(item) }, collapsed ? 'md:justify-center md:px-2' : '']"
                :title="collapsed ? item.label : null"
                @click="sidebarOpen = false"
              >
                <AppIcon :name="item.icon" :size="18" class="shrink-0" />
                <span :class="collapsed ? 'md:hidden' : ''">{{ item.label }}</span>
              </router-link>
            </li>
          </ul>
        </template>
      </nav>

      <!-- Fußbereich: eingeklappt aufklappen, Theme, Benutzer -->
      <div class="sidebar-footer">
        <button
          v-if="collapsed"
          class="btn-icon hidden md:flex w-full justify-center"
          title="Menü ausklappen"
          aria-label="Menü ausklappen"
          :aria-expanded="!collapsed"
          @click="toggleCollapsed"
        >
          <AppIcon name="chevronRight" :size="18" />
        </button>

        <button
          class="user-row"
          :class="collapsed ? 'md:justify-center' : ''"
          :title="isDark ? 'Zu hellem Design wechseln' : 'Zu dunklem Design wechseln'"
          @click="toggleTheme"
        >
          <AppIcon :name="isDark ? 'moon' : 'sun'" :size="18" class="shrink-0" />
          <span class="flex-1 text-left" :class="collapsed ? 'md:hidden' : ''">
            {{ isDark ? 'Dunkel' : 'Hell' }}
          </span>
        </button>

        <div class="user-row user-row--static" :class="collapsed ? 'md:justify-center' : ''">
          <span class="avatar" :title="auth.user?.username">{{ userInitial }}</span>
          <div class="min-w-0 flex-1" :class="collapsed ? 'md:hidden' : ''">
            <p class="user-name">{{ auth.user?.username }}</p>
            <p class="user-role">{{ roleLabel }}</p>
          </div>
          <button
            class="btn-icon logout-btn"
            :class="collapsed ? 'md:hidden' : ''"
            title="Abmelden"
            aria-label="Abmelden"
            @click="handleLogout"
          >
            <AppIcon name="logout" :size="18" />
          </button>
        </div>
      </div>
    </aside>

    <!-- ================================================================
         INHALT
         ================================================================ -->
    <main class="flex-1 overflow-auto min-w-0 flex flex-col">
      <!-- Kopfleiste -->
      <header class="topbar">
        <button class="btn-icon md:hidden" aria-label="Menü öffnen" @click="sidebarOpen = true">
          <AppIcon name="menu" :size="20" />
        </button>
        <h1 class="topbar-title">{{ pageTitle }}</h1>
        <div class="flex-1" />
        <span class="badge badge-neutral hidden sm:inline-flex">{{ auth.user?.username }}</span>
      </header>

      <div class="flex-1">
        <router-view />
      </div>

      <footer class="app-footer">
        <span>{{ footerText }}</span>
        <span class="flex-1" />
        <router-link to="/impressum" class="hover:underline">Impressum</router-link>
        <router-link to="/datenschutz" class="hover:underline">Datenschutz</router-link>
      </footer>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useThemeStore } from '../stores/themeStore'
import { useBrandingStore } from '../stores/brandingStore'
import AppIcon from '../components/AppIcon.vue'
import pkg from '../../package.json'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const themeStore = useThemeStore()
const brandingStore = useBrandingStore()

// Release-Version kommt aus der package.json, damit sie nicht doppelt gepflegt wird.
const appVersion = pkg.version

// Mobile: Sidebar als Overlay. Desktop: angedockt (nur Icons) oder voll.
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

const isDark = computed(() => themeStore.currentTheme === 'dark')
const companyName = computed(() => brandingStore.config?.company_name || 'LogBot')
const footerText = computed(() => brandingStore.config?.footer_text || '')
const logoUrl = computed(() => brandingStore.getLogoUrl())
const brandInitial = computed(() => (companyName.value || 'L').trim().charAt(0).toUpperCase())
const userInitial = computed(() => (auth.user?.username || '?').trim().charAt(0).toUpperCase())
const roleLabel = computed(() => (auth.user?.role === 'admin' ? 'Administrator' : 'Benutzer'))

// Navigation in Gruppen - bei acht Eintraegen ohne Gliederung sucht man sonst.
const navGroups = computed(() => [
  {
    title: 'Überwachung',
    items: [
      { to: '/', name: 'Dashboard', icon: 'dashboard', label: 'Dashboard' },
      { to: '/logs', name: 'Logs', icon: 'logs', label: 'Logs' },
      { to: '/agents', name: 'Agents', icon: 'agents', label: 'Geräte' },
    ],
  },
  {
    title: 'Verwaltung',
    items: [
      { to: '/webhooks', name: 'Webhooks', icon: 'webhooks', label: 'Webhooks' },
      ...(auth.isAdmin ? [{ to: '/users', name: 'Users', icon: 'users', label: 'Benutzer' }] : []),
    ],
  },
  {
    title: 'System',
    items: [
      { to: '/settings', name: 'Settings', icon: 'settings', label: 'Einstellungen' },
      { to: '/settings/branding', name: 'BrandingSettings', icon: 'branding', label: 'Branding' },
      { to: '/health', name: 'Health', icon: 'health', label: 'Systemzustand' },
    ],
  },
])

// Die Geraete-Ansicht (/devices/<host>) gehoert sichtbar zu "Geräte".
function isActive(item) {
  if (route.name === item.name) return true
  return item.name === 'Agents' && route.name === 'DeviceLogs'
}

const pageTitle = computed(() => {
  if (route.name === 'DeviceLogs') return String(route.params.hostname || 'Gerät')
  for (const group of navGroups.value) {
    const hit = group.items.find(item => item.name === route.name)
    if (hit) return hit.label
  }
  return companyName.value
})

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
/* ------------------------------------------------------------------ Sidebar */
.sidebar {
  position: fixed;
  inset-block: 0;
  left: 0;
  z-index: 30;
  width: var(--sidebar-width);
  display: flex;
  flex-direction: column;
  background-color: var(--color-surface);
  border-right: 1px solid var(--color-border);
  transform: translateX(-100%);
  transition: transform var(--duration) var(--ease), width var(--duration) var(--ease);
}

.sidebar.is-open {
  transform: translateX(0);
}

@media (min-width: 768px) {
  .sidebar {
    position: relative;
    transform: none;
  }

  .sidebar.is-collapsed {
    width: var(--sidebar-width-collapsed);
  }
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  padding: 0.875rem 0.75rem;
  border-bottom: 1px solid var(--color-border);
  min-height: var(--header-height);
}

.is-collapsed .sidebar-brand {
  justify-content: center;
}

.brand-mark {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2.25rem;
  height: 2.25rem;
  border-radius: var(--radius);
  background-color: var(--primary-soft);
  color: var(--color-primary);
  font-weight: 700;
  flex-shrink: 0;
  overflow: hidden;
}

.brand-logo {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.brand-initial {
  font-size: 1rem;
  line-height: 1;
}

.brand-text {
  flex: 1;
  min-width: 0;
}

.brand-name {
  font-weight: 600;
  font-size: 0.9375rem;
  color: var(--color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.brand-version {
  font-size: 0.6875rem;
  color: var(--color-text-muted);
  font-variant-numeric: tabular-nums;
}

/* --------------------------------------------------------------- Navigation */
.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: 0.75rem 0.625rem;
}

.nav-group-title {
  padding: 0.75rem 0.75rem 0.375rem;
  font-size: 0.6875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-text-muted);
}

.is-collapsed .nav-group-title {
  padding-top: 0.5rem;
}

.nav-list {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

/* --------------------------------------------------------------- Fußbereich */
.sidebar-footer {
  padding: 0.625rem;
  border-top: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.user-row {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  width: 100%;
  padding: 0.5rem 0.625rem;
  border-radius: var(--radius);
  font-size: 0.875rem;
  color: var(--color-text-secondary);
  text-align: left;
}

.user-row:not(.user-row--static):hover {
  background-color: var(--hover-surface);
  color: var(--color-text-primary);
}

.avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.875rem;
  height: 1.875rem;
  border-radius: var(--radius-full);
  background-color: var(--color-surface-elevated);
  border: 1px solid var(--color-border);
  color: var(--color-text-primary);
  font-size: 0.8125rem;
  font-weight: 600;
  flex-shrink: 0;
}

.user-name {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-role {
  font-size: 0.6875rem;
  color: var(--color-text-muted);
}

.logout-btn:hover {
  background-color: var(--danger-soft);
  color: var(--color-danger);
}

/* ---------------------------------------------------------------- Kopfleiste */
.topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  min-height: var(--header-height);
  padding: 0 1rem;
  background-color: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
}

.topbar-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* -------------------------------------------------------------------- Footer */
.app-footer {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 1.5rem;
  font-size: 0.75rem;
  color: var(--color-text-muted);
  border-top: 1px solid var(--color-border);
  background-color: var(--color-surface);
}

/* ------------------------------------------------------------------ Übergang */
.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--duration) var(--ease);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

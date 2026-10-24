<!-- ==============================================================================
     Name:        Phydran6
     Kontakt:     Phydran6
     Changelog:   ../../../CHANGELOG/frontend.md
     Beschreibung: LogBot - Hauptlayout mit vollstaendig verschachteltem Seitenmenue.

     Was sich gegenueber der Vorgaenger-Fassung geaendert hat:

     * Das System hat seine Unterpunkte jetzt LINKS. Vorher lagen die
       Einstellungen als Reiterleiste rechts im Inhalt - man klickte sich in den
       Bereich und musste dort weitersuchen. Jetzt haengt alles am selben Baum:
       Bereich -> Eintrag -> Unterpunkt.
     * Einklappen klappt wirklich ein. Vorher blieben Text und Unterpunkte
       stehen, weil nur einzelne Elemente ausgeblendet wurden; jetzt schaltet
       die Sidebar auf eine reine Icon-Leiste um.
     * Der Pfeil ist immer da und zeigt in die Richtung, in die es geht:
       nach links zum Einklappen, nach rechts zum Ausklappen.
     ============================================================================== -->

<template>
  <div class="flex h-full" style="background-color: var(--color-bg)">
    <!-- Mobil: Overlay hinter der Sidebar -->
    <transition name="fade">
      <div
        v-if="sidebarOpen"
        class="fixed inset-0 z-20 md:hidden"
        style="background-color: var(--overlay)"
        @click="sidebarOpen = false"
      />
    </transition>

    <!-- ================================================================
         SEITENMENÜ
         ================================================================ -->
    <aside
      class="sidebar"
      :class="[sidebarOpen ? 'is-open' : '', isCollapsed ? 'is-collapsed' : '']"
    >
      <!-- Marke -->
      <div class="sidebar-brand">
        <router-link to="/" class="brand-mark" :title="companyName" @click="closeMobile">
          <img v-if="logoUrl" :src="logoUrl" :alt="companyName" class="brand-logo">
          <span v-else class="brand-initial">{{ brandInitial }}</span>
        </router-link>

        <div v-if="!isCollapsed" class="brand-text">
          <p class="brand-name">{{ companyName }}</p>
          <p class="brand-version">v{{ appVersion }}</p>
        </div>

        <!-- Mobil: schließen. Der Einklapp-Pfeil sitzt unten und ist immer sichtbar. -->
        <button
          class="btn-icon md:hidden"
          :title="t('nav.closeMenu')"
          :aria-label="t('nav.closeMenu')"
          @click="sidebarOpen = false"
        >
          <AppIcon name="close" :size="18" />
        </button>
      </div>

      <!-- ============================================================
           NAVIGATION - drei Ebenen, alle links
           ============================================================ -->
      <nav class="sidebar-nav" :aria-label="t('nav.system')">
        <div v-for="group in navGroups" :key="group.key" class="nav-group">
          <!-- Ebene 1: Bereich -->
          <button
            class="nav-row nav-group-btn"
            :class="{ 'is-open': isGroupOpen(group.key), 'has-active': activeGroupKey === group.key }"
            :title="isCollapsed ? group.title : null"
            :aria-expanded="isGroupOpen(group.key)"
            @click="toggleGroup(group.key)"
          >
            <AppIcon :name="group.icon" :size="18" class="shrink-0" />
            <template v-if="!isCollapsed">
              <span class="nav-label">{{ group.title }}</span>
              <AppIcon
                name="chevronDown"
                :size="16"
                class="nav-chevron shrink-0"
                :class="isGroupOpen(group.key) ? 'is-open' : ''"
              />
            </template>
            <!-- Eingeklappt: ein Punkt zeigt, dass in diesem Bereich die
                 aktuelle Seite liegt - sonst sähe man das am Icon nicht. -->
            <span v-else-if="activeGroupKey === group.key" class="nav-dot" />
          </button>

          <!-- Ebene 2: Einträge des Bereichs -->
          <ul v-if="isGroupOpen(group.key) && !isCollapsed" class="nav-list">
            <li v-for="item in group.items" :key="item.key">
              <!-- Ein Eintrag mit Unterpunkten ist selbst aufklappbar … -->
              <button
                v-if="item.children"
                class="nav-row nav-sub-row"
                :class="{ 'is-open': isItemOpen(item.key), 'has-active': isItemActive(item) }"
                :aria-expanded="isItemOpen(item.key)"
                @click="toggleItem(item.key)"
              >
                <AppIcon :name="item.icon" :size="16" class="shrink-0" />
                <span class="nav-label">{{ item.label }}</span>
                <AppIcon
                  name="chevronDown"
                  :size="14"
                  class="nav-chevron shrink-0"
                  :class="isItemOpen(item.key) ? 'is-open' : ''"
                />
              </button>

              <!-- … ein einfacher Eintrag ist einfach ein Link. -->
              <router-link
                v-else
                :to="item.to"
                class="nav-row nav-sub-row nav-link"
                :class="{ active: isActive(item) }"
                @click="closeMobile"
              >
                <AppIcon :name="item.icon" :size="16" class="shrink-0" />
                <span class="nav-label">{{ item.label }}</span>
                <span v-if="item.badge" class="nav-badge">{{ item.badge > 99 ? '99+' : item.badge }}</span>
              </router-link>

              <!-- Ebene 3: Unterpunkte -->
              <ul v-if="item.children && isItemOpen(item.key)" class="nav-list nav-list--deep">
                <li v-for="child in item.children" :key="child.to">
                  <router-link
                    :to="child.to"
                    class="nav-row nav-leaf-row nav-link"
                    :class="{ active: isActive(child) }"
                    @click="closeMobile"
                  >
                    <span class="nav-label">{{ child.label }}</span>
                  </router-link>
                </li>
              </ul>
            </li>
          </ul>
        </div>
      </nav>

      <!-- Fußbereich -->
      <div class="sidebar-footer">
        <!-- Der Pfeil: immer sichtbar, immer in die Richtung, in die es geht. -->
        <button
          class="nav-row footer-row collapse-btn hidden md:flex"
          :title="isCollapsed ? t('nav.expand') : t('nav.collapse')"
          :aria-label="isCollapsed ? t('nav.expand') : t('nav.collapse')"
          :aria-expanded="!collapsed"
          @click="toggleCollapsed"
        >
          <AppIcon :name="collapsed ? 'chevronRight' : 'chevronLeft'" :size="18" class="shrink-0" />
          <span v-if="!isCollapsed" class="nav-label">{{ t('nav.collapse') }}</span>
        </button>

        <!-- Sprache -->
        <div class="language-row">
          <button
            class="nav-row footer-row"
            :title="t('nav.language')"
            :aria-expanded="languageOpen"
            @click="languageOpen = !languageOpen"
          >
            <AppIcon name="globe" :size="18" class="shrink-0" />
            <template v-if="!isCollapsed">
              <span class="nav-label">{{ localeInfo.label }}</span>
              <AppIcon
                name="chevronDown"
                :size="14"
                class="nav-chevron shrink-0"
                :class="languageOpen ? 'is-open' : ''"
              />
            </template>
          </button>
          <ul v-if="languageOpen" class="language-list">
            <li v-for="option in locales" :key="option.code">
              <button
                class="nav-row language-option"
                :class="{ active: option.code === locale }"
                @click="chooseLocale(option.code)"
              >
                <span class="language-flag">{{ option.flag }}</span>
                <span v-if="!isCollapsed" class="nav-label">{{ option.label }}</span>
              </button>
            </li>
          </ul>
        </div>

        <!-- Design -->
        <button
          class="nav-row footer-row"
          :title="isDark ? t('nav.toLight') : t('nav.toDark')"
          @click="toggleTheme"
        >
          <AppIcon :name="isDark ? 'moon' : 'sun'" :size="18" class="shrink-0" />
          <span v-if="!isCollapsed" class="nav-label">
            {{ isDark ? t('nav.darkMode') : t('nav.lightMode') }}
          </span>
        </button>

        <!-- Benutzer -->
        <div class="nav-row footer-row footer-row--static">
          <span class="avatar" :title="auth.user?.username">{{ userInitial }}</span>
          <div v-if="!isCollapsed" class="min-w-0 flex-1">
            <p class="user-name">{{ auth.user?.username }}</p>
            <p class="user-role">{{ roleLabel }}</p>
          </div>
          <button
            v-if="!isCollapsed"
            class="btn-icon logout-btn"
            :title="t('nav.logout')"
            :aria-label="t('nav.logout')"
            @click="handleLogout"
          >
            <AppIcon name="logout" :size="18" />
          </button>
        </div>
        <!-- Eingeklappt braucht Abmelden eine eigene Zeile, sonst fehlt es. -->
        <button
          v-if="isCollapsed"
          class="nav-row footer-row hidden md:flex"
          :title="t('nav.logout')"
          :aria-label="t('nav.logout')"
          @click="handleLogout"
        >
          <AppIcon name="logout" :size="18" class="shrink-0" />
        </button>
      </div>
    </aside>

    <!-- ================================================================
         INHALT
         ================================================================ -->
    <main class="flex-1 overflow-auto min-w-0 flex flex-col">
      <header class="topbar">
        <button class="btn-icon md:hidden" :aria-label="t('nav.openMenu')" @click="sidebarOpen = true">
          <AppIcon name="menu" :size="20" />
        </button>
        <div class="min-w-0">
          <h1 class="topbar-title">{{ pageTitle }}</h1>
          <p v-if="breadcrumb" class="topbar-crumb">{{ breadcrumb }}</p>
        </div>
        <div class="flex-1" />

        <!-- Meldungen: Glocke mit Zahl der ungelesenen -->
        <router-link to="/notifications" class="bell" :title="t('nav.inbox')" :aria-label="t('nav.inbox')">
          <AppIcon name="bell" :size="18" />
          <span v-if="unread" class="bell-count">{{ unread > 99 ? '99+' : unread }}</span>
        </router-link>

        <!-- Meldet sich, sobald auf GitHub etwas Neues liegt -->
        <router-link v-if="updateNotice" to="/updates" class="update-pill" :title="updateNotice">
          <AppIcon name="download" :size="14" />
          <span class="hidden sm:inline">{{ t('updates.updateAvailable') }}</span>
        </router-link>

        <span class="badge badge-neutral hidden sm:inline-flex">{{ auth.user?.username }}</span>
      </header>

      <div class="flex-1">
        <router-view />
      </div>

      <!-- Pflicht: E-Mail-Adresse und ggf. neues Passwort, bevor es weitergeht -->
      <AccountGate />

      <!-- Die Fusszeile verweist auf die Herkunft statt einen Rechtevorbehalt
           zu behaupten, den es bei einer MIT-Lizenz gar nicht gibt. -->
      <footer class="app-footer">
        <span v-if="footerText">{{ footerText }}</span>
        <router-link to="/about" class="footer-link">{{ t('nav.about') }}</router-link>
      </footer>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useThemeStore } from '../stores/themeStore'
import { useBrandingStore } from '../stores/brandingStore'
import { useI18n } from '../i18n'
import AppIcon from '../components/AppIcon.vue'
import AccountGate from '../components/AccountGate.vue'
import { openTicketStream } from '../utils/stream'
import pkg from '../../package.json'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const themeStore = useThemeStore()
const brandingStore = useBrandingStore()
const { t, locale, locales, localeInfo, setLocale } = useI18n()

const appVersion = pkg.version

const sidebarOpen = ref(false)
const languageOpen = ref(false)

const COLLAPSE_KEY = 'logbot.sidebarCollapsed'
const OPEN_GROUP_KEY = 'logbot.sidebarGroup'

function readStored(key, fallback = '') {
  try {
    return localStorage.getItem(key) ?? fallback
  } catch {
    return fallback
  }
}

function writeStored(key, value) {
  try {
    localStorage.setItem(key, value)
  } catch {
    // Kein localStorage (Privat-Modus) - der Zustand gilt nur für diese Sitzung.
  }
}

const collapsed = ref(readStored(COLLAPSE_KEY) === '1')

// Nur am Desktop gibt es die Icon-Leiste. Auf dem Handy ist die Sidebar ein
// Overlay - dort wäre "eingeklappt" sinnlos, man hat ja den ganzen Bildschirm.
const isDesktopWidth = ref(true)
let mediaQuery = null

function syncWidth(event) {
  isDesktopWidth.value = event.matches
}

onMounted(() => {
  if (typeof window === 'undefined' || !window.matchMedia) return
  mediaQuery = window.matchMedia('(min-width: 768px)')
  isDesktopWidth.value = mediaQuery.matches
  mediaQuery.addEventListener('change', syncWidth)
})

onBeforeUnmount(() => {
  mediaQuery?.removeEventListener('change', syncWidth)
})

/** Wirklich eingeklappt ist nur, was am Desktop eingeklappt ist. */
const isCollapsed = computed(() => collapsed.value && isDesktopWidth.value)

watch(collapsed, (value) => writeStored(COLLAPSE_KEY, value ? '1' : '0'))

// Eingeklappt ist für die Sprachliste kein Platz - sie würde über den Rand
// hinauslaufen. Also zumachen, sobald eingeklappt wird.
watch(isCollapsed, (value) => {
  if (value) languageOpen.value = false
})

const isDark = computed(() => themeStore.currentTheme === 'dark')
const companyName = computed(() => brandingStore.config?.company_name || 'LogBot')
const footerText = computed(() => brandingStore.config?.footer_text || '')
const logoUrl = computed(() => brandingStore.getLogoUrl())
const brandInitial = computed(() => (companyName.value || 'L').trim().charAt(0).toUpperCase())
const userInitial = computed(() => (auth.user?.username || '?').trim().charAt(0).toUpperCase())
const roleLabel = computed(() => (
  auth.user?.role === 'admin' ? t('nav.administrator') : t('nav.user')
))

// Ungelesene Meldungen - für die Glocke oben und die Zahl im Menü.
const unread = ref(0)

// =============================================================================
// Navigation
// =============================================================================
// Drei Ebenen: Bereich -> Eintrag -> Unterpunkt. `match` nennt weitere Routen,
// bei denen ein Eintrag als aktiv gilt (z.B. die Geräte-Ansicht unter "Geräte").
// `tab` zeigt auf einen Reiter der Einstellungsseite - so hängen auch die
// Einstellungen komplett am linken Baum statt an einer Leiste rechts.
//
// Der Aufbau folgt Fragen, nicht Technik. Jeder Bereich beantwortet genau eine:
//
//   Überwachung   Was ist im Netz passiert?
//   Meldungen     Wer muss davon erfahren - und wie (Mail, Telegram, App)?
//   Auswertung    Was mache ich damit?
//   Agents        Womit liefern die Geräte, in welcher Fassung, wie viel?
//   Verwaltung    Wer darf was, und wie lange werden Daten aufgehoben?
//   Mein Konto    Meine Adresse, mein Passwort, meine Anmeldung.
//   System        Womit läuft das hier, und was tut es gerade?
//   Hilfe         Was ist das eigentlich, und wo kommt es her?
//
// Neu 2026.10.23: Es gibt KEINE Auswahlleisten mehr im Inhaltsbereich. Was
// früher als Reiter rechts stand (Einstellungen, Netzwerk → Proxy/DNS), hängt
// jetzt als Unterpunkt hier im Baum. Ebene 1 = Bereich, Ebene 2 = Seite oder
// Gruppe, Ebene 3 = Seite. Tiefer geht es nicht.
//
// Die Trennlinie zwischen Verwaltung und System ist bewusst diese: Verwaltung
// handelt von Menschen und Daten, System von der Maschine. Vorher lagen
// Passwort, LDAP, Datenbank, Netzwerk und Erscheinungsbild alle im selben
// Reiterstapel unter „Einstellungen" — richtig zu raten, wo etwas steckt, war
// Glückssache.
const navGroups = computed(() => {
  const admin = auth.isAdmin
  const onlyAdmin = (entries) => (admin ? entries : [])

  return [
    // --- Was ist im Netz passiert? -----------------------------------------
    {
      key: 'monitoring',
      title: t('nav.monitoring'),
      icon: 'dashboard',
      items: [
        { key: 'dashboard', to: '/', name: 'Dashboard', icon: 'dashboard', label: t('nav.dashboard') },
        { key: 'logs', to: '/logs', name: 'Logs', icon: 'logs', label: t('nav.logs') },
        { key: 'agents', to: '/agents', name: 'Agents', icon: 'devices', label: t('nav.devices'), match: ['DeviceLogs'] },
        ...onlyAdmin([{ key: 'discovery', to: '/discovery', name: 'Discovery', icon: 'network', label: t('nav.discovery') }]),
        { key: 'health', to: '/health', name: 'Health', icon: 'health', label: t('nav.health') },
      ],
    },
    // --- Wer muss davon erfahren? -------------------------------------------
    {
      key: 'notifications',
      title: t('nav.notifications'),
      icon: 'bell',
      items: [
        { key: 'inbox', to: '/notifications', name: 'Notifications', icon: 'bell', label: t('nav.inbox'), badge: unread.value },
        ...onlyAdmin([
          { key: 'rules', to: '/notifications/rules', name: 'NotificationRules', icon: 'filter', label: t('nav.rules') },
          { key: 'watch', to: '/alerts', name: 'Alerts', icon: 'health', label: t('nav.alerts') },
          {
            key: 'channels', icon: 'mail', label: t('nav.channels'), children: [
              { to: '/notifications/mail', name: 'NotifyMail', label: t('nav.mail') },
              { to: '/notifications/telegram', name: 'NotifyTelegram', label: t('nav.telegram') },
              { to: '/notifications/app', name: 'NotifyApp', label: t('nav.pushApp') },
            ],
          },
        ]),
      ],
    },
    // --- Was mache ich damit? -----------------------------------------------
    {
      key: 'analysis',
      title: t('nav.analysis'),
      icon: 'ai',
      items: [
        ...onlyAdmin([{ key: 'ai', to: '/ai', name: 'AiSettings', icon: 'ai', label: t('nav.ai'), match: ['OpenRouterCallback'] }]),
        { key: 'webhooks', to: '/webhooks', name: 'Webhooks', icon: 'webhooks', label: t('nav.webhooks') },
        { key: 'app', to: '/app', name: 'AppQR', icon: 'mobile', label: t('nav.app') },
      ],
    },
    // --- Womit liefern die Geraete? (nur Admin) -----------------------------
    ...onlyAdmin([{
      key: 'agentAdmin',
      title: t('nav.agentAdmin'),
      icon: 'agents',
      items: [
        { key: 'agentUpdates', to: '/agents/updates', name: 'AgentUpdates', icon: 'download', label: t('nav.agentUpdates') },
        { key: 'agentTokens', to: '/agents/tokens', name: 'AgentTokens', icon: 'key', label: t('nav.agentTokens') },
        { key: 'agentDefaults', to: '/agents/limits', name: 'AgentDefaults', icon: 'filter', label: t('nav.agentLimits') },
      ],
    }]),
    // --- Wer darf was, wie lange bleiben Daten? -----------------------------
    {
      key: 'management',
      title: t('nav.management'),
      icon: 'users',
      items: [
        ...onlyAdmin([
          { key: 'users', to: '/users', name: 'Users', icon: 'users', label: t('nav.users') },
          {
            key: 'signin', icon: 'shield', label: t('nav.signin'), children: [
              { to: '/sso', name: 'SsoSettings', label: t('nav.sso') },
              { to: '/settings/ldap', name: 'Settings', tab: 'ldap', label: t('nav.ldap') },
            ],
          },
        ]),
        {
          key: 'data', icon: 'database', label: t('nav.data'), children: [
            { to: '/settings/retention', name: 'Settings', tab: 'retention', label: t('nav.retention') },
            ...onlyAdmin([
              { to: '/storage', name: 'Storage', label: t('nav.storage') },
              { to: '/settings/archiving', name: 'Settings', tab: 'archiving', label: t('nav.archiving') },
              { to: '/settings/database', name: 'Settings', tab: 'database', label: t('nav.database') },
            ]),
          ],
        },
      ],
    },
    // --- Mein Konto ---------------------------------------------------------
    {
      key: 'account',
      title: t('nav.account'),
      icon: 'lock',
      items: [
        { key: 'profile', to: '/account', name: 'Account', icon: 'mail', label: t('nav.profile') },
        { key: 'security', to: '/settings/security', name: 'Settings', tab: 'security', icon: 'shield', label: t('nav.security') },
      ],
    },
    // --- Womit laeuft das hier? ---------------------------------------------
    {
      key: 'system',
      title: t('nav.system'),
      icon: 'settings',
      items: [
        ...onlyAdmin([
          {
            key: 'operation', icon: 'refresh', label: t('nav.operation'), children: [
              { to: '/updates', name: 'Updates', label: t('nav.updates') },
              { to: '/backup', name: 'Backup', label: t('nav.backup') },
              { to: '/journal', name: 'Journal', label: t('nav.journal') },
              { to: '/terminal', name: 'Terminal', label: t('nav.console') },
            ],
          },
          {
            key: 'services', icon: 'stacks', label: t('nav.containers'), children: [
              { to: '/containers', name: 'Containers', label: t('nav.containerOverview') },
              { to: '/stacks', name: 'Stacks', label: t('nav.stacks') },
            ],
          },
          {
            key: 'network', icon: 'globe', label: t('nav.network'), children: [
              { to: '/settings/proxy', name: 'Settings', tab: 'proxy', label: t('nav.proxy') },
              { to: '/settings/dns', name: 'Settings', tab: 'dns', label: t('nav.dns') },
            ],
          },
        ]),
        {
          key: 'preferences', icon: 'settings', label: t('nav.settings'), children: [
            ...onlyAdmin([{ to: '/settings/general', name: 'Settings', tab: 'general', label: t('nav.general') }]),
            { to: '/settings/branding', name: 'Settings', tab: 'branding', label: t('nav.branding') },
            ...onlyAdmin([{ to: '/settings/maintenance', name: 'Settings', tab: 'maintenance', label: t('nav.maintenance') }]),
          ],
        },
      ],
    },
    // --- Was ist das eigentlich? --------------------------------------------
    {
      key: 'help',
      title: t('nav.help'),
      icon: 'help',
      items: [
        { key: 'about', to: '/about', name: 'About', icon: 'help', label: t('nav.about') },
      ],
    },
  ]
})

/** Ist dieser Eintrag (oder Unterpunkt) gerade offen? */
function isActive(entry) {
  if (entry.tab) {
    // Ohne Reiter in der Adresse gilt "general" - so ist /settings nie ohne
    // markierten Unterpunkt.
    const current = String(route.params.tab || 'general')
    return route.name === 'Settings' && current === entry.tab
  }
  if (route.name === entry.name) return true
  return Array.isArray(entry.match) && entry.match.includes(route.name)
}

function isItemActive(item) {
  if (item.children) return item.children.some(child => isActive(child))
  return isActive(item)
}

const activeGroupKey = computed(() => {
  for (const group of navGroups.value) {
    if (group.items.some(item => isItemActive(item))) return group.key
  }
  return ''
})

const activeItemKey = computed(() => {
  for (const group of navGroups.value) {
    const hit = group.items.find(item => isItemActive(item))
    if (hit) return hit.key
  }
  return ''
})

const openGroup = ref(readStored(OPEN_GROUP_KEY) || activeGroupKey.value || 'monitoring')
const openItem = ref(activeItemKey.value)

// Beim Seitenwechsel den passenden Zweig offen halten - sonst klappt das Menü
// unter einem weg, sobald man einen Unterpunkt anklickt.
watch(activeGroupKey, (key) => {
  if (key) {
    openGroup.value = key
    writeStored(OPEN_GROUP_KEY, key)
  }
})
watch(activeItemKey, (key) => {
  if (key) openItem.value = key
})

function isGroupOpen(key) {
  return openGroup.value === key
}

function isItemOpen(key) {
  return openItem.value === key
}

function toggleGroup(key) {
  // Eingeklappt am Desktop: erst ausklappen, dann den Bereich öffnen. Sonst
  // klickt man auf ein Icon und es passiert sichtbar nichts.
  if (isCollapsed.value) {
    collapsed.value = false
    openGroup.value = key
    return
  }
  openGroup.value = openGroup.value === key ? '' : key
  if (openGroup.value) writeStored(OPEN_GROUP_KEY, openGroup.value)
}

function toggleItem(key) {
  openItem.value = openItem.value === key ? '' : key
}

function toggleCollapsed() {
  collapsed.value = !collapsed.value
}

function closeMobile() {
  sidebarOpen.value = false
}

function chooseLocale(code) {
  setLocale(code)
  languageOpen.value = false
}

// =============================================================================
// Kopfzeile
// =============================================================================
const pageTitle = computed(() => {
  if (route.name === 'DeviceLogs') return String(route.params.hostname || t('nav.devices'))
  for (const group of navGroups.value) {
    for (const item of group.items) {
      if (item.children) {
        const child = item.children.find(entry => isActive(entry))
        if (child) return child.label
      } else if (isActive(item)) {
        return item.label
      }
    }
  }
  return companyName.value
})

/** "System · Einstellungen" - zeigt, wo im Baum man gerade steht. */
const breadcrumb = computed(() => {
  for (const group of navGroups.value) {
    for (const item of group.items) {
      if (item.children && item.children.some(entry => isActive(entry))) {
        return `${group.title} · ${item.label}`
      }
      if (!item.children && isActive(item)) return group.title
    }
  }
  return ''
})

// =============================================================================
// Sofortmeldung bei neuem Stand
// =============================================================================
// Der Server meldet sich von selbst (Server-Sent Events, siehe backend
// app/events.py). Ohne das müsste die Seite im Takt nachfragen - und man sähe
// den Hinweis erst beim nächsten Klick.
const updateNotice = ref('')
let closeStream = null
let unreadTimer = null

async function refreshUnread() {
  try {
    const data = await auth.api('/api/notifications/unread')
    unread.value = data.unread_count || 0
  } catch {
    // Kein Netz oder abgemeldet - die Zahl bleibt, wie sie ist.
  }
}

function listenForUpdates() {
  if (!auth.isAdmin || typeof EventSource === 'undefined') return
  // Ticket statt Zugangstoken in der Adresse (utils/stream.js).
  closeStream = openTicketStream('/api/updates/stream', {
    'update.available': (data) => {
      updateNotice.value = data?.reason || t('updates.updateAvailable')
    },
    'update.cleared': () => { updateNotice.value = '' },
    'notification.new': () => { refreshUnread() },
  })
}

onMounted(() => {
  listenForUpdates()
  refreshUnread()
  // Nicht-Admins haben keinen Ereignisstrom - für sie reicht ein ruhiger Takt.
  unreadTimer = setInterval(refreshUnread, auth.isAdmin ? 120000 : 60000)
  window.addEventListener('logbot:notifications-read', refreshUnread)
})
onBeforeUnmount(() => {
  closeStream?.()
  clearInterval(unreadTimer)
  window.removeEventListener('logbot:notifications-read', refreshUnread)
})

function toggleTheme() {
  themeStore.toggleTheme()
}

function handleLogout() {
  closeStream?.()
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
  padding-inline: 0.5rem;
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
  overflow-x: hidden;
  padding: 0.75rem 0.625rem;
}

.is-collapsed .sidebar-nav {
  padding-inline: 0.5rem;
}

.nav-group + .nav-group {
  margin-top: 0.25rem;
}

/* Eine Zeile im Menü - egal auf welcher Ebene. */
.nav-row {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  width: 100%;
  padding: 0.5rem 0.75rem;
  border-radius: var(--radius);
  font-size: 0.875rem;
  color: var(--color-text-secondary);
  cursor: pointer;
  text-align: left;
  transition: background-color var(--duration) var(--ease), color var(--duration) var(--ease);
}

.nav-row:hover {
  background-color: var(--hover-surface);
  color: var(--color-text-primary);
}

/* Eingeklappt: nur das Icon, mittig. */
.is-collapsed .nav-row {
  justify-content: center;
  padding-inline: 0.5rem;
  position: relative;
}

.nav-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nav-group-btn {
  font-weight: 600;
}

.nav-group-btn.has-active {
  color: var(--color-text-primary);
}

/* Eingeklappt bleibt vom aktiven Bereich nur dieser Punkt übrig. */
.nav-dot {
  position: absolute;
  right: 0.375rem;
  top: 0.5rem;
  width: 0.375rem;
  height: 0.375rem;
  border-radius: var(--radius-full);
  background-color: var(--color-primary);
}

.nav-chevron {
  transition: transform var(--duration) var(--ease);
}

.nav-chevron.is-open {
  transform: rotate(180deg);
}

.nav-list {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
  margin: 0.125rem 0 0.375rem 1.0625rem;
  padding-left: 0.875rem;
  border-left: 1px solid var(--color-border);
}

/* Dritte Ebene: noch eine Stufe eingerückt, ohne Icon. */
.nav-list--deep {
  margin-left: 0.5rem;
  padding-left: 0.75rem;
}

.nav-sub-row {
  font-size: 0.8125rem;
}

.nav-leaf-row {
  font-size: 0.8125rem;
  padding-block: 0.375rem;
}

.nav-sub-row.has-active {
  color: var(--color-text-primary);
  font-weight: 600;
}

/* --------------------------------------------------------------- Fußbereich */
.sidebar-footer {
  padding: 0.625rem;
  border-top: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.is-collapsed .sidebar-footer {
  padding-inline: 0.5rem;
}

.footer-row {
  padding-block: 0.5rem;
}

.footer-row--static {
  cursor: default;
}

.footer-row--static:hover {
  background-color: transparent;
}

.collapse-btn {
  color: var(--color-text-muted);
}

/* ----------------------------------------------------------------- Sprache */
.language-row {
  position: relative;
}

.language-list {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
  margin: 0.125rem 0 0.25rem;
}

.is-collapsed .language-list {
  margin-left: 0;
}

.language-option {
  font-size: 0.8125rem;
  padding-block: 0.375rem;
}

.language-option.active {
  color: var(--color-primary);
  font-weight: 600;
}

.language-flag {
  font-size: 1rem;
  line-height: 1;
  flex-shrink: 0;
}

/* ---------------------------------------------------------------- Benutzer */
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

/* -------------------------------------------------------------- Kopfleiste */
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

.topbar-crumb {
  font-size: 0.6875rem;
  color: var(--color-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bell {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.25rem;
  height: 2.25rem;
  border-radius: var(--radius);
  color: var(--color-text-secondary);
}

.bell:hover {
  background-color: var(--hover-surface);
  color: var(--color-text-primary);
}

.bell-count,
.nav-badge {
  min-width: 1.125rem;
  height: 1.125rem;
  padding: 0 0.3125rem;
  border-radius: var(--radius-full);
  background-color: var(--color-danger);
  color: #fff;
  font-size: 0.6875rem;
  font-weight: 700;
  line-height: 1.125rem;
  text-align: center;
}

.bell-count {
  position: absolute;
  top: 0.125rem;
  right: 0.0625rem;
}

.update-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.3125rem 0.625rem;
  border-radius: var(--radius-full);
  font-size: 0.75rem;
  font-weight: 600;
  background-color: var(--primary-soft);
  color: var(--color-primary);
}

.update-pill:hover {
  filter: brightness(1.1);
}

/* ------------------------------------------------------------------ Footer */
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

.footer-link {
  margin-left: auto;
  color: var(--color-primary);
  text-decoration: none;
}

.footer-link:hover {
  text-decoration: underline;
}

/* ---------------------------------------------------------------- Übergang */
.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--duration) var(--ease);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

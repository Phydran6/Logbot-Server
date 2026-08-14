/**
 * ==============================================================================
 * Name:           Phydran6
 * Kontakt:        Phydran6
 * Version:        2026.08.14.12.00.00
 * Changelog:      ../../../CHANGELOG/frontend.md
 * ==============================================================================
 *
 * LogBot Vue Router - Navigation und Route-Definitionen
 * ======================================================
 * Drei Bereiche: Überwachung, Verwaltung, System.
 *
 * Alles, was zum System gehört (Netzwerk, Datenbank, Verzeichnis, Archivierung,
 * Erscheinungsbild, Anmeldesicherheit), liegt unter /settings als Reiter. Die
 * alten Adressen wie /settings/ldap funktionieren weiter: der Teil hinter
 * /settings wählt den Reiter aus.
 *
 * ==============================================================================
 */

import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

// =============================================================================
// Route-Definitionen
// =============================================================================
const routes = [
  // ---------------------------------------------------------------------------
  // Öffentliche Route: Login
  // ---------------------------------------------------------------------------
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { public: true }
  },

  // ---------------------------------------------------------------------------
  // Geschützte Routen: Hauptlayout mit Sidebar
  // ---------------------------------------------------------------------------
  {
    path: '/',
    component: () => import('../views/Layout.vue'),
    children: [
      // --- Überwachung -------------------------------------------------------
      {
        path: '',
        name: 'Dashboard',
        component: () => import('../views/Dashboard.vue')
      },
      {
        path: 'logs',
        name: 'Logs',
        component: () => import('../views/Logs.vue')
      },
      {
        path: 'agents',
        name: 'Agents',
        component: () => import('../views/Agents.vue')
      },
      {
        path: 'devices/:hostname',
        name: 'DeviceLogs',
        component: () => import('../views/DeviceLogs.vue')
      },

      // --- Verwaltung --------------------------------------------------------
      {
        path: 'webhooks',
        name: 'Webhooks',
        component: () => import('../views/Webhooks.vue')
      },
      {
        path: 'users',
        name: 'Users',
        component: () => import('../views/Users.vue'),
        meta: { admin: true }
      },

      // --- System ------------------------------------------------------------
      // Ein Ziel für alle Einstellungen. Der optionale Teil hinter /settings
      // wählt den Reiter (z.B. /settings/ldap).
      {
        path: 'settings/:tab?',
        name: 'Settings',
        component: () => import('../views/Settings.vue')
      },
      {
        path: 'health',
        name: 'Health',
        component: () => import('../views/Health.vue')
      },
      {
        path: 'updates',
        name: 'Updates',
        component: () => import('../views/Updates.vue'),
        meta: { admin: true }
      },
    ]
  },

  // ---------------------------------------------------------------------------
  // Unbekannte Adresse: zurück auf das Dashboard statt leere Seite
  // ---------------------------------------------------------------------------
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

// =============================================================================
// Router-Instanz erstellen
// =============================================================================
const router = createRouter({
  history: createWebHistory(),
  routes
})

// =============================================================================
// Navigation Guard - Auth-Prüfung
// =============================================================================
router.beforeEach(async (to, from, next) => {
  const auth = useAuthStore()

  // Öffentliche Routen durchlassen
  if (to.meta.public) return next()

  // Kein Token = zum Login
  if (!auth.token) return next('/login')

  // User-Daten laden falls noch nicht vorhanden
  if (!auth.user) {
    try {
      await auth.fetchUser()
    } catch {
      return next('/login')
    }
  }

  // Admin-Bereiche: Nicht-Admins landen auf dem Dashboard statt in einer
  // Ansicht, die ihnen ohnehin nur Fehler zeigen würde.
  if (to.meta.admin && !auth.isAdmin) return next('/')

  next()
})

export default router

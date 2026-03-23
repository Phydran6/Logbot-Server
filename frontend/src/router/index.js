/**
 * ==============================================================================
 * Name:           Phil Fischer
 * E-Mail:         p.fischer@phytech.de
 * Version:        20.02.2026.12.00.00
 * ==============================================================================
 * 
 * LogBot Vue Router - Navigation und Route-Definitionen
 * ======================================================
 * Definiert alle verfügbaren Routen der Anwendung.
 * Enthält Auth-Guard für geschützte Bereiche.
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
      // Dashboard (Startseite)
      { 
        path: '', 
        name: 'Dashboard', 
        component: () => import('../views/Dashboard.vue') 
      },
      
      // Log-Ansicht
      { 
        path: 'logs', 
        name: 'Logs', 
        component: () => import('../views/Logs.vue') 
      },
      
      // Agenten-Verwaltung
      { 
        path: 'agents', 
        name: 'Agents', 
        component: () => import('../views/Agents.vue') 
      },

      // Agent Tokens (HTTPS Agents)
      { 
        path: 'agent-tokens', 
        name: 'AgentTokens', 
        component: () => import('../views/AgentTokens.vue') 
      },
      
      // Benutzer-Verwaltung
      { 
        path: 'users', 
        name: 'Users', 
        component: () => import('../views/Users.vue') 
      },
      
      // Webhooks
      { 
        path: 'webhooks', 
        name: 'Webhooks', 
        component: () => import('../views/Webhooks.vue') 
      },
      
      // Allgemeine Einstellungen
      { 
        path: 'settings', 
        name: 'Settings', 
        component: () => import('../views/Settings.vue') 
      },
      
      // System-Health
      { 
        path: 'health', 
        name: 'Health', 
        component: () => import('../views/Health.vue') 
      },
      
      // Branding-Einstellungen (NEU)
      { 
        path: 'settings/branding', 
        name: 'BrandingSettings', 
        component: () => import('../views/BrandingSettings.vue') 
      }
    ]
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
  
  next()
})

export default router

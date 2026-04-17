<!--
================================================================================
Name:           Phil Fischer
E-Mail:         p.fischer@phytech.de & Phydran6
Version:        2026.04.17.15.17.18
================================================================================

LogBot App.vue - Hauptkomponente mit Branding
=============================================
Lädt beim Start die Branding-Konfiguration vom Backend.
Tailwind-kompatibel - überschreibt keine bestehenden Styles.

================================================================================
-->

<template>
  <router-view />
  <CookieBanner />
</template>

<script setup>
import { onMounted } from 'vue'
import { useBrandingStore } from './stores/brandingStore'
import { useThemeStore } from './stores/themeStore'
import CookieBanner from './components/CookieBanner.vue'

const brandingStore = useBrandingStore()
const themeStore = useThemeStore()

onMounted(async () => {
  try {
    // Branding-Config vom Backend laden
    await brandingStore.loadConfig()
  } catch (error) {
    console.error('[App] Branding laden fehlgeschlagen:', error)
    // Fallback: Dark Mode als Default
    themeStore.initTheme('dark')
  }
})
</script>
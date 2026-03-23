<!--
================================================================================
Name:           Phil Fischer
E-Mail:         p.fischer@phytech.de & p.fischer@itconex.de
Version:        30.01.2026.18.33.05
================================================================================

LogBot App.vue - Hauptkomponente mit Branding
=============================================
Lädt beim Start die Branding-Konfiguration vom Backend.
Tailwind-kompatibel - überschreibt keine bestehenden Styles.

================================================================================
-->

<template>
  <router-view />
</template>

<script setup>
import { onMounted } from 'vue'
import { useBrandingStore } from './stores/brandingStore'
import { useThemeStore } from './stores/themeStore'

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
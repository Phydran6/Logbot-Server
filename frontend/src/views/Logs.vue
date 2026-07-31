<!-- ==============================================================================
     Name:        Phydran6
     Kontakt:     Phydran6
     Version:     2026.07.31.21.10.00
     Beschreibung: LogBot - Log-Ansicht ueber alle Hosts.
                   Filter/Tabelle/Export stecken in components/LogTable.vue und
                   werden mit der Geraete-Ansicht (DeviceLogs.vue) geteilt.
     ============================================================================== -->

<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-4">
      <h1 class="text-2xl font-bold" :style="{ color: 'var(--color-text-primary)' }">Logs</h1>
      <router-link
        to="/agents"
        class="text-sm hover:underline"
        :style="{ color: 'var(--color-primary)' }"
      >Geräte-Übersicht →</router-link>
    </div>

    <LogTable sync-url />
  </div>
</template>

<script setup>
import LogTable from '../components/LogTable.vue'
</script>

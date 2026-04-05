<!-- ==============================================================================
     Name:        Philipp Fischer
     Kontakt:     p.fischer@itconex.de
     Version:     2026.04.05
     Beschreibung: LogBot - Cookie-Einwilligungsbanner
     ============================================================================== -->

<template>
  <Transition name="cookie-slide">
    <div
      v-if="visible"
      class="fixed bottom-0 left-0 right-0 z-50 p-4"
      :style="{ backgroundColor: 'var(--color-surface)', borderTop: '1px solid var(--color-border)' }"
    >
      <div class="max-w-5xl mx-auto flex flex-col sm:flex-row items-start sm:items-center gap-4">
        <div class="flex-1">
          <p class="text-sm font-medium mb-1" :style="{ color: 'var(--color-text-primary)' }">
            🍪 Diese Anwendung verwendet Cookies
          </p>
          <p class="text-xs" :style="{ color: 'var(--color-text-muted)' }">
            Wir verwenden technisch notwendige Cookies und lokalen Browserspeicher für Authentifizierung
            und Theme-Einstellungen. Weitere Informationen finden Sie in unserer
            <router-link to="/datenschutz" class="underline hover:opacity-80">Datenschutzerklärung</router-link>.
          </p>
        </div>
        <div class="flex gap-2 shrink-0">
          <button
            @click="decline"
            class="px-4 py-2 text-sm rounded border"
            :style="{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)', backgroundColor: 'var(--color-surface-elevated)' }"
          >
            Nur notwendige
          </button>
          <button
            @click="accept"
            class="px-4 py-2 text-sm rounded font-medium text-white"
            :style="{ backgroundColor: 'var(--color-primary)' }"
          >
            Alle akzeptieren
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const visible = ref(false)

onMounted(() => {
  const consent = localStorage.getItem('logbot-cookie-consent')
  if (!consent) {
    visible.value = true
  }
})

function accept() {
  localStorage.setItem('logbot-cookie-consent', 'all')
  visible.value = false
}

function decline() {
  localStorage.setItem('logbot-cookie-consent', 'necessary')
  visible.value = false
}
</script>

<style scoped>
.cookie-slide-enter-active,
.cookie-slide-leave-active {
  transition: transform 0.3s ease, opacity 0.3s ease;
}

.cookie-slide-enter-from,
.cookie-slide-leave-to {
  transform: translateY(100%);
  opacity: 0;
}
</style>

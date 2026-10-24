<!-- ==============================================================================
     Name:        Phydran6
     Kontakt:     Phydran6
     Changelog:   ../../../CHANGELOG/frontend.md
     Beschreibung: LogBot - Meldungen → Kanäle → App & Push.

     Die App holt Meldungen aus dem Eingang (/api/app/notifications) und kann
     sich zusätzlich für Push anmelden - über UnifiedPush (z.B. ntfy), ohne
     Google-Konto. Der Server verschlüsselt jede Nachricht nach RFC 8291; der
     Verteiler sieht nur, DASS etwas kam, nicht was.
     ============================================================================== -->
<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2 class="page-title">App & Push</h2>
        <p class="page-subtitle">Meldungen in der LogBot-App – im Eingang immer, auf Wunsch zusätzlich als Push.</p>
      </div>
    </div>

    <p v-if="banner" class="card card-body mb-4 text-sm" :style="{ color: bannerError ? 'var(--color-danger)' : 'var(--color-success)' }">{{ banner }}</p>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div class="card">
        <div class="card-header"><span class="card-title">So kommt die App an Meldungen</span></div>
        <div class="card-body text-sm space-y-2" style="color: var(--color-text-secondary)">
          <p><b>1. App verbinden</b> – unter <router-link to="/app" class="link">Auswertung → App verbinden</router-link> den QR-Code scannen oder in der App mit Benutzername/E-Mail anmelden.</p>
          <p><b>2. Push einschalten</b> – in der App unter Einstellungen. Gebraucht wird ein UnifiedPush-Verteiler auf dem Handy, z.B. die App <i>ntfy</i>. Die App meldet sich dann selbst hier an.</p>
          <p><b>3. Regeln</b> – welche Ereignisse als Push kommen, steht unter <router-link to="/notifications/rules" class="link">Meldungen → Regeln</router-link> (Kanal „Push aufs Handy“).</p>
          <p class="hint">Inhalt eines Push: nur Schweregrad und Überschrift, verschlüsselt (RFC 8291, VAPID). Den Rest holt die App angemeldet vom Server.</p>
        </div>
      </div>

      <div class="card">
        <div class="card-header"><span class="card-title">Meine Geräte</span>
          <button class="btn btn-secondary btn-sm" :disabled="!devices.length || busy" @click="test">Test-Push</button></div>
        <div class="card-body">
          <p v-if="!devices.length" class="text-sm" style="color: var(--color-text-muted)">Für dieses Konto ist noch kein Handy für Push angemeldet.</p>
          <ul class="space-y-2">
            <li v-for="d in devices" :key="d.id" class="flex flex-wrap items-center gap-2 text-sm">
              <AppIcon name="mobile" :size="16" />
              <b>{{ d.device_name || 'Gerät' }}</b>
              <span class="badge" :class="d.encrypted ? 'badge-success' : 'badge-warning'">{{ d.encrypted ? 'verschlüsselt' : 'unverschlüsselt' }}</span>
              <span class="badge badge-neutral">ab {{ d.min_severity }}</span>
              <span v-if="d.last_error" class="hint" style="color: var(--color-danger)">{{ d.last_error }}</span>
              <span v-else-if="d.last_ok_at" class="hint">zuletzt zugestellt {{ new Date(d.last_ok_at + 'Z').toLocaleString('de-DE') }}</span>
            </li>
          </ul>
          <p class="hint mt-4">Öffentlicher VAPID-Schlüssel des Servers (für die App):</p>
          <code class="vapid">{{ vapid }}</code>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import AppIcon from '../components/AppIcon.vue'

const auth = useAuthStore()
const devices = ref([])
const vapid = ref('')
const busy = ref(false)
const banner = ref('')
const bannerError = ref(false)

async function load() {
  devices.value = (await auth.api('/api/app/push')).items
  vapid.value = (await auth.api('/api/app/push/vapid')).public_key
}

async function test() {
  busy.value = true
  try {
    const data = await auth.api('/api/app/push/test', { method: 'POST' })
    const failed = data.results.filter(r => !r.ok)
    banner.value = failed.length ? `Nicht zugestellt: ${failed.map(f => `${f.device_name}: ${f.message}`).join(' · ')}` : 'Test-Push verschickt.'
    bannerError.value = !!failed.length
    await load()
  } catch (e) {
    banner.value = e.message
    bannerError.value = true
  } finally {
    busy.value = false
  }
}

onMounted(() => load().catch(e => { banner.value = e.message; bannerError.value = true }))
</script>

<style scoped>
.link { color: var(--color-primary); }

.vapid {
  display: block;
  word-break: break-all;
  font-size: 0.75rem;
  color: var(--color-text-secondary);
}
</style>

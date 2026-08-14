<!-- ==============================================================================
     Name:        Phydran6
     Kontakt:     Phydran6
     Version:     2026.08.14.12.00.00
     Changelog:   ../../../CHANGELOG/frontend.md
     Beschreibung: LogBot - Updates: Stand gegen GitHub prüfen, einspielen,
                   zurückfallen. Inklusive Warnung zum Datenbestand.
     ============================================================================== -->

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2 class="page-title">Updates</h2>
        <p class="page-subtitle">
          Vergleicht den installierten Stand mit dem Stand auf GitHub und spielt ihn auf Wunsch ein.
        </p>
      </div>
      <button class="btn btn-secondary btn-sm" :disabled="checking || isRunning" @click="check(true)">
        <AppIcon name="refresh" :size="16" :class="checking ? 'spin' : ''" />
        {{ checking ? 'Prüfe…' : 'Auf Updates prüfen' }}
      </button>
    </div>

    <p v-if="error" class="note note-fail">{{ error }}</p>

    <!-- ================================================================
         LAUFENDER VORGANG
         ================================================================ -->
    <div v-if="run && run.status === 'running'" class="card mb-4" style="border-color: var(--color-primary)">
      <div class="card-body">
        <div class="flex items-center gap-3 mb-3">
          <AppIcon name="refresh" :size="20" class="spin" style="color: var(--color-primary)" />
          <div class="min-w-0">
            <p class="font-semibold" style="color: var(--color-primary)">
              {{ run.action === 'rollback' ? 'Rückfall läuft' : 'Update läuft' }} – {{ run.step || 'Vorbereitung' }}
            </p>
            <p class="text-sm" style="color: var(--color-text-muted)">{{ run.message }}</p>
          </div>
        </div>
        <div class="bar-track">
          <div class="bar-fill" :style="{ width: (run.progress || 0) + '%', backgroundColor: 'var(--color-primary)' }" />
        </div>
        <p class="text-xs mt-2" style="color: var(--color-text-muted)">
          <template v-if="offline">
            Der Server ist gerade nicht erreichbar – das ist während des Neubaus normal.
            Diese Seite meldet sich von selbst zurück.
          </template>
          <template v-else>
            Bitte das Fenster offen lassen. Die Oberfläche ist gleich kurz nicht erreichbar.
          </template>
        </p>
      </div>
    </div>

    <!-- Ergebnis des letzten Laufs -->
    <div
      v-else-if="run && (run.status === 'success' || run.status === 'failed')"
      class="card mb-4"
      :style="{ borderColor: run.status === 'success' ? 'var(--color-success)' : 'var(--color-danger)' }"
    >
      <div class="card-body">
        <div class="flex items-start gap-3">
          <AppIcon
            :name="run.status === 'success' ? 'check' : 'warning'"
            :size="20"
            class="shrink-0"
            :style="{ color: run.status === 'success' ? 'var(--color-success)' : 'var(--color-danger)' }"
          />
          <div class="min-w-0 flex-1">
            <p class="font-semibold" :style="{ color: run.status === 'success' ? 'var(--color-success)' : 'var(--color-danger)' }">
              {{ run.status === 'success' ? 'Letzter Vorgang erfolgreich' : 'Letzter Vorgang fehlgeschlagen' }}
            </p>
            <p class="text-sm mt-1" style="color: var(--color-text-secondary)">{{ run.message }}</p>
            <p class="text-xs mt-1" style="color: var(--color-text-muted)">
              {{ run.action === 'rollback' ? 'Rückfall' : 'Update' }} vom {{ formatTime(run.updated_at) }}
              <template v-if="run.rolled_back"> · auf den vorherigen Stand zurückgesetzt</template>
              <template v-if="run.backup"> · Sicherung {{ run.backup }}</template>
            </p>
            <div class="flex flex-wrap gap-2 mt-3">
              <button class="btn btn-secondary btn-sm" @click="reloadPage">Seite neu laden</button>
              <button class="btn btn-ghost btn-sm" @click="toggleLog">
                {{ showLog ? 'Protokoll ausblenden' : 'Protokoll anzeigen' }}
              </button>
            </div>
          </div>
        </div>
        <pre v-if="showLog" class="log-box">{{ logText }}</pre>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <!-- ==============================================================
           STAND
           ============================================================== -->
      <div class="card lg:col-span-2">
        <div class="card-header">
          <span class="card-title">Versionsstand</span>
          <span v-if="status" class="badge" :class="status.update_available ? 'badge-warning' : 'badge-success'">
            {{ status.update_available ? 'Update verfügbar' : 'aktuell' }}
          </span>
        </div>
        <div class="card-body space-y-2 text-sm">
          <div class="info-row">
            <span>Installiert</span>
            <span class="font-mono">{{ status?.local?.version || '–' }}</span>
          </div>
          <div v-if="status?.local?.commit_short" class="info-row">
            <span>Stand (Commit)</span>
            <span class="font-mono">{{ status.local.commit_short }} · {{ formatTime(status.local.commit_date) }}</span>
          </div>
          <div class="info-row">
            <span>Verzeichnis auf dem Server</span>
            <span class="font-mono">{{ status?.local?.install_dir || '–' }}</span>
          </div>
          <div class="divider my-2" />
          <div class="info-row">
            <span>Auf GitHub</span>
            <span class="font-mono">
              {{ status?.remote?.version || status?.remote?.commit_short || '–' }}
            </span>
          </div>
          <div v-if="status?.remote?.commit_date" class="info-row">
            <span>Veröffentlicht</span>
            <span>{{ formatTime(status.remote.commit_date) }}</span>
          </div>
          <div v-if="status?.remote?.commit_message" class="info-row">
            <span>Letzte Änderung</span>
            <span class="truncate" :title="status.remote.commit_message">{{ status.remote.commit_message }}</span>
          </div>
          <div class="info-row">
            <span>Quelle</span>
            <span class="font-mono">{{ status?.remote?.repo }}@{{ status?.remote?.branch }}</span>
          </div>

          <p v-if="status?.reason" class="text-xs pt-1" style="color: var(--color-text-muted)">
            {{ status.reason }}
          </p>
          <p v-if="status?.local?.note" class="note note-warn">{{ status.local.note }}</p>
          <p v-if="status && !status.can_update" class="note note-warn">
            Dieser Server lässt sich nicht über die Oberfläche aktualisieren – dem Backend fehlt
            der Zugriff auf den Host. Nutze dafür den Befehl weiter unten.
          </p>

          <div class="pt-2">
            <button
              class="btn btn-primary"
              :disabled="!canStart"
              @click="askUpdate"
            >
              <AppIcon name="download" :size="16" />
              {{ status?.update_available ? 'Update einspielen' : 'Neu installieren (gleicher Stand)' }}
            </button>
          </div>
        </div>
      </div>

      <!-- ==============================================================
           SICHERUNGEN / RÜCKFALL
           ============================================================== -->
      <div class="card">
        <div class="card-header">
          <span class="card-title">Sicherungen</span>
          <span class="badge badge-neutral">{{ backups.length }}</span>
        </div>
        <div class="card-body space-y-3 text-sm">
          <p style="color: var(--color-text-muted)">
            Vor jedem Update wird der bisherige Stand gesichert. Der Rückfall spielt genau
            diese Sicherung wieder ein.
          </p>

          <div v-if="!backups.length" class="empty-state">
            <p class="empty-state-title">Noch keine Sicherung</p>
            <p class="text-sm" style="color: var(--color-text-muted)">
              Sie entsteht beim ersten Update über diese Seite.
            </p>
          </div>

          <div v-for="backup in backups" :key="backup.name" class="backup-row">
            <div class="min-w-0">
              <p class="font-mono text-sm">{{ backup.name }}</p>
              <p class="text-xs" style="color: var(--color-text-muted)">
                {{ backup.version || 'ohne Versionsangabe' }}
                <template v-if="backup.size"> · {{ backup.size }}</template>
                · {{ backup.database_dump ? 'mit Datenbank' : 'ohne Datenbank' }}
              </p>
            </div>
            <button
              class="btn btn-secondary btn-sm"
              :disabled="!canStart"
              @click="askRollback(backup)"
            >
              Zurück
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- ================================================================
         UPDATE PER KOMMANDOZEILE
         ================================================================ -->
    <div class="card mt-4">
      <div class="card-header"><span class="card-title">Update ohne Oberfläche</span></div>
      <div class="card-body">
        <p class="text-sm mb-2" style="color: var(--color-text-muted)">
          Derselbe Vorgang als Einzeiler – falls die Oberfläche nicht erreichbar ist:
        </p>
        <div class="flex items-center gap-2">
          <code class="oneliner">{{ status?.oneliner || '–' }}</code>
          <button class="btn btn-secondary btn-sm" :disabled="!status?.oneliner" @click="copyOneliner">
            {{ copied ? 'Kopiert' : 'Kopieren' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ================================================================
         RÜCKFRAGE VOR DEM EINGRIFF
         ================================================================ -->
    <div v-if="dialog" class="modal-backdrop" @click.self="dialog = null">
      <div class="modal max-w-lg">
        <div class="card-header">
          <span class="card-title">
            {{ dialog.mode === 'update' ? 'Update wirklich einspielen?' : 'Wirklich zurückfallen?' }}
          </span>
        </div>
        <div class="card-body space-y-3 text-sm overflow-y-auto">
          <div class="warn-box">
            <p class="font-semibold mb-1">Das kann Logdaten kosten.</p>
            <p>
              Normalerweise bleibt die Datenbank erhalten – sie liegt in einem eigenen
              Docker-Volume. Verlassen sollte man sich darauf nicht: ändert sich das
              Datenbankschema oder schlägt der Vorgang mitten im Lauf fehl, können Logs
              verloren gehen. <strong>Wer die Logs braucht, sichert sie vorher.</strong>
            </p>
          </div>

          <p v-if="dialog.mode === 'update'">
            Eingespielt wird der Stand
            <strong>{{ status?.remote?.version || status?.remote?.commit_short }}</strong>
            aus <span class="font-mono">{{ status?.remote?.repo }}@{{ status?.remote?.branch }}</span>.
            Alle Container werden neu gebaut und gestartet; die Oberfläche ist dabei einige
            Minuten nicht erreichbar.
          </p>
          <p v-else>
            Wiederhergestellt wird die Sicherung
            <strong class="font-mono">{{ dialog.backup?.name }}</strong>
            <template v-if="dialog.backup?.version"> (Version {{ dialog.backup.version }})</template>.
            <template v-if="dialog.backup?.database_dump">
              Der mitgesicherte Datenbankstand wird dabei eingespielt – <strong>alle Logs, die
              seit dieser Sicherung dazugekommen sind, gehen dabei verloren.</strong>
            </template>
            <template v-else>
              Diese Sicherung enthält keinen Datenbankabzug – die Datenbank bleibt, wie sie ist.
            </template>
          </p>

          <label v-if="dialog.mode === 'update'" class="flex items-start gap-2 cursor-pointer">
            <input v-model="databaseBackup" type="checkbox" class="mt-1">
            <span>
              Datenbank vorher sichern (empfohlen).
              <span class="block text-xs" style="color: var(--color-text-muted)">
                Bei vielen Logs dauert das eine Weile und braucht Platz auf der Platte.
                Ohne Haken geht es schneller, aber ohne Netz.
              </span>
            </span>
          </label>

          <label class="flex items-start gap-2 cursor-pointer">
            <input v-model="understood" type="checkbox" class="mt-1">
            <span>Ich habe verstanden, dass dabei Logdaten verloren gehen können.</span>
          </label>
        </div>
        <div class="modal-actions">
          <button class="btn btn-ghost" @click="dialog = null">Abbrechen</button>
          <button class="btn btn-danger" :disabled="!understood || starting" @click="confirmDialog">
            {{ starting ? 'Wird gestartet…' : (dialog.mode === 'update' ? 'Update starten' : 'Rückfall starten') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import AppIcon from '../components/AppIcon.vue'

const auth = useAuthStore()

const status = ref(null)
const checking = ref(false)
const starting = ref(false)
const error = ref('')
const offline = ref(false)
const dialog = ref(null)
const understood = ref(false)
const databaseBackup = ref(true)
const showLog = ref(false)
const logText = ref('')
const copied = ref(false)

let pollTimer = null
let pendingSince = 0

// Zwischen "Start abgeschickt" und dem ersten Lebenszeichen des Skripts vergehen
// ein paar Sekunden. Solange gilt der Lauf als laufend - sonst zeigt die Seite
// noch das Ergebnis des *vorherigen* Laufs und hört zu früh auf zu warten.
const pendingStart = ref(false)
const pendingAction = ref('apply')
const PENDING_GRACE_MS = 45000

const serverRun = computed(() => status.value?.run || null)
const backups = computed(() => status.value?.backups || [])
const isRunning = computed(() => serverRun.value?.status === 'running' || pendingStart.value)

/** Was angezeigt wird: der echte Zustand, ersatzweise der Startvermerk. */
const run = computed(() => {
  if (serverRun.value?.status === 'running') return serverRun.value
  if (pendingStart.value) {
    return {
      status: 'running',
      action: pendingAction.value,
      step: 'Start',
      message: 'Der Wartungslauf wird auf dem Server gestartet…',
      progress: 2,
    }
  }
  return serverRun.value
})

const canStart = computed(() => !!status.value?.can_update && !isRunning.value && !starting.value)

onMounted(() => {
  load()
})

onUnmounted(() => {
  stopPolling()
})

async function load(force = false) {
  try {
    status.value = await auth.api(`/api/updates/status${force ? '?force=true' : ''}`)
    offline.value = false
    error.value = ''
    if (isRunning.value) startPolling()
  } catch (e) {
    error.value = e.message || 'Der Update-Stand konnte nicht geladen werden.'
  }
}

async function check(force) {
  checking.value = true
  try {
    await load(force)
  } finally {
    checking.value = false
  }
}

function startPolling() {
  if (pollTimer) return
  pollTimer = setInterval(poll, 3000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

/** Während des Updates ist der Server zeitweise weg - das ist kein Fehler. */
async function poll() {
  try {
    status.value = await auth.api('/api/updates/status')
    offline.value = false

    // Das Skript hat sich gemeldet - der Startvermerk hat seinen Zweck erfüllt.
    if (serverRun.value?.status === 'running') {
      pendingStart.value = false
      return
    }

    // Kein "läuft" mehr, aber vielleicht schon ein Ergebnis dieses Laufs -
    // ein Vorlauf kann auch sofort scheitern (falsches Verzeichnis o. ä.).
    if (pendingStart.value) {
      const stamp = Date.parse(serverRun.value?.updated_at || '')
      const fresh = !Number.isNaN(stamp) && stamp >= pendingSince - 5000
      if (!fresh && Date.now() - pendingSince < PENDING_GRACE_MS) return
      pendingStart.value = false
      if (!fresh) {
        error.value = 'Der Wartungslauf hat sich nicht gemeldet. Bitte das Protokoll ansehen.'
      }
    }

    stopPolling()
    await loadLog()
  } catch {
    // Server gerade weg (Neubau läuft) - weiter warten.
    offline.value = true
  }
}

function askUpdate() {
  understood.value = false
  databaseBackup.value = true
  dialog.value = { mode: 'update' }
}

function askRollback(backup) {
  understood.value = false
  dialog.value = { mode: 'rollback', backup }
}

async function confirmDialog() {
  if (!dialog.value || !understood.value) return
  starting.value = true
  error.value = ''
  const mode = dialog.value.mode
  try {
    if (mode === 'update') {
      await auth.api('/api/updates/apply', {
        method: 'POST',
        body: { confirm: 'UPDATE', database_backup: databaseBackup.value },
      })
    } else {
      await auth.api('/api/updates/rollback', {
        method: 'POST',
        body: { confirm: 'ROLLBACK', backup: dialog.value.backup?.name || '' },
      })
    }
    dialog.value = null
    logText.value = ''
    showLog.value = false
    // Der Lauf braucht einen Moment, bis er den ersten Zustand schreibt.
    pendingAction.value = mode === 'update' ? 'apply' : 'rollback'
    pendingSince = Date.now()
    pendingStart.value = true
    startPolling()
  } catch (e) {
    error.value = e.message || 'Der Vorgang konnte nicht gestartet werden.'
    dialog.value = null
  } finally {
    starting.value = false
  }
}

async function loadLog() {
  try {
    const data = await auth.api('/api/updates/log?lines=300')
    logText.value = (data.lines || []).join('\n') || 'Kein Protokoll vorhanden.'
  } catch {
    logText.value = 'Das Protokoll konnte nicht gelesen werden.'
  }
}

async function toggleLog() {
  showLog.value = !showLog.value
  if (showLog.value && !logText.value) await loadLog()
}

function reloadPage() {
  window.location.reload()
}

async function copyOneliner() {
  if (!status.value?.oneliner) return
  try {
    await navigator.clipboard.writeText(status.value.oneliner)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch {
    error.value = 'Kopieren hat nicht geklappt – bitte von Hand markieren.'
  }
}

function formatTime(value) {
  if (!value) return '–'
  const date = new Date(value)
  return isNaN(date.getTime()) ? value : date.toLocaleString('de-DE')
}
</script>

<style scoped>
.info-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.info-row > span:first-child {
  color: var(--color-text-muted);
}

.info-row > span:last-child {
  color: var(--color-text-primary);
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 60%;
}

.bar-track {
  height: 0.5rem;
  border-radius: var(--radius-full);
  background-color: var(--hover-surface);
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: var(--radius-full);
  transition: width var(--duration) var(--ease);
}

.backup-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.5rem 0.625rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
}

.note {
  padding: 0.625rem 0.75rem;
  border-radius: var(--radius);
  font-size: 0.8125rem;
}

.note-fail {
  background-color: var(--danger-soft);
  color: var(--color-danger);
  margin-bottom: 1rem;
}

.note-warn {
  background-color: var(--warning-soft);
  color: var(--color-warning);
}

.warn-box {
  padding: 0.75rem;
  border-radius: var(--radius);
  background-color: var(--warning-soft);
  color: var(--color-warning);
  line-height: 1.5;
}

.oneliner {
  flex: 1;
  min-width: 0;
  padding: 0.5rem 0.625rem;
  border-radius: var(--radius);
  background-color: var(--color-surface-elevated);
  border: 1px solid var(--color-border);
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--color-text-primary);
  overflow-x: auto;
  white-space: nowrap;
}

.log-box {
  margin-top: 0.75rem;
  padding: 0.75rem;
  max-height: 20rem;
  overflow: auto;
  border-radius: var(--radius);
  background-color: var(--color-surface-elevated);
  border: 1px solid var(--color-border);
  font-family: var(--font-mono);
  font-size: 0.6875rem;
  line-height: 1.5;
  color: var(--color-text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  padding: 0.875rem 1.25rem;
  border-top: 1px solid var(--color-border);
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>

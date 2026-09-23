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

        <!-- Die Ausgabe des Wartungsskripts, live.

             Ein Fortschrittsbalken sagt „43 %". Er sagt nicht, woran es gerade
             hängt, und wenn etwas schiefgeht, sagt er gar nichts. Hier läuft
             stattdessen mit, was auf dem Server tatsächlich passiert — so, wie
             in einer Shell danebenzustehen. -->
        <div class="mt-4">
          <div class="flex items-center justify-between gap-2 mb-1">
            <span class="text-xs font-medium" style="color: var(--color-text-secondary)">
              Ausgabe vom Server
              <span v-if="liveConnected" class="badge badge-success ml-1">live</span>
              <span v-else class="badge badge-neutral ml-1">Verbindung unterbrochen</span>
            </span>
            <label class="flex items-center gap-1.5 text-xs cursor-pointer" style="color: var(--color-text-muted)">
              <input type="checkbox" v-model="followOutput">
              mitscrollen
            </label>
          </div>
          <pre ref="liveBox" class="log-box log-box--live">{{ liveLines.join('\n') || 'Warte auf die erste Ausgabe…' }}</pre>
        </div>
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
          <span v-if="status" class="badge" :class="stateBadge">
            {{ stateLabel }}
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

          <!-- Der Kanal zeigt auf einen aelteren Stand als den installierten.
               Meist fehlt einfach ein Release fuer den aktuellen Stand. Hier
               steht deshalb kein Update-Knopf, sondern was zu tun ist. -->
          <div v-if="status?.is_downgrade" class="downgrade-note">
            <p class="font-semibold mb-1">Einspielen wäre hier ein Rückschritt.</p>
            <p>
              Der eingestellte Kanal <strong>{{ channelLabel }}</strong> zeigt auf
              <span class="font-mono">{{ status?.remote?.version || status?.target_ref }}</span> —
              installiert ist aber schon
              <span class="font-mono">{{ status?.local?.version }}</span>.
            </p>
            <p class="mt-1">Zwei Wege:</p>
            <ul class="downgrade-list">
              <li>Auf GitHub ein Release für den aktuellen Stand anlegen — dann stimmt „Stabil“ wieder.</li>
              <li>Oder oben den Kanal auf <strong>Aktuell ({{ status?.remote?.branch }})</strong> stellen.</li>
            </ul>
          </div>
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
              {{ applyLabel }}
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
         WELCHER STAND? (Kanal und Release)
         ================================================================ -->
    <div class="card mt-4">
      <div class="card-header">
        <span class="card-title">Welchen Stand soll dieser Server fahren?</span>
      </div>
      <div class="card-body space-y-3">
        <p class="text-sm" style="color: var(--color-text-muted)">
          Nicht jeder will immer den letzten Commit. Hier steht, woran sich dieser
          Server hält — die Update-Prüfung oben richtet sich danach.
        </p>

        <div class="channel-grid">
          <label
            v-for="option in channels"
            :key="option.id"
            class="channel"
            :class="{ 'is-picked': channel.channel === option.id }"
          >
            <input v-model="channel.channel" type="radio" :value="option.id">
            <span>
              <strong>{{ option.label }}</strong>
              <em>{{ option.hint }}</em>
            </span>
          </label>
        </div>

        <!-- Nur bei "festgelegte Version": welche denn? -->
        <div v-if="channel.channel === 'pinned'">
          <label class="label">Release oder Tag</label>
          <select v-if="releases.length" v-model="channel.ref" class="select">
            <option value="">– bitte wählen –</option>
            <option v-for="release in releases" :key="release.tag" :value="release.tag">
              {{ release.name }}{{ release.prerelease ? ' (Vorabversion)' : '' }}
            </option>
          </select>
          <input v-else v-model="channel.ref" type="text" class="input"
                 placeholder="z.B. v2026.08.14 oder ein Commit">
          <p class="text-xs mt-1" style="color: var(--color-text-muted)">
            Der Server bleibt auf diesem Stand stehen, bis hier etwas anderes gewählt wird.
          </p>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <button class="btn btn-primary btn-sm" :disabled="channelSaving" @click="saveChannel">
            {{ channelSaving ? 'Wird gespeichert…' : 'Übernehmen' }}
          </button>
          <span v-if="status?.target_ref" class="text-xs" style="color: var(--color-text-muted)">
            Zielpunkt: <code class="font-mono">{{ status.target_ref }}</code>
          </span>
        </div>

        <!-- Sofortmeldung: wie der Server von einem Push erfährt -->
        <div v-if="status?.webhook" class="webhook-box">
          <p class="text-sm font-semibold" style="color: var(--color-text-primary)">
            Sofort erfahren, wenn etwas gepusht wird
          </p>
          <p class="text-xs mt-1" style="color: var(--color-text-muted)">
            Dieser Server sieht von selbst alle
            {{ status.watcher?.interval_seconds || 120 }} Sekunden nach und meldet einen
            neuen Stand sofort in jedes offene Fenster.
            <template v-if="!status.webhook.configured">
              Noch schneller geht es mit einem Webhook — {{ status.webhook.hint }}
            </template>
            <template v-else>
              Der GitHub-Webhook ist eingerichtet: <code class="font-mono">{{ status.webhook.url || status.webhook.path }}</code>
            </template>
          </p>
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
            {{ starting ? 'Wird gestartet…' : (dialog.mode === 'update' ? 'Weiter' : 'Weiter') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Letzter Schritt vor dem Eingriff: die Sicherungsfrage. Ohne beantwortete
         Frage weist der Server den Aufruf ab (backend app/guard.py). -->
    <BackupPrompt
      :open="promptOpen"
      :operation="promptOperation"
      :warning="promptWarning"
      :scopes="backupScopes"
      @confirm="startRun"
      @cancel="promptOpen = false"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import AppIcon from '../components/AppIcon.vue'
import BackupPrompt from '../components/BackupPrompt.vue'

const auth = useAuthStore()

// Release-Auswahl und Sicherungsfrage
const releases = ref([])
const channels = ref([])
const channel = ref({ channel: 'stable', ref: '', auto_offer: true })
const channelSaving = ref(false)
const backupScopes = ref([])
const promptOpen = ref(false)
const promptOperation = ref('')
const promptWarning = ref('')

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

// Mitlaufende Ausgabe des Wartungslaufs (Server-Sent Events).
const liveLines = ref([])
const liveConnected = ref(false)
const followOutput = ref(true)
const liveBox = ref(null)
let outputStream = null

// Wie viele Zeilen im Fenster stehen bleiben. Ein Neubau erzeugt schnell
// einige tausend - alle zu behalten macht den Browser langsam, ohne dass es
// jemandem hilft. Das vollstaendige Protokoll steht weiterhin unter
// „Protokoll anzeigen".
const MAX_LIVE_LINES = 2000

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

const canStart = computed(() => (
  !!status.value?.can_update && !isRunning.value && !starting.value
  // Bei einem Rueckschritt bleibt der Knopf aus: der Server weist das ohnehin
  // ab (HTTP 409), und ein Knopf, der nur eine Fehlermeldung erzeugt, hilft
  // niemandem.
  && !status.value?.is_downgrade
))

/** Drei Zustaende statt zwei: hinterher, gleichauf, oder voraus. */
const stateBadge = computed(() => {
  if (status.value?.is_downgrade) return 'badge-neutral'
  return status.value?.update_available ? 'badge-warning' : 'badge-success'
})

const stateLabel = computed(() => {
  if (status.value?.is_downgrade) return 'Server ist voraus'
  return status.value?.update_available ? 'Update verfügbar' : 'aktuell'
})

const applyLabel = computed(() => (
  status.value?.update_available ? 'Update einspielen' : 'Neu installieren (gleicher Stand)'
))

const channelLabel = computed(() => {
  const key = status.value?.channel?.channel
  return channels.value.find(c => c.id === key)?.label || key || '—'
})

onMounted(() => {
  load()
  loadReleases()
  loadBackupScopes()
})

onUnmounted(() => {
  stopPolling()
  stopOutputStream()
})

// Sobald ein Lauf beginnt, haengt sich die Seite an die Ausgabe - und loest
// sich wieder, wenn er durch ist. Ohne das liefe ein offener Kanal weiter,
// an dem niemand mehr haengt.
watch(isRunning, (running) => {
  if (running) startOutputStream()
  else stopOutputStream()
}, { immediate: true })

async function load(force = false) {
  try {
    status.value = await auth.api(`/api/updates/status${force ? '?force=true' : ''}`)
    offline.value = false
    error.value = ''
    if (isRunning.value) {
      startPolling()
      startOutputStream()
    }
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

/**
 * Der alte Dialog erklaert nur noch, was passiert. Losgeschickt wird erst nach
 * der Sicherungsfrage - die ist Pflicht und wird auch serverseitig verlangt.
 */
function confirmDialog() {
  if (!dialog.value || !understood.value) return
  const mode = dialog.value.mode
  promptOperation.value = mode === 'update'
    ? `Update auf ${status.value?.remote?.version || status.value?.remote?.commit_short || 'den neuen Stand'}`
    : `Rückfall auf ${dialog.value.backup?.name || 'die letzte Sicherung'}`
  promptWarning.value = mode === 'rollback' && dialog.value.backup?.database_dump
    ? 'Der mitgesicherte Datenbankstand wird eingespielt — alle Logs seit dieser Sicherung gehen verloren.'
    : ''
  promptOpen.value = true
}

/** Startet den Lauf, sobald die Sicherungsfrage beantwortet ist. */
async function startRun(decision) {
  promptOpen.value = false
  if (!dialog.value) return

  starting.value = true
  error.value = ''
  const mode = dialog.value.mode
  try {
    if (mode === 'update') {
      await auth.api('/api/updates/apply', {
        method: 'POST',
        body: {
          confirm: 'UPDATE',
          database_backup: databaseBackup.value,
          ref: status.value?.target_ref || '',
          backup: decision,
        },
      })
    } else {
      await auth.api('/api/updates/rollback', {
        method: 'POST',
        body: {
          confirm: 'ROLLBACK',
          // Die Sicherung des Wartungsskripts auf dem Host - nicht zu
          // verwechseln mit der ZIP-Sicherung aus der Rueckfrage oben.
          backup_dir: dialog.value.backup?.name || '',
          backup: decision,
        },
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

// =============================================================================
// Release-Auswahl
// =============================================================================
async function loadReleases() {
  try {
    const data = await auth.api('/api/updates/releases')
    releases.value = data.releases || []
    channels.value = data.channels || []
    if (data.current_channel) channel.value = { ...data.current_channel }
  } catch (e) {
    // Ohne GitHub-Antwort bleibt die Liste leer - der Kanal laesst sich
    // trotzdem umstellen, nur ohne Auswahlhilfe.
    releases.value = []
  }
}

async function saveChannel() {
  channelSaving.value = true
  error.value = ''
  try {
    const data = await auth.api('/api/updates/channel', {
      method: 'PUT',
      body: {
        channel: channel.value.channel,
        ref: channel.value.ref || '',
        auto_offer: channel.value.auto_offer !== false,
      },
    })
    status.value = data.status
  } catch (e) {
    error.value = e.message
  } finally {
    channelSaving.value = false
  }
}

async function loadBackupScopes() {
  try {
    const data = await auth.api('/api/backup/overview')
    backupScopes.value = data.scopes
  } catch {
    backupScopes.value = []
  }
}

/**
 * Haengt sich an die laufende Ausgabe.
 *
 * Bewusst ein eigener Strom statt des allgemeinen Ereigniskanals: hier kommen
 * je nach Lauf hunderte Zeilen pro Sekunde, und die haben in dem Kanal, ueber
 * den sonst nur Hinweise laufen, nichts verloren.
 */
function startOutputStream() {
  if (outputStream || typeof EventSource === 'undefined') return
  outputStream = new EventSource(
    `/api/updates/log/stream?token=${encodeURIComponent(auth.token)}`)

  outputStream.addEventListener('update.output', (event) => {
    liveConnected.value = true
    try {
      const data = JSON.parse(event.data)
      if (data.initial) liveLines.value = []
      liveLines.value = [...liveLines.value, ...(data.lines || [])].slice(-MAX_LIVE_LINES)
      scrollToEnd()
    } catch {
      // Eine unlesbare Zeile ist kein Grund, den Strom aufzugeben.
    }
  })

  outputStream.addEventListener('update.state', (event) => {
    try {
      const state = JSON.parse(event.data)
      if (status.value) status.value.run = state
    } catch {
      // Zustand kommt beim naechsten Takt ohnehin wieder.
    }
  })

  outputStream.addEventListener('update.done', () => {
    liveConnected.value = false
    stopOutputStream()
    load()
  })

  outputStream.onopen = () => { liveConnected.value = true }
  // Bricht die Verbindung ab (der Container wird gerade neu gebaut - genau
  // das ist ja der Vorgang), versucht der Browser es von selbst erneut.
  outputStream.onerror = () => { liveConnected.value = false }
}

function stopOutputStream() {
  outputStream?.close()
  outputStream = null
}

function scrollToEnd() {
  if (!followOutput.value) return
  nextTick(() => {
    const box = liveBox.value
    if (box) box.scrollTop = box.scrollHeight
  })
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
.downgrade-note {
  margin-top: 0.625rem;
  padding: 0.625rem 0.75rem;
  border-radius: var(--radius);
  border: 1px solid var(--color-warning);
  background-color: var(--primary-soft);
  color: var(--color-text-secondary);
  font-size: 0.75rem;
}

.downgrade-list {
  margin-top: 0.25rem;
  padding-left: 1.125rem;
  list-style: disc;
}

.channel-grid {
  display: grid;
  gap: 0.5rem;
}

@media (min-width: 768px) {
  .channel-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

.channel {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.625rem 0.75rem;
  border-radius: var(--radius);
  border: 1px solid var(--color-border);
  cursor: pointer;
  font-size: 0.8125rem;
}

.channel:hover {
  background-color: var(--hover-surface);
}

.channel.is-picked {
  border-color: var(--color-primary);
  background-color: var(--primary-soft);
}

.channel input {
  margin-top: 0.1875rem;
  flex-shrink: 0;
}

.channel span {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
  min-width: 0;
}

.channel strong {
  color: var(--color-text-primary);
  font-weight: 600;
}

.channel em {
  font-style: normal;
  font-size: 0.6875rem;
  color: var(--color-text-muted);
}

.webhook-box {
  padding: 0.625rem 0.75rem;
  border-radius: var(--radius);
  background-color: var(--color-surface-elevated);
  border: 1px solid var(--color-border);
}

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

/* Die mitlaufende Ausgabe darf hoeher sein und sieht aus wie eine Konsole -
   sie ist ja eine. Dunkler Hintergrund auch im hellen Design: eine
   Terminalausgabe liest sich so besser, und man verwechselt sie nicht mit dem
   Rest der Seite. */
.log-box--live {
  max-height: 26rem;
  margin-top: 0;
  background-color: #0b1220;
  border-color: #1e293b;
  color: #cbd5e1;
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

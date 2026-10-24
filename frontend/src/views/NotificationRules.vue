<!-- ==============================================================================
     Name:        Phydran6
     Kontakt:     Phydran6
     Changelog:   ../../../CHANGELOG/frontend.md
     Beschreibung: LogBot - Meldungen: Regeln (was löst aus, wohin geht es).
     ============================================================================== -->
<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2 class="page-title">Regeln</h2>
        <p class="page-subtitle">
          Wann LogBot meldet – und wohin. Gleichartige Ereignisse werden in der Ruhezeit
          zusammengefasst („… und 37 weitere“), damit niemand mit Meldungen geflutet wird.
        </p>
      </div>
      <div class="flex gap-2">
        <button class="btn btn-secondary btn-sm" :disabled="testing" @click="sendTest">
          <AppIcon name="send" :size="16" /> Testmeldung
        </button>
        <button class="btn btn-primary btn-sm" :disabled="saving" @click="save">
          {{ saving ? 'Wird gespeichert…' : 'Speichern' }}
        </button>
      </div>
    </div>

    <p v-if="message" class="text-sm mb-3" :style="{ color: messageError ? 'var(--color-danger)' : 'var(--color-success)' }">{{ message }}</p>

    <!-- Kanäle auf einen Blick -->
    <div v-if="channels" class="grid grid-cols-1 md:grid-cols-3 gap-3 mb-5">
      <router-link to="/notifications/mail" class="card card-hover channel">
        <AppIcon name="mail" :size="20" />
        <div>
          <p class="font-semibold">E-Mail</p>
          <p class="text-xs" :style="{ color: channels.mail.ready ? 'var(--color-success)' : 'var(--color-warning)' }">
            {{ channels.mail.ready ? `bereit · ${channels.mail.recipients.length} Empfänger` : 'nicht eingerichtet' }}
          </p>
        </div>
      </router-link>
      <router-link to="/notifications/telegram" class="card card-hover channel">
        <AppIcon name="send" :size="20" />
        <div>
          <p class="font-semibold">Telegram</p>
          <p class="text-xs" :style="{ color: channels.telegram.ready ? 'var(--color-success)' : 'var(--color-warning)' }">
            {{ channels.telegram.ready ? `@${channels.telegram.bot_username} · ${channels.telegram.chats} Chat(s)` : 'nicht eingerichtet' }}
          </p>
        </div>
      </router-link>
      <router-link to="/notifications/app" class="card card-hover channel">
        <AppIcon name="mobile" :size="20" />
        <div>
          <p class="font-semibold">App & Push</p>
          <p class="text-xs" style="color: var(--color-success)">
            Eingang immer · {{ channels.app.devices }} Gerät(e) mit Push
          </p>
        </div>
      </router-link>
    </div>

    <!-- Regeln -->
    <div class="space-y-3">
      <div v-for="(rule, index) in rules" :key="rule.id" class="card">
        <div class="card-header">
          <label class="flex items-center gap-2 min-w-0 flex-1">
            <input v-model="rule.enabled" type="checkbox">
            <input v-model="rule.name" class="input rule-name" aria-label="Name der Regel">
          </label>
          <span class="badge badge-neutral">{{ TYPE_LABELS[rule.type] }}</span>
          <button class="btn btn-ghost btn-sm" title="Regel entfernen" @click="rules.splice(index, 1)">
            <AppIcon name="trash" :size="16" />
          </button>
        </div>
        <div class="card-body grid grid-cols-1 md:grid-cols-2 gap-4">
          <div v-if="rule.type !== 'offline'">
            <label class="label">{{ rule.type === 'log' ? 'Ab Schweregrad' : 'Ab Stufe im Systemtagebuch' }}</label>
            <select v-model="rule.min_severity" class="select w-full">
              <option value="critical">kritisch (emergency, alert, critical)</option>
              <option value="error">Fehler und dringender</option>
              <option value="warning">Warnung und dringender</option>
            </select>
          </div>
          <div v-if="rule.type !== 'system'">
            <label class="label">Geräte</label>
            <input :value="(rule.hosts || []).join(', ')" class="input w-full" placeholder="leer = alle · z.B. docker01, web*"
                   @change="rule.hosts = split($event.target.value)">
            <p class="hint">„docker01“ trifft die VM und ihre Container. Stern am Ende = beginnt mit.</p>
          </div>
          <div v-if="rule.type === 'log'">
            <label class="label">Nur wenn der Text enthält</label>
            <input :value="(rule.keywords || []).join(', ')" class="input w-full" placeholder="leer = egal"
                   @change="rule.keywords = split($event.target.value)">
          </div>
          <div v-if="rule.type === 'log'">
            <label class="label">Nicht, wenn der Text enthält</label>
            <input :value="(rule.exclude || []).join(', ')" class="input w-full" placeholder="z.B. healthcheck"
                   @change="rule.exclude = split($event.target.value)">
          </div>
          <div v-if="rule.type === 'log'" class="flex items-center gap-2">
            <input :id="`c-${rule.id}`" v-model="rule.include_containers" type="checkbox">
            <label :for="`c-${rule.id}`" class="text-sm">Auch Container-Logs</label>
          </div>
          <div v-if="rule.type === 'system'">
            <label class="label">Nur diese Bereiche</label>
            <div class="flex flex-wrap gap-2">
              <label v-for="cat in categories" :key="cat.key" class="chip">
                <input type="checkbox" :checked="(rule.categories || []).includes(cat.key)"
                       @change="toggleIn(rule, 'categories', cat.key)"> {{ cat.label }}
              </label>
            </div>
            <p class="hint">Nichts angehakt = alle Bereiche.</p>
          </div>
          <div>
            <label class="label">Senden an</label>
            <div class="flex flex-wrap gap-3">
              <label v-for="ch in CHANNELS" :key="ch.id" class="flex items-center gap-1 text-sm">
                <input type="checkbox" :checked="rule.channels.includes(ch.id)" @change="toggleIn(rule, 'channels', ch.id)">
                {{ ch.label }}
              </label>
            </div>
            <p class="hint">Im Eingang (Web und App) steht jede Meldung ohnehin.</p>
          </div>
          <div>
            <label class="label">Ruhezeit (Minuten)</label>
            <input v-model.number="rule.cooldown_minutes" type="number" min="0" max="1440" class="input w-32">
            <p class="hint">So lange meldet diese Regel pro Gerät höchstens einmal.</p>
          </div>
        </div>
      </div>
    </div>

    <div class="flex flex-wrap gap-2 mt-4">
      <button class="btn btn-secondary btn-sm" @click="add('log')"><AppIcon name="plus" :size="16" /> Regel für Logzeilen</button>
      <button class="btn btn-secondary btn-sm" @click="add('system')"><AppIcon name="plus" :size="16" /> Regel für LogBot selbst</button>
      <button class="btn btn-secondary btn-sm" @click="add('offline')"><AppIcon name="plus" :size="16" /> Regel für stumme Geräte</button>
    </div>

    <!-- Mail-Empfänger -->
    <div class="card mt-6">
      <div class="card-header"><span class="card-title">Wer bekommt Mails?</span></div>
      <div class="card-body space-y-3">
        <label class="flex items-center gap-2 text-sm">
          <input v-model="mailAdmins" type="checkbox">
          Alle Administratoren mit bestätigter E-Mail-Adresse
        </label>
        <p v-if="channels?.mail.admins_without_verified_mail?.length" class="hint" style="color: var(--color-warning)">
          Ohne bestätigte Adresse (bekommen keine Mails): {{ channels.mail.admins_without_verified_mail.join(', ') }}
        </p>
        <div>
          <label class="label">Zusätzliche Empfänger</label>
          <input v-model="mailExtra" class="input w-full" placeholder="it@firma.de, bereitschaft@firma.de">
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
const rules = ref([])
const channels = ref(null)
const categories = ref([])
const mailAdmins = ref(true)
const mailExtra = ref('')
const saving = ref(false)
const testing = ref(false)
const message = ref('')
const messageError = ref(false)

const TYPE_LABELS = { log: 'Logzeilen', system: 'LogBot selbst', offline: 'Geräte stumm' }
const CHANNELS = [
  { id: 'telegram', label: 'Telegram' },
  { id: 'mail', label: 'E-Mail' },
  { id: 'app', label: 'Push aufs Handy' },
]

const split = (value) => value.split(/[,\n]/).map(v => v.trim()).filter(Boolean)

function toggleIn(rule, key, value) {
  const list = rule[key] || []
  rule[key] = list.includes(value) ? list.filter(v => v !== value) : [...list, value]
}

function add(type) {
  rules.value.push({
    id: `rule-${Math.random().toString(16).slice(2, 10)}`,
    name: { log: 'Neue Log-Regel', system: 'LogBot: Fehler', offline: 'Gerät stumm' }[type],
    enabled: true, type, min_severity: type === 'log' ? 'critical' : 'error',
    hosts: [], keywords: [], exclude: [], categories: [], include_containers: true,
    channels: ['app'], cooldown_minutes: 15,
  })
}

function apply(data) {
  rules.value = data.config.rules
  mailAdmins.value = data.config.mail_admins
  mailExtra.value = (data.config.mail_extra || []).join(', ')
  channels.value = data.channels
  categories.value = data.categories
}

async function load() {
  try {
    apply(await auth.api('/api/notifications/config'))
  } catch (e) {
    message.value = e.message
    messageError.value = true
  }
}

async function save() {
  saving.value = true
  message.value = ''
  try {
    apply(await auth.api('/api/notifications/rules', {
      method: 'PUT',
      body: { rules: rules.value, mail_admins: mailAdmins.value, mail_extra: split(mailExtra.value) },
    }))
    message.value = 'Gespeichert.'
    messageError.value = false
  } catch (e) {
    message.value = e.message
    messageError.value = true
  } finally {
    saving.value = false
  }
}

async function sendTest() {
  testing.value = true
  message.value = ''
  try {
    const result = await auth.api('/api/notifications/test', { method: 'POST', body: { channels: ['app', 'mail', 'telegram'] } })
    const parts = Object.entries(result.delivery || {}).map(([k, v]) =>
      `${({ mail: 'E-Mail', telegram: 'Telegram', app: 'App' })[k]}: ${v.ok ? 'ok' : (v.skipped || v.error || 'Fehler')}`)
    message.value = `Testmeldung ausgelöst – ${parts.join(' · ')}`
    messageError.value = false
  } catch (e) {
    message.value = e.message
    messageError.value = true
  } finally {
    testing.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.channel {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem;
  color: var(--color-text-primary);
}

.rule-name {
  font-weight: 600;
  max-width: 24rem;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.125rem 0.5rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  font-size: 0.75rem;
}
</style>

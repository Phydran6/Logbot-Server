<!-- ==============================================================================
     Name:        Phydran6
     Kontakt:     Phydran6
     Changelog:   ../../../CHANGELOG/frontend.md
     Beschreibung: LogBot - Meldungen → Kanäle → E-Mail: der Mail-Assistent.

     Drei Wege, so einfach es geht:
       * Google - App-Passwort (zwei Felder) oder "Mit Google anmelden".
       * Microsoft 365 - der Assistent legt die App-Registrierung selbst an:
         einmal mit einem Admin-Konto anmelden, dann mit dem Postfach.
         Outlook.com geht genauso (Anmeldung mit dem privaten Konto).
       * Jeder andere Anbieter - Vorlagen für GMX, WEB.DE, IONOS, Strato …
     Kennwörter und Anmeldungen liegen verschlüsselt auf dem Server und kommen
     nie zurück in den Browser.
     ============================================================================== -->
<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2 class="page-title">E-Mail</h2>
        <p class="page-subtitle">
          Über diesen Weg verschickt LogBot Meldungen, Bestätigungscodes, Passwort-Links und
          Anmelde-Links für die App.
        </p>
      </div>
    </div>

    <p v-if="banner" class="card card-body mb-4 text-sm" :style="{ color: bannerError ? 'var(--color-danger)' : 'var(--color-success)' }">
      {{ banner }}
    </p>

    <!-- Stand -->
    <div v-if="config" class="card mb-4">
      <div class="card-body flex flex-wrap items-center gap-4">
        <span class="badge" :class="config.ready ? 'badge-success' : 'badge-warning'">
          {{ config.ready ? 'eingerichtet' : 'noch nicht eingerichtet' }}
        </span>
        <div class="flex-1 min-w-0 text-sm">
          <p><b>{{ modeLabel }}</b><span v-if="config.from_address"> · Absender {{ config.from_address }}</span></p>
          <p v-if="config.oauth?.refresh_token_readable === false" style="color: var(--color-danger)">
            Die Anmeldung ist auf diesem Server nicht mehr lesbar (anderer Server / neues JWT_SECRET) – bitte neu anmelden.
          </p>
        </div>
        <div class="flex gap-2 items-center">
          <input v-model="testRecipient" class="input" placeholder="Empfänger der Probemail" style="width: 16rem">
          <button class="btn btn-secondary btn-sm" :disabled="busy || !config.ready" @click="sendTest">Probemail</button>
          <button v-if="['google', 'microsoft'].includes(config.mode)" class="btn btn-ghost btn-sm" @click="disconnect">Abmelden</button>
        </div>
      </div>
    </div>

    <!-- Öffentliche Adresse -->
    <div class="card mb-6">
      <div class="card-header"><span class="card-title">Adresse dieses Servers in Mails</span></div>
      <div class="card-body">
        <div class="flex gap-2 flex-wrap">
          <input v-model="publicUrl" class="input flex-1" placeholder="https://logbot.firma.de" style="min-width: 16rem">
          <button class="btn btn-secondary btn-sm" @click="savePublicUrl">Übernehmen</button>
        </div>
        <p class="hint">
          Links in Mails (Passwort zurücksetzen, App-Anmeldung, Meldungen) zeigen hierhin. Bewusst fest
          eingestellt und nicht aus der Anfrage gelesen – sonst könnte ein Angreifer Links auf seine
          eigene Seite in echte Mails schmuggeln.
        </p>
      </div>
    </div>

    <!-- Schritt 1: Weg wählen -->
    <h3 class="section-title">Weg wählen</h3>
    <div class="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3 mb-6">
      <button v-for="option in OPTIONS" :key="option.id" class="card card-hover tile"
              :class="{ 'is-picked': choice === option.id }" @click="pick(option.id)">
        <span class="tile-title">{{ option.label }}</span>
        <span class="tile-hint">{{ option.hint }}</span>
      </button>
    </div>

    <!-- ============================== Google ============================== -->
    <div v-if="choice === 'google'" class="card">
      <div class="card-body space-y-5">
        <div class="flex gap-2">
          <button class="btn btn-sm" :class="googleWay === 'apppass' ? 'btn-primary' : 'btn-secondary'" @click="googleWay = 'apppass'">App-Passwort (einfach)</button>
          <button class="btn btn-sm" :class="googleWay === 'oauth' ? 'btn-primary' : 'btn-secondary'" @click="googleWay = 'oauth'">Mit Google anmelden</button>
        </div>

        <div v-if="googleWay === 'apppass'" class="space-y-3 max-w-xl">
          <ol class="steps">
            <li>Im Google-Konto die <b>Bestätigung in zwei Schritten</b> einschalten (falls noch nicht).</li>
            <li><a href="https://myaccount.google.com/apppasswords" target="_blank" rel="noopener" class="link">App-Passwort erstellen</a> – Name z.B. „LogBot“ – und die 16 Zeichen hier einfügen.</li>
          </ol>
          <label class="label">Gmail-Adresse<input v-model="form.email" class="input w-full" placeholder="name@gmail.com"></label>
          <label class="label">App-Passwort<input v-model="form.password" type="password" class="input w-full" autocomplete="new-password"></label>
          <button class="btn btn-primary" :disabled="busy" @click="saveSmtp('gmail')">Speichern</button>
        </div>

        <div v-else class="space-y-3 max-w-2xl">
          <ol class="steps">
            <li>In der <a href="https://console.cloud.google.com/projectcreate" target="_blank" rel="noopener" class="link">Google Cloud Console</a> ein Projekt anlegen.</li>
            <li><a href="https://console.cloud.google.com/apis/library/gmail.googleapis.com" target="_blank" rel="noopener" class="link">Gmail-API aktivieren</a>.</li>
            <li><a href="https://console.cloud.google.com/apis/credentials/consent" target="_blank" rel="noopener" class="link">OAuth-Zustimmungsbildschirm</a>: „Extern“, eigene Adresse eintragen, danach <b>„App veröffentlichen“</b> (sonst läuft die Anmeldung nach 7 Tagen ab; der Hinweis „nicht verifiziert“ ist für eigene Apps normal).</li>
            <li v-if="callbackUrl"><a href="https://console.cloud.google.com/apis/credentials/oauthclient" target="_blank" rel="noopener" class="link">OAuth-Client-ID anlegen</a>, Typ <b>„Webanwendung“</b>, unter „Autorisierte Weiterleitungs-URIs“ diese Adresse eintragen:
              <code class="copyable" @click="copy(callbackUrl)">{{ callbackUrl }}</code>
              Client-ID und Clientschlüssel hier einfügen. Nach der Anmeldung kommt der Browser von selbst zurück.</li>
            <li v-else><a href="https://console.cloud.google.com/apis/credentials/oauthclient" target="_blank" rel="noopener" class="link">OAuth-Client-ID anlegen</a>, Typ <b>„Desktop-App“</b>. Client-ID und Clientschlüssel hier einfügen.
              (Ohne öffentliche HTTPS-Adresse oben muss die Adresse nach der Anmeldung einmal zurückkopiert werden.)</li>
          </ol>
          <label class="label">Client-ID<input v-model="form.clientId" class="input w-full" placeholder="….apps.googleusercontent.com"></label>
          <label class="label">Clientschlüssel<input v-model="form.clientSecret" type="password" class="input w-full"></label>
          <button class="btn btn-primary" :disabled="busy || !form.clientId" @click="startGoogle">Mit Google anmelden</button>
          <PasteStep v-if="flow && flow.kind === 'authorize'" :flow="flow" :busy="busy" @submit="completePaste" />
        </div>
      </div>
    </div>

    <!-- ========================= Microsoft 365 / Outlook ========================= -->
    <div v-if="choice === 'm365' || choice === 'outlook'" class="card">
      <div class="card-body space-y-6">
        <!-- Schritt A: App-Registrierung -->
        <section>
          <h4 class="step-title"><span class="step-no">1</span> App-Registrierung</h4>
          <div v-if="msApp.app_id && !changeApp" class="text-sm space-y-1">
            <p style="color: var(--color-success)">✓ „{{ msApp.display_name }}“ im Mandanten „{{ msApp.tenant_name }}“</p>
            <p class="hint">Anwendungs-ID {{ msApp.app_id }} · angelegt von {{ msApp.registered_by }}
              <span v-if="!msApp.consent_granted"> · Zustimmung erfolgt beim Anmelden des Postfachs</span></p>
            <button class="btn btn-ghost btn-sm" @click="changeApp = true">Andere App verwenden</button>
          </div>
          <div v-else class="space-y-3">
            <p class="text-sm" style="color: var(--color-text-secondary)">
              Damit LogBot über Microsoft Mails senden darf, braucht es eine App-Registrierung. Der
              Assistent legt sie selbst an: einmal mit einem Konto anmelden, das das darf
              (Globaler Administrator, Anwendungs- oder Cloudanwendungsadministrator).
              <span v-if="choice === 'outlook'">Für Outlook.com reicht dafür ein beliebiger Microsoft-365-/Entra-Mandant –
                die App wird für private Konten freigegeben.</span>
            </p>
            <button class="btn btn-primary" :disabled="busy" @click="startRegister('device')">Mit Microsoft anmelden und App anlegen</button>
            <DeviceStep v-if="flow && flow.kind === 'device' && flow.purpose === 'register'" :flow="flow" />
            <PasteStep v-if="flow && flow.kind === 'register_authorize'" :flow="flow" :busy="busy" @submit="completePaste" />
            <details class="text-sm">
              <summary class="link">Anmeldung per Code ist bei euch gesperrt?</summary>
              <p class="hint mt-1">Manche Mandanten sperren die Code-Anmeldung per bedingtem Zugriff. Dann geht es auch über
                den Browser – Microsofts Werkzeug springt danach aber auf <code>{{ msLoopback }}</code>, die Adresse muss
                einmal zurückkopiert werden.</p>
              <button class="btn btn-ghost btn-sm mt-1" :disabled="busy" @click="startRegister('browser')">Über den Browser anlegen</button>
            </details>
            <ul v-if="registerReport" class="steps-report">
              <li v-for="line in registerReport" :key="line">{{ line }}</li>
            </ul>
            <details class="text-sm">
              <summary class="link">Vorhandene App-Registrierung eintragen</summary>
              <div class="grid md:grid-cols-2 gap-3 mt-2">
                <label class="label">Anwendungs-ID (Client-ID)<input v-model="form.msClientId" class="input w-full"></label>
                <label v-if="choice === 'm365'" class="label">Verzeichnis-ID (Mandant)<input v-model="form.msTenant" class="input w-full" placeholder="GUID oder firma.onmicrosoft.com"></label>
              </div>
              <p class="hint">Plattform „Mobile und Desktopanwendungen“ mit Umleitungs-URI <code>{{ msLoopback }}</code>,
                „Öffentliche Clientflows zulassen“ = Ja, delegierte Berechtigung Microsoft Graph „Mail.Send“.</p>
            </details>
          </div>
        </section>

        <!-- Schritt B: Postfach -->
        <section>
          <h4 class="step-title"><span class="step-no">2</span> Mit dem Postfach anmelden</h4>
          <p class="text-sm mb-3" style="color: var(--color-text-secondary)">
            Mit dem Konto anmelden, <b>von dem</b> die Mails kommen sollen (z.B. logbot@firma.de –
            braucht ein Postfach bzw. eine Exchange-Lizenz).
          </p>
          <div class="flex flex-wrap gap-2 items-center">
            <button v-if="msDirect" class="btn btn-primary" :disabled="busy || !(msApp.app_id || form.msClientId)" @click="startMailbox('browser')">Mit Microsoft anmelden</button>
            <button class="btn" :class="msDirect ? 'btn-ghost btn-sm' : 'btn-primary'" :disabled="busy || !(msApp.app_id || form.msClientId)" @click="startMailbox('device')">{{ msDirect ? 'Lieber per Code anmelden' : 'Mit Microsoft anmelden' }}</button>
            <button v-if="!msDirect" class="btn btn-ghost btn-sm" :disabled="busy || !(msApp.app_id || form.msClientId)" @click="startMailbox('browser')">Über den Browser (Adresse zurückkopieren)</button>
          </div>
          <p v-if="!msDirect && msApp.app_id && !changeApp" class="hint mt-2">Direkt zurück zu LogBot geht es, wenn die App mit LogBots
            öffentlicher HTTPS-Adresse angelegt wurde – dafür oben „Andere App verwenden“ und neu anlegen lassen.</p>
          <DeviceStep v-if="flow && flow.kind === 'device' && flow.purpose === 'mailbox'" :flow="flow" />
          <PasteStep v-if="flow && flow.kind === 'authorize'" :flow="flow" :busy="busy" @submit="completePaste" />
        </section>
      </div>
    </div>

    <!-- ============================== SMTP ============================== -->
    <div v-if="choice === 'smtp'" class="card">
      <div class="card-body space-y-3 max-w-2xl">
        <label class="label">Anbieter
          <select v-model="form.preset" class="select w-full" @change="applyPreset">
            <option v-for="p in presets" :key="p.id" :value="p.id">{{ p.label }}</option>
          </select>
        </label>
        <p v-if="presetHint" class="hint">{{ presetHint }}</p>
        <div class="grid md:grid-cols-3 gap-3">
          <label class="label md:col-span-2">Server<input v-model="form.host" class="input w-full"></label>
          <label class="label">Port<input v-model.number="form.port" type="number" class="input w-full"></label>
        </div>
        <label class="label">Verschlüsselung
          <select v-model="form.encryption" class="select w-full">
            <option value="starttls">STARTTLS (Port 587)</option>
            <option value="tls">TLS (Port 465)</option>
            <option value="none">keine (nur im eigenen Netz)</option>
          </select>
        </label>
        <div class="grid md:grid-cols-2 gap-3">
          <label class="label">Benutzer<input v-model="form.email" class="input w-full" autocomplete="off"></label>
          <label class="label">Passwort<input v-model="form.password" type="password" class="input w-full" autocomplete="new-password"
                 :placeholder="config?.smtp_password_set ? '•••••• (unverändert)' : ''"></label>
        </div>
        <label class="label">Absenderadresse<input v-model="form.from" class="input w-full" placeholder="logbot@firma.de"></label>
        <label class="flex items-center gap-2 text-sm"><input v-model="form.verify" type="checkbox"> Zertifikat prüfen</label>
        <button class="btn btn-primary" :disabled="busy" @click="saveSmtp(form.preset)">Speichern</button>
      </div>
    </div>

    <!-- ============================== Postfix ============================== -->
    <div v-if="choice === 'container'" class="card">
      <div class="card-body space-y-3 max-w-2xl">
        <p class="text-sm" style="color: var(--color-text-secondary)">
          LogBots eigener Mailserver (Zusatzdienst „postfix“ unter System → Container → Zusatzdienste).
          Die meisten Anschlüsse dürfen nicht selbst zustellen – dann über einen Smarthost.
        </p>
        <label class="label">Absenderadresse<input v-model="form.from" class="input w-full"></label>
        <label class="label">Hostname des Mailservers<input v-model="form.myhostname" class="input w-full" placeholder="logbot.firma.de"></label>
        <div class="grid md:grid-cols-3 gap-3">
          <label class="label md:col-span-2">Smarthost (optional)<input v-model="form.relayHost" class="input w-full"></label>
          <label class="label">Port<input v-model.number="form.relayPort" type="number" class="input w-full"></label>
        </div>
        <div class="grid md:grid-cols-2 gap-3">
          <label class="label">Smarthost-Benutzer<input v-model="form.relayUser" class="input w-full"></label>
          <label class="label">Smarthost-Passwort<input v-model="form.relayPassword" type="password" class="input w-full"></label>
        </div>
        <button class="btn btn-primary" :disabled="busy" @click="saveContainer">Speichern</button>
      </div>
    </div>

    <div v-if="choice === 'off'" class="card">
      <div class="card-body">
        <p class="text-sm mb-3">Ohne Mailversand gibt es keine Passwort-Links, keine Bestätigungscodes und keine Meldungen per Mail.</p>
        <button class="btn btn-danger btn-sm" :disabled="busy" @click="turnOff">Mailversand ausschalten</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const OPTIONS = [
  { id: 'google', label: 'Google', hint: 'Gmail und Workspace' },
  { id: 'm365', label: 'Microsoft 365', hint: 'Exchange Online, App wird angelegt' },
  { id: 'outlook', label: 'Outlook.com', hint: 'private Microsoft-Konten' },
  { id: 'smtp', label: 'Anderer Anbieter', hint: 'GMX, WEB.DE, IONOS, Strato …' },
  { id: 'container', label: 'Eigener Postfix', hint: 'Zusatzdienst auf diesem Server' },
  { id: 'off', label: 'Aus', hint: 'keine Mails' },
]

const config = ref(null)
const presets = ref([])
const msLoopback = ref('http://localhost')
const publicUrl = ref('')
const choice = ref('')
const googleWay = ref('apppass')
const changeApp = ref(false)
const busy = ref(false)
const banner = ref('')
const bannerError = ref(false)
const flow = ref(null)
const registerReport = ref(null)
const testRecipient = ref('')
let pollTimer = null

const form = ref({
  email: '', password: '', clientId: '', clientSecret: '', msClientId: '', msTenant: '',
  preset: 'gmx', host: '', port: 587, encryption: 'starttls', from: '', verify: true,
  myhostname: '', relayHost: '', relayPort: 587, relayUser: '', relayPassword: '',
})

const msApp = computed(() => config.value?.ms_app || {})
const callbackUrl = ref('')
// Postfach-Anmeldung kommt von selbst zurueck: nur mit der App, die LogBot mit genau dieser Adresse angelegt hat.
const msDirect = computed(() => !!callbackUrl.value && !changeApp.value
  && msApp.value.app_id && msApp.value.callback_url === callbackUrl.value)
const modeLabel = computed(() => ({
  off: 'Aus', google: 'Google', microsoft: 'Microsoft', relay: 'SMTP-Server', container: 'Postfix-Container',
}[config.value?.mode] || '–'))
const presetHint = computed(() => presets.value.find(p => p.id === form.value.preset)?.hint || '')

function say(text, isError = false) {
  banner.value = text
  bannerError.value = isError
}

// --- kleine Bausteine: Gerätecode anzeigen, Adresse zurückkopieren -------------
const DeviceStep = defineComponent({
  props: { flow: Object },
  setup(props) {
    return () => h('div', { class: 'device-box space-y-2' }, [
      h('p', { class: 'text-sm' }, props.flow.copied
        ? ['Die Microsoft-Anmeldung ist im neuen Tab offen und der Code ', h('b', 'schon kopiert'),
            ' – dort einfügen (Strg+V), anmelden, zustimmen. Fertig.']
        : ['Bei Microsoft diesen Code eingeben, anmelden und zustimmen:']),
      h('p', { class: 'device-code' }, props.flow.user_code),
      h('div', { class: 'flex flex-wrap gap-2' }, [
        h('a', { href: props.flow.verification_uri, target: '_blank', rel: 'noopener', class: 'btn btn-secondary btn-sm' }, 'Microsoft-Anmeldung öffnen'),
        h('button', { class: 'btn btn-ghost btn-sm', onClick: () => navigator.clipboard?.writeText(props.flow.user_code) }, 'Code kopieren'),
      ]),
      h('p', { class: 'hint' }, 'Diese Seite wartet und macht von selbst weiter, sobald die Anmeldung erledigt ist.'),
    ])
  },
})

const PasteStep = defineComponent({
  props: { flow: Object, busy: Boolean },
  emits: ['submit'],
  setup(props, { emit }) {
    const value = ref('')
    // Eingefuegte Adresse mit Code: sofort abschliessen - der Code gilt nur wenige Minuten.
    const onPaste = (e) => {
      const text = (e.clipboardData?.getData('text') || '').trim()
      if (text.includes('code=') && !props.busy) {
        value.value = text
        setTimeout(() => emit('submit', text))
      }
    }
    return () => h('div', { class: 'device-box space-y-3' }, props.flow.returns_by_itself
      ? [h('p', { class: 'text-sm' }, 'Die Anmeldung läuft im neuen Fenster. Danach kommt der Browser von selbst hierher zurück.')]
      : [
          h('ol', { class: 'paste-steps' }, [
            h('li', [h('a', { href: props.flow.auth_url, target: '_blank', rel: 'noopener', class: 'btn btn-primary btn-sm' },
              'Anmeldeseite öffnen'), ' – anmelden und den Berechtigungen zustimmen.']),
            h('li', ['Danach zeigt der neue Tab eine Fehlerseite wie „Diese Seite ist nicht erreichbar“, die Adresse beginnt mit ',
              h('code', `${props.flow.redirect_uri.replace(/\/$/, '')}/?code=`), '. ', h('b', 'Das ist richtig – nichts ist kaputt.')]),
            h('li', 'Die komplette Adresse aus der Adresszeile dieses Tabs kopieren und hier einfügen. Der Code gilt nur wenige Minuten.'),
          ]),
          h('input', { class: 'input w-full', value: value.value, placeholder: `${props.flow.redirect_uri.replace(/\/$/, '')}/?code=…`,
            onInput: (e) => { value.value = e.target.value }, onPaste }),
          h('button', { class: 'btn btn-secondary btn-sm', disabled: props.busy || !value.value,
            onClick: () => emit('submit', value.value) }, props.busy ? 'Wird abgeschlossen …' : 'Anmeldung abschließen'),
        ])
  },
})

// --- Laden und Speichern ---------------------------------------------------------
async function load() {
  const data = await auth.api('/api/mail/config')
  config.value = data.config
  presets.value = data.presets
  msLoopback.value = data.microsoft_loopback
  callbackUrl.value = data.callback_url || ''
  publicUrl.value = data.public_url || window.location.origin
  if (!choice.value) {
    choice.value = { google: 'google', microsoft: msApp.value.personal_accounts ? 'outlook' : 'm365',
                     relay: 'smtp', container: 'container' }[config.value.mode] || ''
  }
  form.value.from = config.value.from_address || ''
  if (!testRecipient.value) testRecipient.value = auth.user?.email || ''
}

function pick(id) {
  choice.value = id
  flow.value = null
  stopPolling()
  if (id === 'smtp') applyPreset()
}

function applyPreset() {
  const p = presets.value.find(x => x.id === form.value.preset)
  if (p && p.id !== 'custom') {
    form.value.host = p.host
    form.value.port = p.port
    form.value.encryption = p.encryption
  }
}

async function savePublicUrl() {
  try {
    const data = await auth.api('/api/mail/public-url', { method: 'PUT', body: { public_url: publicUrl.value } })
    publicUrl.value = data.public_url
    say('Adresse gespeichert.')
  } catch (e) { say(e.message, true) }
}

async function ensurePublicUrl() {
  // Ohne Adresse gehen keine Links raus - beim ersten Einrichten die Adresse
  // übernehmen, über die der Administrator gerade arbeitet.
  if (!config.value?.ready && publicUrl.value) {
    try { await auth.api('/api/mail/public-url', { method: 'PUT', body: { public_url: publicUrl.value } }) } catch { /* bleibt sichtbar */ }
  }
}

async function saveSmtp(preset) {
  busy.value = true
  try {
    const p = presets.value.find(x => x.id === preset)
    const body = preset === 'gmail'
      ? { mode: 'relay', preset: 'gmail', smtp_host: 'smtp.gmail.com', smtp_port: 587, encryption: 'starttls',
          smtp_user: form.value.email, smtp_password: form.value.password, from_address: form.value.email,
          verify_certificate: true }
      : { mode: 'relay', preset, smtp_host: form.value.host || p?.host, smtp_port: form.value.port,
          encryption: form.value.encryption, smtp_user: form.value.email, smtp_password: form.value.password,
          from_address: form.value.from || form.value.email, verify_certificate: form.value.verify }
    await ensurePublicUrl()
    const data = await auth.api('/api/mail/config', { method: 'PUT', body })
    config.value = data.config
    form.value.password = ''
    say('Gespeichert. Jetzt eine Probemail schicken.')
  } catch (e) { say(e.message, true) } finally { busy.value = false }
}

async function saveContainer() {
  busy.value = true
  try {
    const data = await auth.api('/api/mail/config', { method: 'PUT', body: {
      mode: 'container', from_address: form.value.from, myhostname: form.value.myhostname,
      relay_host: form.value.relayHost, relay_port: form.value.relayPort, relay_user: form.value.relayUser,
      relay_password: form.value.relayPassword,
    } })
    config.value = data.config
    say('Gespeichert. Der Postfix-Container muss neu gestartet werden (System → Container).')
  } catch (e) { say(e.message, true) } finally { busy.value = false }
}

async function turnOff() {
  busy.value = true
  try {
    const data = await auth.api('/api/mail/config', { method: 'PUT', body: { mode: 'off' } })
    config.value = data.config
    say('Mailversand ist aus.')
  } catch (e) { say(e.message, true) } finally { busy.value = false }
}

async function sendTest() {
  busy.value = true
  try {
    const result = await auth.api('/api/mail/test', { method: 'POST', body: { recipient: testRecipient.value } })
    say(`Probemail an ${result.recipients.join(', ')} verschickt (${result.via}).`)
  } catch (e) { say(e.message, true) } finally { busy.value = false }
}

async function disconnect() {
  const data = await auth.api('/api/mail/oauth/disconnect', { method: 'POST' })
  config.value = data.config
  say('Anmeldung entfernt.')
}

function copy(text) {
  navigator.clipboard?.writeText(text).then(() => say('In die Zwischenablage kopiert.'), () => {})
}

// Gerätecode: Code gleich kopieren und die Microsoft-Seite öffnen - der Nutzer fügt nur noch ein.
async function showDevice(data, purpose) {
  let copied = false
  try { await navigator.clipboard.writeText(data.user_code); copied = true } catch { /* Code steht groß da */ }
  window.open(data.verification_uri, '_blank', 'noopener')
  flow.value = { ...data, kind: 'device', purpose, copied }
  poll()
}

// --- OAuth ------------------------------------------------------------------
async function startGoogle() {
  busy.value = true
  try {
    await ensurePublicUrl()
    const data = await auth.api('/api/mail/oauth/google/start', { method: 'POST', body: {
      client_id: form.value.clientId, client_secret: form.value.clientSecret, return_mode: 'auto' } })
    if (data.returns_by_itself) { window.location.assign(data.auth_url); return }
    flow.value = { ...data, kind: 'authorize' }
  } catch (e) { say(e.message, true) } finally { busy.value = false }
}

async function startRegister(method) {
  busy.value = true
  registerReport.value = null
  try {
    // Die App bekommt LogBots oeffentliche Adresse als Ruecksprung - vorher speichern.
    await ensurePublicUrl()
    const data = await auth.api('/api/mail/oauth/microsoft/register/start', { method: 'POST', body: {
      method, personal_accounts: choice.value === 'outlook' } })
    if (method === 'device') {
      await showDevice(data, 'register')
    } else {
      // Zurueckkopieren noetig: erst die Anleitung zeigen, die Seite oeffnet der Knopf darin.
      flow.value = { ...data, kind: 'register_authorize', returns_by_itself: false }
    }
  } catch (e) { say(e.message, true) } finally { busy.value = false }
}

async function startMailbox(method) {
  busy.value = true
  try {
    await ensurePublicUrl()
    const data = await auth.api('/api/mail/oauth/microsoft/start', { method: 'POST', body: {
      client_id: changeApp.value || !msApp.value.app_id ? form.value.msClientId : '',
      tenant: form.value.msTenant, account_type: choice.value === 'outlook' ? 'personal' : 'work',
      method, return_mode: 'paste' } })
    if (method === 'device') {
      await showDevice(data, 'mailbox')
    } else if (data.returns_by_itself) {
      // Wie bei anderen Diensten: im selben Tab zu Microsoft und von dort direkt hierher zurück.
      window.location.assign(data.auth_url)
    } else {
      flow.value = { ...data, kind: 'authorize' }
    }
  } catch (e) { say(e.message, true) } finally { busy.value = false }
}

function stopPolling() { clearTimeout(pollTimer) }

async function poll() {
  stopPolling()
  if (!flow.value || flow.value.kind !== 'device') return
  try {
    const result = await auth.api('/api/mail/oauth/poll', { method: 'POST', body: { flow_id: flow.value.flow_id } })
    if (result.status === 'pending') {
      pollTimer = setTimeout(poll, 4000)
      return
    }
    handleResult(result)
  } catch (e) {
    flow.value = null
    say(e.message, true)
  }
}

async function completePaste(pasted) {
  busy.value = true
  try {
    const result = await auth.api('/api/mail/oauth/complete', { method: 'POST', body: { flow_id: flow.value.flow_id, pasted } })
    handleResult(result)
  } catch (e) { say(e.message, true) } finally { busy.value = false }
}

async function handleResult(result) {
  flow.value = null
  if (result.status === 'registered') {
    registerReport.value = result.steps
    changeApp.value = false
    say('App-Registrierung angelegt. Jetzt mit dem Postfach anmelden (Schritt 2).')
  } else if (result.status === 'connected') {
    say(`Angemeldet als ${result.account}. Mails gehen ab jetzt über dieses Konto.`)
  }
  await load()
}

onMounted(async () => {
  try { await load() } catch (e) { say(e.message, true) }
  const state = route.query.oauth
  if (state) {
    const texts = { connected: ['Angemeldet – der Mailversand ist eingerichtet.', false],
      denied: ['Die Anmeldung wurde abgelehnt.', true], expired: ['Die Anmeldung ist abgelaufen – bitte neu starten.', true],
      failed: ['Die Anmeldung ist fehlgeschlagen – Details im Systemtagebuch.', true] }
    const [text, isError] = texts[state] || ['', false]
    if (text) say(text, isError)
    router.replace({ query: {} })
  }
})
onBeforeUnmount(stopPolling)
</script>

<style scoped>
.section-title {
  font-size: 0.9375rem;
  font-weight: 600;
  margin-bottom: 0.625rem;
  color: var(--color-text-primary);
}

.tile {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.875rem;
  text-align: left;
}

.tile.is-picked {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 1px var(--color-primary);
}

.tile-title {
  font-weight: 600;
  color: var(--color-text-primary);
}

.tile-hint {
  font-size: 0.75rem;
  color: var(--color-text-muted);
}

.steps {
  list-style: decimal;
  padding-left: 1.25rem;
  font-size: 0.875rem;
  color: var(--color-text-secondary);
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.copyable {
  display: inline-block;
  cursor: copy;
  word-break: break-all;
}
.paste-steps {
  list-style: decimal;
  padding-left: 1.25rem;
  font-size: 0.875rem;
  display: grid;
  gap: 0.5rem;
}
.steps-report {
  font-size: 0.8125rem;
  color: var(--color-success);
  list-style: '✓ ';
  padding-left: 1.25rem;
}

.step-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.step-no {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.5rem;
  height: 1.5rem;
  border-radius: var(--radius-full);
  background-color: var(--color-primary);
  color: #fff;
  font-size: 0.75rem;
}

.link {
  color: var(--color-primary);
  cursor: pointer;
}

:deep(.device-box) {
  margin-top: 0.75rem;
  padding: 0.875rem;
  border: 1px dashed var(--color-border);
  border-radius: var(--radius);
}

:deep(.device-code) {
  font-family: var(--font-mono);
  font-size: 1.75rem;
  font-weight: 700;
  letter-spacing: 0.25rem;
  margin: 0.5rem 0;
  color: var(--color-text-primary);
}

:deep(.link) {
  color: var(--color-primary);
}
</style>

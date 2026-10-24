<!-- ==============================================================================
     Name:        Phydran6
     Kontakt:     Phydran6
     Changelog:   ../../../CHANGELOG/frontend.md
     Beschreibung: LogBot - Meldungen → Kanäle → Telegram: Bot verbinden.

     Drei Schritte: Bot bei @BotFather anlegen und Token einfügen, Chat per
     Start-Link (oder QR-Code am Handy) verbinden, Testnachricht. Welche
     Ereignisse nach Telegram gehen, steht unter Meldungen → Regeln - ab Werk
     die wirklich kritischen Logzeilen und Fehler von LogBot selbst.
     ============================================================================== -->
<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2 class="page-title">Telegram</h2>
        <p class="page-subtitle">Kritische Ereignisse als Nachricht aufs Handy – über einen eigenen Telegram-Bot.</p>
      </div>
    </div>

    <p v-if="banner" class="card card-body mb-4 text-sm" :style="{ color: bannerError ? 'var(--color-danger)' : 'var(--color-success)' }">{{ banner }}</p>

    <!-- Schritt 1 -->
    <div class="card mb-4">
      <div class="card-header"><span class="card-title"><span class="step-no">1</span> Bot anlegen</span>
        <span v-if="tg.bot_username" class="badge badge-success">@{{ tg.bot_username }}</span></div>
      <div class="card-body space-y-3 max-w-2xl">
        <ol class="steps">
          <li>In Telegram <a href="https://t.me/BotFather" target="_blank" rel="noopener" class="link">@BotFather</a> öffnen und <code>/newbot</code> schicken.</li>
          <li>Einen Namen (z.B. „LogBot Firma“) und einen Benutzernamen, der auf <code>bot</code> endet, vergeben.</li>
          <li>Den Token, den BotFather schickt (Form <code>123456789:AA…</code>), hier einfügen.</li>
        </ol>
        <div class="flex gap-2 flex-wrap">
          <input v-model="token" type="password" class="input flex-1" style="min-width: 18rem"
                 :placeholder="tg.bot_token_set ? 'Token hinterlegt – zum Ersetzen neu einfügen' : '123456789:AA…'" autocomplete="off">
          <button class="btn btn-primary btn-sm" :disabled="busy || !token" @click="saveToken">Prüfen und speichern</button>
        </div>
        <p v-if="tg.bot_token_readable === false" class="hint" style="color: var(--color-danger)">
          Der hinterlegte Token ist auf diesem Server nicht lesbar (anderer Server / neues JWT_SECRET) – bitte neu einfügen.
        </p>
      </div>
    </div>

    <!-- Schritt 2 -->
    <div class="card mb-4" :class="{ 'is-disabled': !tg.bot_username }">
      <div class="card-header"><span class="card-title"><span class="step-no">2</span> Chat verbinden</span></div>
      <div class="card-body space-y-3">
        <button class="btn btn-primary btn-sm" :disabled="busy || !tg.bot_username" @click="startLink">Verbindungslink erzeugen</button>
        <div v-if="link" class="link-box">
          <img :src="link.qr_image" alt="QR-Code zum Verbinden" class="qr">
          <div class="space-y-2 text-sm">
            <p>Am Handy den QR-Code scannen oder den Link öffnen und in Telegram auf <b>„Starten“</b> tippen:</p>
            <a :href="link.url" target="_blank" rel="noopener" class="link font-mono break-all">{{ link.url }}</a>
            <p class="hint">Für eine Gruppe: den Bot in die Gruppe aufnehmen und dort <code>{{ link.group_command }}</code> schicken.</p>
            <p class="hint">Diese Seite wartet und meldet sich, sobald der Chat verbunden ist (Link gilt 15 Minuten).</p>
          </div>
        </div>
        <ul v-if="tg.chats?.length" class="chats">
          <li v-for="chat in tg.chats" :key="chat.id">
            <span>{{ chat.type === 'private' ? '👤' : '👥' }} {{ chat.title }}</span>
            <span class="hint">verbunden {{ chat.linked_at?.slice(0, 10) }}</span>
            <button class="btn btn-ghost btn-sm" @click="removeChat(chat.id)">Entfernen</button>
          </li>
        </ul>
      </div>
    </div>

    <!-- Schritt 3 -->
    <div class="card mb-4">
      <div class="card-header"><span class="card-title"><span class="step-no">3</span> Ausprobieren</span></div>
      <div class="card-body flex flex-wrap gap-2 items-center">
        <button class="btn btn-secondary btn-sm" :disabled="busy || !tg.chats?.length" @click="test">Testnachricht senden</button>
        <router-link to="/notifications/rules" class="btn btn-ghost btn-sm">Welche Ereignisse? → Regeln</router-link>
        <button v-if="tg.bot_username" class="btn btn-ghost btn-sm" style="color: var(--color-danger)" @click="removeBot">Bot entfernen</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const tg = ref({})
const token = ref('')
const link = ref(null)
const busy = ref(false)
const banner = ref('')
const bannerError = ref(false)
let timer = null

function say(text, isError = false) { banner.value = text; bannerError.value = isError }

async function load() {
  const data = await auth.api('/api/notifications/config')
  tg.value = data.config.telegram || {}
}

async function saveToken() {
  busy.value = true
  try {
    const data = await auth.api('/api/notifications/telegram/token', { method: 'POST', body: { bot_token: token.value.trim() } })
    token.value = ''
    say(`Bot @${data.bot.username} („${data.bot.name}“) ist hinterlegt. Jetzt den Chat verbinden.`)
    await load()
  } catch (e) { say(e.message, true) } finally { busy.value = false }
}

async function startLink() {
  busy.value = true
  try {
    link.value = await auth.api('/api/notifications/telegram/link/start', { method: 'POST' })
    poll()
  } catch (e) { say(e.message, true) } finally { busy.value = false }
}

async function poll() {
  clearTimeout(timer)
  if (!link.value) return
  try {
    const result = await auth.api('/api/notifications/telegram/link/poll', { method: 'POST' })
    if (result.status === 'linked') {
      link.value = null
      say(`Chat „${result.chat.title}“ ist verbunden – dort kam eben eine Bestätigung an.`)
      await load()
      return
    }
    timer = setTimeout(poll, 3000)
  } catch (e) {
    link.value = null
    say(e.message, true)
  }
}

async function removeChat(id) {
  await auth.api('/api/notifications/telegram/chat/remove', { method: 'POST', body: { chat_id: id } })
  await load()
}

async function removeBot() {
  if (!confirm('Bot-Token und alle verbundenen Chats entfernen?')) return
  await auth.api('/api/notifications/telegram', { method: 'DELETE' })
  say('Telegram ist entfernt.')
  await load()
}

async function test() {
  busy.value = true
  try {
    const result = await auth.api('/api/notifications/test', { method: 'POST', body: { channels: ['telegram'] } })
    const d = result.delivery?.telegram || {}
    say(d.ok ? 'Testnachricht verschickt.' : `Nicht zugestellt: ${JSON.stringify(d.results || d.skipped || d)}`, !d.ok)
  } catch (e) { say(e.message, true) } finally { busy.value = false }
}

onMounted(() => load().catch(e => say(e.message, true)))
onBeforeUnmount(() => clearTimeout(timer))
</script>

<style scoped>
.steps {
  list-style: decimal;
  padding-left: 1.25rem;
  font-size: 0.875rem;
  color: var(--color-text-secondary);
}

.step-no {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.375rem;
  height: 1.375rem;
  margin-right: 0.375rem;
  border-radius: var(--radius-full);
  background-color: var(--color-primary);
  color: #fff;
  font-size: 0.75rem;
}

.is-disabled {
  opacity: 0.6;
}

.link-box {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  align-items: flex-start;
}

.qr {
  width: 10rem;
  height: 10rem;
  border-radius: var(--radius);
  background: #fff;
}

.chats li {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.375rem 0;
  border-bottom: 1px solid var(--color-border);
}

.link {
  color: var(--color-primary);
}
</style>

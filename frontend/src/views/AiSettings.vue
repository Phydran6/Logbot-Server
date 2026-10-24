<!-- ==============================================================================
     Name:        Phydran6
     Kontakt:     Phydran6
     Changelog:   ../../../CHANGELOG/frontend.md
     Beschreibung: LogBot - System -> KI-Auswertung: Weg waehlen, testen, fragen.
     ============================================================================== -->

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">{{ t('ai.title') }}</h1>
        <p class="page-subtitle">{{ t('ai.intro') }}</p>
      </div>
    </div>

    <p v-if="error" class="alert alert-danger">{{ error }}</p>
    <p v-if="message" class="alert alert-success">{{ message }}</p>

    <!-- ========================================================== Weg waehlen -->
    <section class="card">
      <div class="card-header">
        <h2 class="card-title">{{ t('ai.provider') }}</h2>
      </div>
      <div class="card-body space-y-4">
        <div class="provider-grid">
          <label
            v-for="option in providers"
            :key="option.id"
            class="provider"
            :class="{ 'is-picked': config.provider === option.id }"
          >
            <input v-model="config.provider" type="radio" :value="option.id">
            <span>
              <strong>
                {{ locale === 'en' ? option.label_en : option.label }}
                <!-- Der Unterschied, auf den es bei Logdaten ankommt: bleibt
                     die Auswertung im Haus oder nicht? -->
                <span v-if="option.local" class="badge badge-success ml-1">bleibt im Haus</span>
              </strong>
              <em>{{ option.hint }}</em>
            </span>
          </label>
        </div>

        <p v-if="config.provider !== 'off' && !current?.local" class="alert alert-warning">
          {{ t('ai.dataWarning') }}
        </p>
        <p v-else-if="current?.local" class="alert alert-info">
          Läuft die Gegenstelle auf diesem Server (Open WebUI mit lokalem Modell über
          Ollama), verlässt keine Logzeile das Haus. Zeigt die Adresse dagegen nach
          außen, gilt dieselbe Warnung wie bei jedem anderen Anbieter: die ausgewählten
          Zeilen gehen dorthin.
        </p>

        <!-- ================================================ OpenRouter-Assistent -->
        <div v-if="config.provider === 'openrouter'" class="openrouter space-y-4">
          <div>
            <p class="step-head"><span class="step-no">1</span> Mit OpenRouter verbinden
              <span v-if="config.api_key_set" class="badge badge-success ml-2">verbunden</span></p>
            <p class="hint mb-2">
              OpenRouter bündelt Claude, GPT, Gemini, Llama und viele weitere Modelle – auch kostenlose – hinter
              einem Konto. Bei der Anmeldung legt OpenRouter einen Schlüssel nur für LogBot an; er lässt sich dort
              jederzeit widerrufen.
            </p>
            <div class="flex flex-wrap gap-2">
              <button class="btn btn-primary btn-sm" :disabled="orBusy" @click="openRouterLogin">Mit OpenRouter anmelden</button>
              <button class="btn btn-secondary btn-sm" @click="orManual = !orManual">Schlüssel selbst einfügen</button>
            </div>
            <div v-if="orManual" class="flex gap-2 mt-2">
              <input v-model="orKey" type="password" class="input" placeholder="sk-or-v1-…" autocomplete="off">
              <button class="btn btn-secondary btn-sm" :disabled="orBusy || !orKey" @click="openRouterKey">Übernehmen</button>
            </div>
            <p v-if="orInfo" class="hint mt-1">{{ orInfo }}</p>
          </div>
          <div>
            <p class="step-head"><span class="step-no">2</span> Modell wählen
              <span class="hint ml-2">aktuell: <code>{{ config.model || '–' }}</code></span></p>
            <div class="flex gap-2 flex-wrap mb-2">
              <input v-model="orFilter" class="input" placeholder="Suchen: claude, gpt, llama, gemini …" style="max-width: 20rem">
              <label class="flex items-center gap-1 text-sm"><input v-model="orFreeOnly" type="checkbox"> nur kostenlose</label>
              <button class="btn btn-ghost btn-sm" :disabled="orBusy" @click="loadOpenRouterModels(true)">Liste laden</button>
            </div>
            <div v-if="orModels.length" class="model-list">
              <button v-for="m in shownModels" :key="m.id" class="model" :class="{ 'is-picked': config.model === m.id }"
                      :title="m.description" @click="pickOpenRouterModel(m.id)">
                <span class="model-name">{{ m.name }}</span>
                <span class="model-meta font-mono">{{ m.id }}</span>
                <span class="model-meta">
                  <span v-if="m.free" class="badge badge-success">kostenlos</span>
                  <template v-else>{{ m.price_in }} $ / {{ m.price_out }} $ je 1 Mio. Token</template>
                  <template v-if="m.context"> · {{ Math.round(m.context / 1000) }}k Kontext</template>
                </span>
              </button>
            </div>
            <p class="hint">Kostenlose Modelle haben bei OpenRouter enge Tageslimits und können Anfragen für Training nutzen – für Logdaten lieber ein bezahltes Modell.</p>
          </div>
        </div>

        <!-- Nur zeigen, was der gewählte Weg braucht. -->
        <div v-if="current?.needs_key && config.provider !== 'openrouter'" class="space-y-1">
          <label class="label">{{ t('ai.apiKey') }}</label>
          <input
            v-model="apiKey"
            type="password"
            class="input"
            autocomplete="off"
            :placeholder="config.api_key_set ? t('ai.apiKeyKeep') : ''"
          >
          <p class="hint">
            {{ config.api_key_set ? t('ai.apiKeySet') : '' }}
            {{ current.key_hint || '' }}
            <a v-if="current.key_url" class="link" :href="current.key_url" target="_blank" rel="noopener">
              {{ current.key_url }}
            </a>
          </p>
        </div>

        <div v-if="current?.needs_url" class="space-y-1">
          <label class="label">{{ t('ai.webhookUrl') }}</label>
          <input v-model="config.webhook_url" type="url" class="input"
                 :placeholder="current.default_url || 'https://n8n.example.com/webhook/logbot'">
          <label class="label mt-2">Kopfzeile <span class="hint">({{ t('common.optional') }}, „Name: Wert“)</span></label>
          <input v-model="config.webhook_header" type="text" class="input" placeholder="X-Auth: geheim">
        </div>

        <div v-if="config.provider !== 'off'" class="grid gap-3 sm:grid-cols-2">
          <div v-if="current?.needs_key && config.provider !== 'openrouter'">
            <label class="label">{{ t('ai.model') }}</label>
            <!-- Bei Open WebUI hängt hinter der Adresse das, was der Betreiber
                 selbst installiert hat - den Namen kann niemand erraten. Also
                 abfragen statt abtippen lassen. -->
            <div class="flex gap-2">
              <input v-model="config.model" type="text" class="input" :placeholder="current.default_model"
                     list="ai-model-options">
              <button
                v-if="config.provider === 'openwebui'"
                type="button"
                class="btn btn-secondary btn-sm shrink-0"
                :disabled="loadingModels"
                @click="loadModels"
              >
                {{ loadingModels ? '…' : 'Modelle holen' }}
              </button>
            </div>
            <datalist id="ai-model-options">
              <option v-for="entry in models" :key="entry.id" :value="entry.id">{{ entry.label }}</option>
            </datalist>
            <p v-if="modelNote" class="hint">{{ modelNote }}</p>
          </div>
          <div>
            <label class="label">{{ t('ai.maxLogs') }}</label>
            <input v-model.number="config.max_logs" type="number" min="1" :max="limits.max_logs" class="input">
          </div>
        </div>

        <div v-if="config.provider !== 'off'">
          <label class="label">{{ t('ai.systemPrompt') }}</label>
          <textarea v-model="config.system_prompt" class="textarea" rows="4"
                    :placeholder="defaultPrompt"></textarea>
        </div>

        <div v-if="config.provider !== 'off'" class="space-y-2">
          <label class="toggle">
            <input v-model="config.include_raw" type="checkbox">
            <span>{{ t('ai.includeRaw') }}</span>
          </label>
          <label class="toggle">
            <input v-model="config.enabled_for_users" type="checkbox">
            <span>{{ t('ai.allowUsers') }}</span>
          </label>
        </div>

        <div class="flex flex-wrap gap-2">
          <button class="btn btn-primary" :disabled="saving" @click="save">
            {{ saving ? t('common.saving') : t('common.save') }}
          </button>
          <button
            class="btn btn-secondary"
            :disabled="testing || config.provider === 'off'"
            @click="test"
          >
            {{ testing ? t('common.loading') : t('ai.testConnection') }}
          </button>
        </div>

        <p v-if="testResult" class="alert" :class="testResult.ok ? 'alert-success' : 'alert-danger'">
          {{ testResult.message }}
          <span v-if="testResult.answer"> — „{{ testResult.answer }}“</span>
        </p>
      </div>
    </section>

    <!-- ============================================================== Fragen -->
    <section v-if="config.provider !== 'off'" class="card">
      <div class="card-header">
        <h2 class="card-title">{{ t('ai.ask') }}</h2>
      </div>
      <div class="card-body space-y-3">
        <div>
          <label class="label">{{ t('ai.question') }}</label>
          <input v-model="question" type="text" class="input"
                 placeholder="Was ist heute Nacht auf srv01 schiefgelaufen?">
        </div>

        <div class="grid gap-3 sm:grid-cols-3">
          <div>
            <label class="label">Host</label>
            <input v-model="ask.hostname" type="text" class="input">
          </div>
          <div>
            <label class="label">Ab Schweregrad</label>
            <select v-model="ask.min_severity" class="select">
              <option value="">{{ t('common.none') }}</option>
              <option value="error">error</option>
              <option value="warning">warning</option>
              <option value="critical">critical</option>
            </select>
          </div>
          <div>
            <label class="label">Zeitraum (Stunden)</label>
            <input v-model.number="ask.hours" type="number" min="1" max="720" class="input">
          </div>
        </div>

        <div class="flex flex-wrap gap-2">
          <button class="btn btn-ghost" :disabled="busy" @click="preview">{{ t('ai.preview') }}</button>
          <button class="btn btn-primary" :disabled="busy" @click="analyze">
            {{ busy ? t('common.loading') : t('ai.ask') }}
          </button>
        </div>

        <div v-if="previewData" class="preview-box">
          <p class="hint">
            {{ previewData.count }} Zeilen · {{ previewData.characters }} Zeichen ·
            ca. {{ previewData.approx_tokens }} Token → {{ previewData.target }}
          </p>
          <pre class="preview-text">{{ previewData.sample }}</pre>
        </div>

        <div v-if="answer" class="answer-box">
          <p class="hint">
            {{ answer.provider }} · {{ answer.model }} · {{ answer.logs_sent }} Zeilen ·
            {{ answer.duration_seconds }}s
          </p>
          <p class="answer-text">{{ answer.answer }}</p>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useI18n } from '../i18n'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

// --- OpenRouter-Assistent -----------------------------------------------------
const orBusy = ref(false)
const orManual = ref(false)
const orKey = ref('')
const orInfo = ref('')
const orModels = ref([])
const orFilter = ref('')
const orFreeOnly = ref(false)
const shownModels = computed(() => {
  const term = orFilter.value.trim().toLowerCase()
  return orModels.value
    .filter(m => !orFreeOnly.value || m.free)
    .filter(m => !term || m.id.toLowerCase().includes(term) || m.name.toLowerCase().includes(term))
    .slice(0, 60)
})

function keyInfo(key) {
  if (!key) return ''
  const used = key.usage != null ? `verbraucht ${Number(key.usage).toFixed(2)} $` : ''
  const limit = key.limit != null ? ` von ${key.limit} $` : ''
  return `Schlüssel aktiv${key.label ? ' („' + key.label + '“)' : ''}${used ? ' · ' + used + limit : ''}${key.is_free_tier ? ' · kostenloses Kontingent' : ''}`
}

async function openRouterLogin() {
  orBusy.value = true
  error.value = ''
  try {
    const data = await auth.api('/api/ai/openrouter/start', { method: 'POST',
      body: { callback_url: `${window.location.origin}/ai/openrouter` } })
    window.location.href = data.auth_url
  } catch (err) {
    error.value = err.message
    orBusy.value = false
  }
}

async function openRouterKey() {
  orBusy.value = true
  error.value = ''
  try {
    const data = await auth.api('/api/ai/openrouter/key', { method: 'POST', body: { api_key: orKey.value.trim(), model: config.value.model } })
    config.value = data.config
    orInfo.value = keyInfo(data.key)
    orKey.value = ''
    orManual.value = false
    message.value = 'OpenRouter ist eingerichtet.'
    loadOpenRouterModels()
  } catch (err) {
    error.value = err.message
  } finally {
    orBusy.value = false
  }
}

async function loadOpenRouterModels(force = false) {
  try {
    orModels.value = (await auth.api(`/api/ai/openrouter/models${force ? '?force=true' : ''}`)).items
  } catch (err) {
    orInfo.value = err.message
  }
}

async function pickOpenRouterModel(id) {
  try {
    const data = await auth.api(`/api/ai/openrouter/model?model=${encodeURIComponent(id)}`, { method: 'PUT' })
    config.value = data.config
    message.value = `Modell ${id} gewählt.`
  } catch (err) {
    // Noch nicht verbunden: Auswahl merken, beim Verbinden mitgeben.
    config.value.model = id
    if (!config.value.api_key_set) message.value = `Modell ${id} vorgemerkt – jetzt verbinden.`
    else error.value = err.message
  }
}

async function finishOpenRouterCallback() {
  const { code, state } = route.query
  if (route.name !== 'OpenRouterCallback' || !code || !state) return
  orBusy.value = true
  try {
    const data = await auth.api('/api/ai/openrouter/exchange', { method: 'POST',
      body: { code: String(code), state: String(state), model: config.value.model || null } })
    config.value = data.config
    orInfo.value = keyInfo(data.key)
    message.value = 'Mit OpenRouter verbunden. Jetzt ein Modell wählen.'
    loadOpenRouterModels()
  } catch (err) {
    error.value = err.message
  } finally {
    orBusy.value = false
    router.replace('/ai')
  }
}
const { t, locale } = useI18n()

const config = ref({ provider: 'off', max_logs: 100 })
const providers = ref([])
const models = ref([])
const modelNote = ref('')
const loadingModels = ref(false)
const limits = ref({ max_logs: 500 })
const defaultPrompt = ref('')
const apiKey = ref('')

const saving = ref(false)
const testing = ref(false)
const busy = ref(false)
const error = ref('')
const message = ref('')
const testResult = ref(null)

const question = ref('')
const ask = ref({ hostname: '', min_severity: '', hours: 24 })
const previewData = ref(null)
const answer = ref(null)

const current = computed(() => providers.value.find(p => p.id === config.value.provider))

async function load() {
  try {
    const data = await auth.api('/api/ai/config')
    config.value = data.config
    providers.value = data.providers
    limits.value = data.limits
    defaultPrompt.value = data.default_system_prompt
  } catch (err) {
    error.value = err.message
  }
}

async function save() {
  saving.value = true
  error.value = ''
  message.value = ''
  try {
    const body = { ...config.value }
    // Leeres Feld heißt "Schlüssel behalten" - deshalb nur mitschicken, wenn
    // wirklich etwas eingetippt wurde.
    if (apiKey.value) body.api_key = apiKey.value
    delete body.api_key_set
    delete body.provider_label
    const data = await auth.api('/api/ai/config', { method: 'PUT', body })
    config.value = data.config
    apiKey.value = ''
    message.value = t('common.success')
  } catch (err) {
    error.value = err.message
  } finally {
    saving.value = false
  }
}

/**
 * Holt die Modellliste der eingerichteten Gegenstelle (derzeit Open WebUI).
 *
 * Warum das nicht automatisch passiert: es braucht Adresse UND Schlüssel, und
 * beides ist erst nach dem Speichern hinterlegt. Ein Knopf sagt klarer, was
 * gerade passiert, als eine Abfrage, die im Hintergrund still scheitert.
 */
async function loadModels() {
  loadingModels.value = true
  modelNote.value = ''
  try {
    const data = await auth.api('/api/ai/models')
    models.value = data.models || []
    modelNote.value = data.note
      || (models.value.length ? `${models.value.length} Modell(e) gefunden.` : '')
  } catch (err) {
    modelNote.value = err.message
  } finally {
    loadingModels.value = false
  }
}

async function test() {
  testing.value = true
  testResult.value = null
  try {
    testResult.value = await auth.api('/api/ai/test', { method: 'POST' })
  } catch (err) {
    testResult.value = { ok: false, message: err.message }
  } finally {
    testing.value = false
  }
}

function askBody() {
  return {
    question: question.value,
    hostname: ask.value.hostname || null,
    min_severity: ask.value.min_severity || null,
    hours: ask.value.hours,
  }
}

async function preview() {
  busy.value = true
  error.value = ''
  answer.value = null
  try {
    previewData.value = await auth.api('/api/ai/preview', { method: 'POST', body: askBody() })
  } catch (err) {
    error.value = err.message
  } finally {
    busy.value = false
  }
}

async function analyze() {
  busy.value = true
  error.value = ''
  previewData.value = null
  try {
    answer.value = await auth.api('/api/ai/analyze', { method: 'POST', body: askBody() })
  } catch (err) {
    error.value = err.message
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  await load()
  await finishOpenRouterCallback()
  if (config.value.provider === 'openrouter') loadOpenRouterModels()
})
</script>

<style scoped>
.provider-grid {
  display: grid;
  gap: 0.5rem;
}

@media (min-width: 768px) {
  .provider-grid {
    grid-template-columns: 1fr 1fr;
  }
}

.provider {
  display: flex;
  align-items: flex-start;
  gap: 0.625rem;
  padding: 0.75rem;
  border-radius: var(--radius);
  border: 1px solid var(--color-border);
  cursor: pointer;
  font-size: 0.8125rem;
}

.provider:hover {
  background-color: var(--hover-surface);
}

.provider.is-picked {
  border-color: var(--color-primary);
  background-color: var(--primary-soft);
}

.provider input {
  margin-top: 0.1875rem;
  flex-shrink: 0;
}

.provider span {
  display: flex;
  flex-direction: column;
  gap: 0.1875rem;
  min-width: 0;
}

.provider strong {
  color: var(--color-text-primary);
  font-weight: 600;
}

.provider em {
  font-style: normal;
  font-size: 0.6875rem;
  color: var(--color-text-muted);
}

.toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8125rem;
  color: var(--color-text-secondary);
  cursor: pointer;
}

.preview-box,
.answer-box {
  padding: 0.75rem;
  border-radius: var(--radius);
  border: 1px solid var(--color-border);
  background-color: var(--color-surface-elevated);
}

.preview-text {
  margin-top: 0.5rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.6875rem;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 16rem;
  overflow: auto;
  color: var(--color-text-secondary);
}

.answer-text {
  margin-top: 0.5rem;
  white-space: pre-wrap;
  font-size: 0.875rem;
  color: var(--color-text-primary);
  line-height: 1.6;
}

.alert {
  padding: 0.625rem 0.875rem;
  border-radius: var(--radius);
  font-size: 0.8125rem;
  margin-bottom: 0.75rem;
  border: 1px solid var(--color-border);
}

.alert-danger {
  background-color: var(--danger-soft);
  color: var(--color-danger);
  border-color: var(--color-danger);
}

.alert-success {
  background-color: var(--primary-soft);
  color: var(--color-success);
}

/* Fuer den umgekehrten Fall: die Daten bleiben hier. Das ist eine gute
   Nachricht und soll nicht wie eine Warnung aussehen. */
.alert-info {
  background-color: var(--success-soft);
  color: var(--color-success);
}

.alert-warning {
  background-color: var(--primary-soft);
  color: var(--color-warning);
  border-color: var(--color-warning);
}

.step-head {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  font-weight: 600;
  margin-bottom: 0.375rem;
}

.step-no {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.375rem;
  height: 1.375rem;
  border-radius: var(--radius-full);
  background-color: var(--color-primary);
  color: #fff;
  font-size: 0.75rem;
}

.model-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(16rem, 1fr));
  gap: 0.5rem;
  max-height: 22rem;
  overflow-y: auto;
  margin-bottom: 0.5rem;
}

.model {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
  padding: 0.5rem 0.625rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  text-align: left;
}

.model:hover { border-color: var(--color-primary); }
.model.is-picked { border-color: var(--color-primary); box-shadow: 0 0 0 1px var(--color-primary); }
.model-name { font-weight: 600; font-size: 0.8125rem; }
.model-meta { font-size: 0.6875rem; color: var(--color-text-muted); }
</style>

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
              <strong>{{ locale === 'en' ? option.label_en : option.label }}</strong>
              <em>{{ option.hint }}</em>
            </span>
          </label>
        </div>

        <p v-if="config.provider !== 'off'" class="alert alert-warning">
          {{ t('ai.dataWarning') }}
        </p>

        <!-- Nur zeigen, was der gewählte Weg braucht. -->
        <div v-if="current?.needs_key" class="space-y-1">
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
          <div v-if="current?.needs_key">
            <label class="label">{{ t('ai.model') }}</label>
            <input v-model="config.model" type="text" class="input" :placeholder="current.default_model">
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
import { useAuthStore } from '../stores/auth'
import { useI18n } from '../i18n'

const auth = useAuthStore()
const { t, locale } = useI18n()

const config = ref({ provider: 'off', max_logs: 100 })
const providers = ref([])
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

onMounted(load)
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

.alert-warning {
  background-color: var(--primary-soft);
  color: var(--color-warning);
  border-color: var(--color-warning);
}
</style>

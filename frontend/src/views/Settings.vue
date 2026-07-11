<!-- ==============================================================================
     Name:        Phydran6
     Kontakt:     Phydran6
     Version:     2026.07.11.13.03.42
     Changelog:   ../../../CHANGELOG/frontend.md
     Beschreibung: LogBot - Einstellungen mit Theme-Support (inkl. Netzwerk-Tab: Reverse Proxy + DNS)
     ============================================================================== -->

<template>
  <div class="p-6">
    <h1 class="text-2xl font-bold mb-6" :style="{ color: 'var(--color-text-primary)' }">Einstellungen</h1>
    <!-- Tabs -->
    <div class="flex flex-wrap gap-2 mb-6">
      <button
        v-for="tab in availableTabs"
        :key="tab.id"
        class="px-3 py-2 rounded text-sm"
        :style="tabButtonStyle(tab.id)"
        @click="setTab(tab.id)"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- Allgemein -->
    <div v-if="activeTab === 'general'" class="rounded-lg shadow p-6" :style="cardStyle">
      <h2 class="text-lg font-semibold mb-4" :style="{ color: 'var(--color-text-primary)' }">Allgemeine Einstellungen</h2>
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium mb-1" :style="{ color: 'var(--color-text-secondary)' }">Anwendungsname</label>
          <input v-model="settings.app_name" type="text" class="w-full rounded px-3 py-2" :style="inputStyle">
        </div>
        <div>
          <label class="block text-sm font-medium mb-1" :style="{ color: 'var(--color-text-secondary)' }">Zeitzone</label>
          <input v-model="settings.timezone" type="text" class="w-full rounded px-3 py-2" :style="inputStyle" placeholder="Europe/Berlin">
        </div>
        <div>
          <label class="block text-sm font-medium mb-1" :style="{ color: 'var(--color-text-secondary)' }">Agent Offline Timeout (Sekunden)</label>
          <input v-model.number="settings.agent_offline_timeout" type="number" min="60" class="w-full rounded px-3 py-2" :style="inputStyle">
          <p class="text-xs mt-1" :style="{ color: 'var(--color-text-muted)' }">Nach dieser Zeit ohne Logs gilt ein Agent als offline</p>
        </div>
        <div>
          <label class="block text-sm font-medium mb-1" :style="{ color: 'var(--color-text-secondary)' }">Max. Logs pro API-Anfrage</label>
          <input v-model.number="settings.max_logs_per_request" type="number" min="100" max="10000" class="w-full rounded px-3 py-2" :style="inputStyle">
        </div>
        <div class="flex items-center justify-between">
          <div>
            <label class="block text-sm font-medium" :style="{ color: 'var(--color-text-secondary)' }">Auto-Discovery</label>
            <p class="text-xs" :style="{ color: 'var(--color-text-muted)' }">Neue Agents automatisch erstellen</p>
          </div>
          <label class="relative inline-flex items-center cursor-pointer">
            <input type="checkbox" v-model="settings.enable_auto_discovery" class="sr-only peer">
            <div class="w-11 h-6 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all" :style="{ backgroundColor: settings.enable_auto_discovery ? 'var(--color-primary)' : 'var(--color-surface-elevated)' }"></div>
          </label>
        </div>
        <button @click="saveAllSettings" :disabled="saving" class="w-full text-white py-2 rounded disabled:opacity-50 mt-4 hover:opacity-90" :style="{ backgroundColor: 'var(--color-primary)' }">
          {{ saving ? 'Speichere...' : '💾 Einstellungen speichern' }}
        </button>
        <p v-if="saveMessage" class="text-sm text-center" :style="{ color: saveError ? 'var(--color-danger)' : 'var(--color-success)' }">
          {{ saveMessage }}
        </p>
      </div>
    </div>

    <!-- Retention -->
    <div v-if="activeTab === 'retention'" class="rounded-lg shadow p-6" :style="cardStyle">
      <h2 class="text-lg font-semibold mb-4" :style="{ color: 'var(--color-text-primary)' }">Log Retention</h2>
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium mb-1" :style="{ color: 'var(--color-text-secondary)' }">Aufbewahrung (Tage)</label>
          <input v-model.number="retentionDays" type="number" min="1" class="w-full rounded px-3 py-2" :style="inputStyle">
          <p class="text-xs mt-1" :style="{ color: 'var(--color-text-muted)' }">Logs älter als diese Anzahl Tage werden bei Cleanup gelöscht</p>
        </div>
        <button @click="previewRetention" class="w-full py-2 rounded hover:opacity-80" :style="buttonSecondaryStyle">
          Vorschau anzeigen
        </button>
        <div v-if="retentionPreview" class="rounded p-4" :style="warningBoxStyle">
          <p class="font-medium" :style="{ color: 'var(--color-warning)' }">
            {{ retentionPreview.logs_to_delete.toLocaleString() }} Logs würden gelöscht
          </p>
          <p v-if="retentionPreview.oldest_log_date" class="text-sm mt-1" :style="{ color: 'var(--color-text-secondary)' }">
            Ältester Log: {{ formatDate(retentionPreview.oldest_log_date) }}
          </p>
        </div>
        <button
          @click="executeRetention"
          :disabled="!retentionPreview || retentionPreview.logs_to_delete === 0"
          class="w-full text-white py-2 rounded disabled:opacity-50 hover:opacity-90"
          :style="{ backgroundColor: 'var(--color-danger)' }"
        >
          Alte Logs löschen
        </button>
      </div>
      <div class="mt-6 pt-6 border-t" :style="{ borderColor: 'var(--color-border)' }">
        <h3 class="font-medium mb-4" :style="{ color: 'var(--color-danger)' }">Gefahrenzone</h3>
        <button
          @click="deleteAllLogs"
          class="w-full py-2 rounded hover:opacity-80 disabled:opacity-50"
          :disabled="deletingAllLogs"
          :style="dangerButtonStyle"
        >
          {{ deletingAllLogs ? 'Lösche alle Logs...' : 'ALARM: ALLE Logs löschen (TRUNCATE)' }}
        </button>
        <p v-if="deleteAllMessage" class="text-xs mt-2" :style="{ color: deleteAllError ? 'var(--color-danger)' : 'var(--color-success)' }">
          {{ deleteAllMessage }}
        </p>
        <button
          @click="compactLogs"
          class="w-full py-2 rounded hover:opacity-80 disabled:opacity-50 mt-3"
          :disabled="compactingLogs"
          :style="dangerButtonStyle"
        >
          {{ compactingLogs ? 'Komprimiere Logs...' : 'Speicher freigeben (VACUUM FULL)' }}
        </button>
        <p v-if="compactMessage" class="text-xs mt-2" :style="{ color: compactError ? 'var(--color-danger)' : 'var(--color-success)' }">
          {{ compactMessage }}
        </p>
        <p class="text-xs mt-2" :style="{ color: 'var(--color-danger)' }">Diese Aktion kann nicht rueckgaengig gemacht werden!</p>
      </div>
    </div>

    <!-- Agent Token -->
    <div v-if="activeTab === 'agents'" class="rounded-lg shadow p-6 mt-6" :style="cardStyle">
      <h2 class="text-lg font-semibold mb-4" :style="{ color: 'var(--color-text-primary)' }">Agent Token (global)</h2>
      <p class="text-sm mb-4" :style="{ color: 'var(--color-text-muted)' }">
        Ein Token für alle Agenten (Linux/Windows). Für höhere Sicherheit kannst du es bei Bedarf regenerieren.
      </p>

      <div v-if="tokenError" class="text-sm mb-2" :style="{ color: 'var(--color-danger)' }">{{ tokenError }}</div>
      <div v-if="tokenMessage" class="text-sm mb-2" :style="{ color: 'var(--color-success)' }">{{ tokenMessage }}</div>

      <div class="flex flex-col md:flex-row gap-3 items-start md:items-end">
        <div class="flex-1 w-full">
          <label class="block text-sm font-medium mb-1" :style="{ color: 'var(--color-text-secondary)' }">Token</label>
          <input :value="agentToken?.token || ''" readonly class="w-full rounded px-3 py-2 font-mono" :style="inputStyle">
          <p class="text-xs mt-1" :style="{ color: 'var(--color-text-muted)' }">
            Name: {{ agentToken?.name || 'global-agent' }}
          </p>
        </div>
        <div class="flex gap-2">
          <button
            class="px-3 py-2 rounded text-white hover:opacity-90"
            :style="{ backgroundColor: 'var(--color-primary)' }"
            :disabled="tokenLoading || !agentToken"
            @click="copyAgentToken"
          >
            Kopieren
          </button>
          <button
            class="px-3 py-2 rounded text-white hover:opacity-90"
            :style="{ backgroundColor: 'var(--color-danger)' }"
            :disabled="tokenLoading || !agentToken"
            @click="regenerateAgentToken"
          >
            {{ tokenLoading ? 'Regeneriere…' : 'Neu generieren' }}
          </button>
        </div>
      </div>
    </div>
    <!-- Netzwerk (Reverse Proxy + DNS, nur Admin) -->
    <div v-if="authStore.isAdmin && activeTab === 'network'" class="mt-6 space-y-4">
      <!-- Unter-Navigation -->
      <div class="flex flex-wrap gap-2">
        <button
          v-for="sub in networkSubTabs"
          :key="sub.id"
          class="px-3 py-2 rounded text-sm"
          :style="subTabButtonStyle(sub.id)"
          @click="networkSubTab = sub.id"
        >
          {{ sub.label }}
        </button>
      </div>

    <!-- Reverse Proxy & TLS (Caddy) -->
    <div v-if="networkSubTab === 'caddy'" class="rounded-lg shadow p-6" :style="cardStyle">
      <h2 class="text-lg font-semibold mb-2" :style="{ color: 'var(--color-text-primary)' }">Reverse Proxy & TLS (Caddy)</h2>
      <p class="text-sm mb-4" :style="{ color: 'var(--color-text-muted)' }">
        Caddyfile im Browser anpassen und sicher anwenden. Ungültige Config wird von Caddy abgelehnt – bei Fehler bleibt die alte aktiv.
      </p>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label class="block text-sm font-medium mb-1" :style="{ color: 'var(--color-text-secondary)' }">FQDN</label>
          <input
            v-model="caddyDomain"
            :disabled="caddyMode === 'http'"
            type="text"
            class="w-full rounded px-3 py-2"
            :style="{
              ...inputStyle,
              borderColor: caddyMode === 'http' ? inputStyle.borderColor : (isFqdnValid ? 'var(--color-success)' : 'var(--color-danger)')
            }"
            :placeholder="caddyMode === 'http' ? 'FQDN nur bei HTTPS' : 'logbot.example.com'">
          <div class="mt-3 space-y-2 text-sm" :style="{ color: 'var(--color-text-secondary)' }">
            <label class="flex items-center gap-2 cursor-pointer">
              <input type="radio" value="http" v-model="caddyMode">
              <span>Nur HTTP (Port 80, ohne FQDN)</span>
            </label>
            <label class="flex items-center gap-2 cursor-pointer">
              <input type="radio" value="letsencrypt" v-model="caddyMode">
              <span>HTTPS via Let's Encrypt (Auto-Zertifikat)</span>
            </label>
            <label class="flex items-center gap-2 cursor-pointer">
              <input type="radio" value="custom" v-model="caddyMode">
              <span>HTTPS mit eigenem Zertifikat</span>
            </label>
          </div>
          <div v-if="caddyMode === 'letsencrypt'" class="mt-3">
            <label class="block text-sm font-medium mb-1" :style="{ color: 'var(--color-text-secondary)' }">E-Mail für Let's Encrypt</label>
            <input v-model="caddyEmail" type="email" class="w-full rounded px-3 py-2" :style="inputStyle" placeholder="admin@example.com">
          </div>
        </div>
        <div>
          <label class="block text-sm font-medium mb-1" :style="{ color: 'var(--color-text-secondary)' }">Zertifikat (.crt / fullchain)</label>
          <input type="file" accept=".crt,.pem" class="w-full text-sm" @change="e => certUpload.cert = e.target.files?.[0] || null">
          <label class="block text-sm font-medium mt-3 mb-1" :style="{ color: 'var(--color-text-secondary)' }">Private Key (.key)</label>
          <input type="file" accept=".key,.pem" class="w-full text-sm" @change="e => certUpload.key = e.target.files?.[0] || null">
          <p class="text-xs mt-2" :style="{ color: caddyCertPresent ? 'var(--color-success)' : 'var(--color-text-muted)' }">
            {{ caddyCertPresent ? 'Zertifikat vorhanden' : 'Noch kein Zertifikat gespeichert' }}
          </p>
          <p class="text-xs" :style="{ color: 'var(--color-text-muted)' }">
            Hinweis: Lade am besten die Fullchain (Leaf + Intermediate) als .crt hoch; Root wird nicht benötigt.
          </p>
          <button
            class="mt-3 px-3 py-2 rounded text-white hover:opacity-90 disabled:opacity-50"
            :style="{ backgroundColor: 'var(--color-primary)' }"
            @click="uploadCaddyCert"
            :disabled="caddyLoading"
          >
            Zertifikat speichern
          </button>
          <p v-if="caddyMode !== 'custom'" class="text-xs mt-2" :style="{ color: 'var(--color-text-muted)' }">
            Hinweis: Custom Cert wird nur genutzt, wenn der Modus „Eigenes Zertifikat“ aktiviert ist.
          </p>
        </div>
      </div>

      <div class="flex flex-col md:flex-row gap-3 mt-4">
        <button
          class="px-3 py-2 rounded hover:opacity-90"
          :style="buttonSecondaryStyle"
          @click="buildCaddyTemplate"
          :disabled="caddyLoading"
        >
          Template erzeugen
        </button>
        <button
          class="px-3 py-2 rounded text-white hover:opacity-90 disabled:opacity-50"
          :style="{ backgroundColor: 'var(--color-primary)' }"
          @click="applyCaddy"
          :disabled="caddyLoading"
        >
          {{ caddyLoading ? 'Wird angewendet...' : 'Apply & Reload' }}
        </button>
      </div>

      <textarea
        v-model="caddyfile"
        class="w-full mt-4 rounded px-3 py-2 font-mono text-sm"
        rows="12"
        :style="inputStyle"
        placeholder="Caddyfile"
      ></textarea>

      <p v-if="caddyMessage" class="text-sm mt-2" :style="{ color: 'var(--color-success)' }">{{ caddyMessage }}</p>
        <p v-if="caddyError" class="text-sm mt-2" :style="{ color: 'var(--color-danger)' }">{{ caddyError }}</p>
        <div v-if="showHttpHint" class="mt-3 p-3 rounded" :style="warningBoxStyle">
          <p class="text-sm" :style="{ color: 'var(--color-text-primary)' }">
            HTTP-Modus aktiv. Öffne&nbsp;
            <a :href="httpLink" target="_blank" rel="noopener" class="underline">{{ httpLink }}</a>
            &nbsp;in einem neuen Tab.
          </p>
          <div class="flex items-center gap-2 mt-2">
            <button
              class="text-sm px-3 py-1 rounded"
              :style="buttonSecondaryStyle"
              @click="copyHttpLink"
            >
              Link kopieren
            </button>
            <span v-if="httpCopyMessage" class="text-xs" :style="{ color: 'var(--color-success)' }">
              {{ httpCopyMessage }}
            </span>
          </div>
          <p class="text-xs mt-2" :style="{ color: 'var(--color-text-muted)' }">
            Hinweis: Stelle sicher, dass Port 80 erreichbar ist. Wenn nicht, bleibt HTTPS bis zum nächsten Apply aktiv.
          </p>
        </div>
      </div>

      <!-- DNS -->
      <div v-if="networkSubTab === 'dns'" class="rounded-lg shadow p-6" :style="cardStyle">
        <h2 class="text-lg font-semibold mb-2" :style="{ color: 'var(--color-text-primary)' }">DNS</h2>
        <p class="text-sm mb-4" :style="{ color: 'var(--color-text-muted)' }">
          Standardmäßig wird der im Netzwerk per DHCP vergebene DNS verwendet. Alternativ kannst du eigene DNS-Server hinterlegen.
        </p>

        <div v-if="dnsError" class="text-sm mb-2" :style="{ color: 'var(--color-danger)' }">{{ dnsError }}</div>
        <div v-if="dnsMessage" class="text-sm mb-2" :style="{ color: 'var(--color-success)' }">{{ dnsMessage }}</div>

        <div class="space-y-2 text-sm" :style="{ color: 'var(--color-text-secondary)' }">
          <label class="flex items-center gap-2 cursor-pointer">
            <input type="radio" value="dhcp" v-model="dnsMode">
            <span>Automatisch (per DHCP vergebener DNS)</span>
          </label>
          <label class="flex items-center gap-2 cursor-pointer">
            <input type="radio" value="manual" v-model="dnsMode">
            <span>Manuell (eigene DNS-Server)</span>
          </label>
        </div>

        <div class="mt-4">
          <label class="block text-sm font-medium mb-1" :style="{ color: 'var(--color-text-secondary)' }">Erkannte System-DNS (DHCP)</label>
          <p class="text-sm font-mono" :style="{ color: 'var(--color-text-primary)' }">
            {{ dnsDetected.length ? dnsDetected.join(', ') : 'Keine erkannt' }}
          </p>
        </div>

        <div v-if="dnsMode === 'manual'" class="mt-4">
          <label class="block text-sm font-medium mb-1" :style="{ color: 'var(--color-text-secondary)' }">DNS-Server</label>
          <div v-for="(srv, idx) in dnsServers" :key="idx" class="flex items-center gap-2 mb-2">
            <input v-model="dnsServers[idx]" type="text" class="flex-1 rounded px-3 py-2" :style="inputStyle" placeholder="z.B. 192.168.179.30">
            <button class="px-3 py-2 rounded hover:opacity-80" :style="buttonSecondaryStyle" @click="dnsServers.splice(idx, 1)">Entfernen</button>
          </div>
          <button class="px-3 py-2 rounded hover:opacity-80" :style="buttonSecondaryStyle" @click="dnsServers.push('')">+ Server hinzufügen</button>

          <label class="block text-sm font-medium mt-4 mb-1" :style="{ color: 'var(--color-text-secondary)' }">Such-Domains (optional)</label>
          <input v-model="dnsSearchInput" type="text" class="w-full rounded px-3 py-2" :style="inputStyle" placeholder="z.B. phytech.de intern.lan (Leerzeichen-getrennt)">
        </div>

        <div class="mt-4">
          <label class="block text-sm font-medium mb-1" :style="{ color: 'var(--color-text-secondary)' }">Aktuell aktive Nameserver (Container)</label>
          <p class="text-sm font-mono" :style="{ color: 'var(--color-text-primary)' }">
            {{ dnsActive.length ? dnsActive.join(', ') : '-' }}
          </p>
        </div>

        <div class="flex flex-col md:flex-row gap-3 mt-4">
          <button
            class="px-3 py-2 rounded text-white hover:opacity-90 disabled:opacity-50"
            :style="{ backgroundColor: 'var(--color-primary)' }"
            @click="applyDns"
            :disabled="dnsLoading"
          >
            {{ dnsLoading ? 'Wird angewendet...' : 'Anwenden' }}
          </button>
        </div>

        <div class="mt-6 pt-4 border-t" :style="{ borderColor: 'var(--color-border)' }">
          <label class="block text-sm font-medium mb-1" :style="{ color: 'var(--color-text-secondary)' }">Auflösung testen</label>
          <div class="flex items-center gap-2">
            <input v-model="dnsTestHost" type="text" class="flex-1 rounded px-3 py-2" :style="inputStyle" placeholder="logbot.example.com">
            <button
              class="px-3 py-2 rounded hover:opacity-80 disabled:opacity-50"
              :style="buttonSecondaryStyle"
              @click="testDns"
              :disabled="dnsTesting"
            >
              {{ dnsTesting ? 'Teste…' : 'Testen' }}
            </button>
          </div>
          <p v-if="dnsTestResult" class="text-sm mt-2" :style="{ color: dnsTestResult.resolved ? 'var(--color-success)' : 'var(--color-danger)' }">
            {{ dnsTestResult.resolved ? ('OK: ' + (dnsTestResult.addresses || []).join(', ')) : ('Fehler: ' + (dnsTestResult.error || 'nicht auflösbar')) }}
          </p>
        </div>
      </div>
    </div>
    <!-- /Netzwerk -->

    <!-- Datenbank (nur Admin) -->
    <div v-if="authStore.isAdmin && activeTab === 'database'" class="rounded-lg shadow p-6 mt-6" :style="cardStyle">
      <h2 class="text-lg font-semibold mb-4" :style="{ color: 'var(--color-text-primary)' }">Datenbank</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <div>
          <p class="text-xs" :style="{ color: 'var(--color-text-muted)' }">Host</p>
          <p :style="{ color: 'var(--color-text-primary)' }">{{ dbSettings?.host || '-' }}</p>
        </div>
        <div>
          <p class="text-xs" :style="{ color: 'var(--color-text-muted)' }">Port</p>
          <p :style="{ color: 'var(--color-text-primary)' }">{{ dbSettings?.port || '-' }}</p>
        </div>
        <div>
          <p class="text-xs" :style="{ color: 'var(--color-text-muted)' }">Benutzer</p>
          <p :style="{ color: 'var(--color-text-primary)' }">{{ dbSettings?.user || '-' }}</p>
        </div>
        <div>
          <p class="text-xs" :style="{ color: 'var(--color-text-muted)' }">Datenbank</p>
          <p :style="{ color: 'var(--color-text-primary)' }">{{ dbSettings?.name || '-' }}</p>
        </div>
      </div>
      <div>
        <label class="block text-sm font-medium mb-1" :style="{ color: 'var(--color-text-secondary)' }">Passwort</label>
        <div class="flex items-center gap-2">
          <input
            :type="showDbPassword ? 'text' : 'password'"
            :value="dbSettings?.password || ''"
            readonly
            class="w-full rounded px-3 py-2"
            :style="inputStyle"
          >
          <button
            type="button"
            class="px-3 py-2 rounded hover:opacity-80"
            :style="buttonSecondaryStyle"
            @click="showDbPassword = !showDbPassword"
            :disabled="!dbSettings"
          >
            {{ showDbPassword ? 'Verbergen' : 'Anzeigen' }}
          </button>
          <button
            type="button"
            class="px-3 py-2 rounded hover:opacity-80"
            :style="buttonSecondaryStyle"
            @click="copyDbPassword"
            :disabled="!dbSettings?.password"
          >
            Kopieren
          </button>
        </div>
        <p v-if="dbCopyMessage" class="text-xs mt-1" :style="{ color: 'var(--color-text-muted)' }">{{ dbCopyMessage }}</p>
        <p v-if="dbError" class="text-sm mt-2" :style="{ color: 'var(--color-danger)' }">{{ dbError }}</p>
      </div>
    </div>
    
    <!-- System (nur Admin) -->
    <div v-if="authStore.isAdmin && activeTab === 'system'" class="rounded-lg shadow p-6 mt-6" :style="cardStyle">
      <h2 class="text-lg font-semibold mb-4" :style="{ color: 'var(--color-text-primary)' }">System</h2>
      <p class="text-sm mb-4" :style="{ color: 'var(--color-text-secondary)' }">
        Startet das Betriebssystem neu. Aktive Nutzer werden getrennt.
      </p>
      <button
        @click="rebootSystem"
        :disabled="rebooting"
        class="w-full text-white py-2 rounded disabled:opacity-50 hover:opacity-90"
        :style="{ backgroundColor: 'var(--color-danger)' }"
      >
        {{ rebooting ? 'Neustart wird ausgelöst...' : 'System neu starten' }}
      </button>
      <p v-if="rebootMessage" class="text-xs mt-2" :style="{ color: rebootError ? 'var(--color-danger)' : 'var(--color-success)' }">
        {{ rebootMessage }}
      </p>
    </div>
    
    <!-- Passwort ändern -->
    <div v-if="activeTab === 'password'" class="rounded-lg shadow p-6 mt-6" :style="cardStyle">
      <h2 class="text-lg font-semibold mb-4" :style="{ color: 'var(--color-text-primary)' }">Passwort ändern</h2>
      <form @submit.prevent="changePassword" class="max-w-md space-y-4">
        <div>
          <label class="block text-sm font-medium mb-1" :style="{ color: 'var(--color-text-secondary)' }">Neues Passwort</label>
          <input v-model="newPassword" type="password" required minlength="6" class="w-full rounded px-3 py-2" :style="inputStyle">
        </div>
        <div>
          <label class="block text-sm font-medium mb-1" :style="{ color: 'var(--color-text-secondary)' }">Passwort bestätigen</label>
          <input v-model="confirmPassword" type="password" required minlength="6" class="w-full rounded px-3 py-2" :style="inputStyle">
        </div>
        <button type="submit" class="text-white px-4 py-2 rounded hover:opacity-90" :style="{ backgroundColor: 'var(--color-primary)' }">
          Passwort ändern
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()

const tabs = [
  { id: 'general', label: 'Allgemein' },
  { id: 'retention', label: 'Retention' },
  { id: 'agents', label: 'Agent Token' },
  { id: 'network', label: 'Netzwerk', adminOnly: true },
  { id: 'database', label: 'Datenbank', adminOnly: true },
  { id: 'system', label: 'System', adminOnly: true },
  { id: 'password', label: 'Passwort' }
]
const activeTab = ref('general')
const tabLoaded = ref({ network: false, database: false })
const networkSubTabs = [
  { id: 'caddy', label: 'Reverse Proxy' },
  { id: 'dns', label: 'DNS' }
]
const networkSubTab = ref('caddy')

const settings = ref({
  app_name: 'LogBot',
  timezone: 'Europe/Berlin',
  agent_offline_timeout: 300,
  max_logs_per_request: 1000,
  enable_auto_discovery: true
})

const retentionDays = ref(90)
const retentionPreview = ref(null)
const newPassword = ref('')
const confirmPassword = ref('')
const dbSettings = ref(null)
const dbError = ref('')
const dbCopyMessage = ref('')
const showDbPassword = ref(false)
// Agent Token (Single)
const agentToken = ref(null)
const tokenMessage = ref('')
const tokenError = ref('')
const tokenLoading = ref(false)
const saving = ref(false)
const saveMessage = ref('')
const saveError = ref(false)
const deletingAllLogs = ref(false)
const deleteAllMessage = ref('')
const deleteAllError = ref(false)
const compactingLogs = ref(false)
const compactMessage = ref('')
const compactError = ref(false)
const rebooting = ref(false)
const rebootMessage = ref('')
const rebootError = ref(false)
// Caddy / Reverse Proxy
const caddyLoading = ref(false)
const caddyMessage = ref('')
const caddyError = ref('')
const caddyfile = ref('')
const caddyDomain = ref('logbot.example.com')
const caddyMode = ref('custom') // 'http' | 'letsencrypt' | 'custom'
const caddyEmail = ref('')
const caddyCertPresent = ref(false)
const showHttpHint = ref(false)
const httpLink = ref('')
const httpCopyMessage = ref('')
// DNS
const dnsMode = ref('dhcp')
const dnsServers = ref([''])
const dnsSearchInput = ref('')
const dnsDetected = ref([])
const dnsActive = ref([])
const dnsLoading = ref(false)
const dnsMessage = ref('')
const dnsError = ref('')
const dnsTestHost = ref('')
const dnsTesting = ref(false)
const dnsTestResult = ref(null)
let certUpload = { cert: null, key: null }
const httpTemplate = `{
    admin 0.0.0.0:2019
}

:80 {
    handle /api/* {
        reverse_proxy backend:8000
    }

    handle {
        reverse_proxy frontend:80
    }

    log {
        output stdout
    }
}
`

const availableTabs = computed(() => tabs.filter(t => !t.adminOnly || authStore.isAdmin))

const tlsHint = computed(() => {
  if (caddyMode.value === 'http') return 'Nur HTTP (Port 80). Kein Zertifikat nötig.'
  if (caddyMode.value === 'letsencrypt') return 'Let’s Encrypt besorgt das Zertifikat automatisch (FQDN + 80/443 öffentlich erreichbar, E-Mail erforderlich).'
  return caddyCertPresent.value
    ? 'Eigenes Zertifikat gefunden. Wird für HTTPS genutzt.'
    : 'Eigenes Zertifikat wählen und speichern, dann Apply.'
})
const fqdnRegex = /^[A-Za-z0-9]([-A-Za-z0-9]*\.)+[A-Za-z]{2,}$/
const isFqdnValid = computed(() => {
  if (caddyMode.value === 'http') return true
  const d = (caddyDomain.value || '').trim()
  return fqdnRegex.test(d)
})

// Automatisch auf sicheres Template umschalten, wenn der Modus gewechselt wird
watch(caddyMode, async (mode) => {
  // FQDN ist für HTTPS erforderlich, bei HTTP bewusst leer halten
  if (mode === 'http') {
    caddyDomain.value = ''
    caddyEmail.value = ''
    showHttpHint.value = false
    httpLink.value = ''
    httpCopyMessage.value = ''
    // Lokales HTTP-Template setzen, damit kein alter FQDN bleibt
    caddyfile.value = httpTemplate
  } else {
    // falls noch keine Caddyfile geladen wurde, baue eine erste Vorlage
    if (!caddyfile.value) {
      await buildCaddyTemplate()
    }
  }
})

// Wenn im HTTPS-Modus der FQDN geändert wird, Template automatisch aktualisieren
watch(caddyDomain, async (val) => {
  if (caddyMode.value !== 'http' && val) {
    await buildCaddyTemplate()
  }
})

// Computed Styles
const cardStyle = computed(() => ({
  backgroundColor: 'var(--color-surface)',
  borderColor: 'var(--color-border)'
}))

const inputStyle = computed(() => ({
  backgroundColor: 'var(--color-surface-elevated)',
  borderColor: 'var(--color-border)',
  color: 'var(--color-text-primary)',
  border: '1px solid var(--color-border)'
}))

const buttonSecondaryStyle = computed(() => ({
  backgroundColor: 'var(--color-surface-elevated)',
  color: 'var(--color-text-primary)',
  border: '1px solid var(--color-border)'
}))

const warningBoxStyle = computed(() => ({
  backgroundColor: 'var(--color-surface-elevated)',
  border: '1px solid var(--color-warning)'
}))

const dangerButtonStyle = computed(() => ({
  backgroundColor: 'var(--color-surface-elevated)',
  color: 'var(--color-danger)',
  border: '1px solid var(--color-danger)'
}))

onMounted(async () => {
  try {
    const data = await authStore.api('/api/settings')
    settings.value = { ...settings.value, ...data.settings }
    if (data.settings.log_retention_days) {
      retentionDays.value = data.settings.log_retention_days
    }
    if (authStore.isAdmin) {
      // lazy: nur laden, wenn Tab geöffnet wird
    }
    await loadAgentToken()
  } catch (e) {
    console.error('Fehler:', e)
  }
})

function tabButtonStyle(id) {
  const isActive = activeTab.value === id
  return {
    backgroundColor: isActive ? 'var(--color-primary)' : 'var(--color-surface-elevated)',
    color: isActive ? '#fff' : 'var(--color-text-primary)',
    border: '1px solid var(--color-border)'
  }
}

function subTabButtonStyle(id) {
  const isActive = networkSubTab.value === id
  return {
    backgroundColor: isActive ? 'var(--color-primary)' : 'var(--color-surface-elevated)',
    color: isActive ? '#fff' : 'var(--color-text-primary)',
    border: '1px solid var(--color-border)'
  }
}

async function setTab(id) {
  activeTab.value = id
  if (id === 'database' && authStore.isAdmin && !tabLoaded.value.database) {
    await loadDatabaseSettings()
    tabLoaded.value.database = true
  }
  if (id === 'network' && authStore.isAdmin && !tabLoaded.value.network) {
    await loadCaddyConfig()
    await loadDnsConfig()
    tabLoaded.value.network = true
  }
}

async function loadDatabaseSettings() {
  dbError.value = ''
  try {
    dbSettings.value = await authStore.api('/api/settings/database')
  } catch (e) {
    dbError.value = e.message
  }
}

async function loadAgentToken() {
  tokenLoading.value = true
  tokenError.value = ''
  tokenMessage.value = ''
  try {
    let list = await authStore.api('/api/agent-tokens')
    if (!Array.isArray(list)) list = []
    const preferred = list.find(t => t.name === 'global-agent')
    if (!preferred) {
      const created = await authStore.api('/api/agent-tokens', {
        method: 'POST',
        body: { name: 'global-agent' }
      })
      agentToken.value = created
      tokenMessage.value = 'Standard-Token erstellt'
    } else {
      agentToken.value = preferred
    }
  } catch (e) {
    tokenError.value = e.message || 'Token laden fehlgeschlagen'
  } finally {
    tokenLoading.value = false
  }
}

async function loadCaddyConfig() {
  caddyLoading.value = true
  caddyError.value = ''
  caddyMessage.value = ''
  try {
    const res = await authStore.api('/api/caddy/config')
    caddyfile.value = res.saved_caddyfile || ''
    caddyCertPresent.value = !!res.cert_present
  } catch (e) {
    caddyError.value = e.message || 'Caddy-Konfiguration konnte nicht geladen werden'
  } finally {
    caddyLoading.value = false
  }
}

async function loadDnsConfig() {
  dnsError.value = ''
  try {
    const res = await authStore.api('/api/network/dns')
    dnsMode.value = res.mode || 'dhcp'
    dnsServers.value = (res.configured && res.configured.length) ? [...res.configured] : ['']
    dnsSearchInput.value = (res.search_domains || []).join(' ')
    dnsDetected.value = res.detected || []
    dnsActive.value = res.active || []
    if (!dnsTestHost.value) dnsTestHost.value = caddyDomain.value || ''
  } catch (e) {
    dnsError.value = e.message || 'DNS-Konfiguration konnte nicht geladen werden'
  }
}

async function applyDns() {
  dnsLoading.value = true
  dnsError.value = ''
  dnsMessage.value = ''
  try {
    const servers = dnsMode.value === 'manual'
      ? dnsServers.value.map(s => s.trim()).filter(Boolean)
      : []
    const search = dnsSearchInput.value.split(/\s+/).map(s => s.trim()).filter(Boolean)
    const res = await authStore.api('/api/network/dns', {
      method: 'PUT',
      body: { mode: dnsMode.value, servers, search_domains: search }
    })
    dnsDetected.value = res.detected || []
    dnsActive.value = res.active || []
    dnsMessage.value = 'DNS angewendet.'
  } catch (e) {
    dnsError.value = e.message || 'DNS konnte nicht angewendet werden'
  } finally {
    dnsLoading.value = false
  }
}

async function testDns() {
  if (!dnsTestHost.value) return
  dnsTesting.value = true
  dnsTestResult.value = null
  try {
    dnsTestResult.value = await authStore.api('/api/network/dns/test', {
      method: 'POST',
      body: { host: dnsTestHost.value.trim() }
    })
  } catch (e) {
    dnsTestResult.value = { resolved: false, error: e.message }
  } finally {
    dnsTesting.value = false
  }
}

async function buildCaddyTemplate() {
  caddyError.value = ''
  if (caddyMode.value !== 'http' && !isFqdnValid.value) {
    caddyError.value = 'FQDN ist ungültig (z.B. logbot.example.com).'
    return
  }
  // HTTP-Modus: kein API-Call nötig, lokales Template einsetzen
  if (caddyMode.value === 'http') {
    caddyfile.value = httpTemplate
    caddyMessage.value = 'HTTP-Template geladen (nur :80, kein Redirect).'
    return
  }
  try {
    const domainToSend = caddyMode.value === 'http' ? null : caddyDomain.value
    const res = await authStore.api('/api/caddy/template', {
      method: 'POST',
      body: {
        domain: domainToSend,
        mode: caddyMode.value,
        letsencrypt_email: caddyMode.value === 'letsencrypt' ? caddyEmail.value : null
      }
    })
    caddyfile.value = res.caddyfile
    caddyMessage.value = 'Template eingefügt. Prüfe & passe nach Bedarf an.'
  } catch (e) {
    caddyError.value = e.message
  }
}

async function uploadCaddyCert() {
  if (!certUpload.cert || !certUpload.key) {
    caddyError.value = 'Bitte Zertifikat UND Key auswählen.'
    return
  }
  caddyError.value = ''
  caddyMessage.value = ''
  const form = new FormData()
  form.append('cert_file', certUpload.cert)
  form.append('key_file', certUpload.key)
  try {
    await authStore.api('/api/caddy/certificates', {
      method: 'POST',
      body: form
    })
    caddyCertPresent.value = true
    caddyMessage.value = 'Zertifikat gespeichert.'
  } catch (e) {
    caddyError.value = e.message
  }
}

async function applyCaddy() {
  if (caddyMode.value !== 'http' && !caddyDomain.value) {
    caddyError.value = 'FQDN ist für HTTPS erforderlich.'
    return
  }
  if (caddyMode.value !== 'http' && !isFqdnValid.value) {
    caddyError.value = 'FQDN ist ungültig (z.B. logbot.example.com).'
    return
  }
  if (caddyMode.value === 'letsencrypt' && !caddyEmail.value) {
    caddyError.value = 'E-Mail für Let\'s Encrypt fehlt.'
    return
  }
  if (caddyMode.value === 'custom' && !caddyCertPresent.value) {
    caddyError.value = 'Custom-Zertifikat hochladen, bevor du es aktivierst.'
    return
  }
  // Stelle sicher, dass im HTTP-Modus die Caddyfile keine alten FQDNs enthält
  if (caddyMode.value === 'http') {
    caddyfile.value = httpTemplate
  }
  if (!confirm('Apply & Reload Caddy jetzt ausführen?')) return

  caddyLoading.value = true
  caddyError.value = ''
  caddyMessage.value = ''
  try {
    await authStore.api('/api/caddy/apply', {
      method: 'POST',
      body: {
        caddyfile: caddyfile.value,
        save: true,
        mode: caddyMode.value,
        domain: caddyMode.value === 'http' ? null : caddyDomain.value,
        letsencrypt_email: caddyMode.value === 'letsencrypt' ? caddyEmail.value : null
      }
    })
    caddyMessage.value = 'Caddy neu geladen. Bei Fehler bleibt die alte Konfiguration aktiv.'
    if (caddyMode.value === 'http') {
      // Im HTTP-Modus muss der Benutzer wirklich auf HTTP landen, sonst schlagen alle API-Calls über HTTPS fehl.
      const currentPort = window.location.port
      const targetPort = !currentPort || currentPort === '443' ? '80' : currentPort
      const target = `http://${window.location.hostname}${targetPort === '80' ? '' : ':' + targetPort}/settings`

      httpLink.value = target
      showHttpHint.value = true
      // Versuch, URL zu kopieren – hilfreich, wenn Popups unterbunden sind
      try {
        await navigator.clipboard.writeText(target)
        caddyMessage.value = `HTTP-Modus aktiv. Öffne ${target} in einem neuen Tab (URL kopiert).`
        httpCopyMessage.value = 'Link kopiert'
      } catch (copyErr) {
        console.warn('Kopieren HTTP-Link fehlgeschlagen:', copyErr)
        caddyMessage.value = `HTTP-Modus aktiv. Bitte öffne ${target} manuell in einem neuen Tab.`
        httpCopyMessage.value = ''
      }
      // Öffne zusätzlich in neuem Tab (falls geblockt, bleibt die aktuelle Seite, Redirect folgt darunter)
      window.open(target, '_blank')
      // Harte Weiterleitung nach kurzem Delay, damit der User nicht im toten HTTPS-Kontext bleibt
      setTimeout(() => { window.location.href = target }, 500)
      return
    }
  } catch (e) {
    caddyError.value = e.message
  } finally {
    caddyLoading.value = false
  }
}

async function copyDbPassword() {
  if (!dbSettings.value?.password) return
  await navigator.clipboard.writeText(dbSettings.value.password)
  dbCopyMessage.value = 'Passwort kopiert'
  setTimeout(() => { dbCopyMessage.value = '' }, 2000)
}

async function regenerateAgentToken() {
  if (!agentToken.value) return
  if (!confirm(`Agent-Token "${agentToken.value.name}" regenerieren?`)) return
  tokenLoading.value = true
  tokenMessage.value = ''
  tokenError.value = ''
  try {
    const updated = await authStore.api(`/api/agent-tokens/${agentToken.value.id}/regenerate`, { method: 'POST' })
    agentToken.value = updated
    tokenMessage.value = 'Token regeneriert'
  } catch (e) {
    tokenError.value = e.message || 'Fehler beim Regenerieren'
  } finally {
    tokenLoading.value = false
  }
}

async function copyAgentToken() {
  if (!agentToken.value?.token) return
  try {
    await navigator.clipboard.writeText(agentToken.value.token)
    tokenMessage.value = 'Token kopiert'
    tokenError.value = ''
  } catch (e) {
    tokenError.value = 'Kopieren fehlgeschlagen'
  }
}

async function saveAllSettings() {
  saving.value = true
  saveMessage.value = ''
  saveError.value = false
  
  try {
    const settingsToSave = [
      ['app_name', settings.value.app_name],
      ['timezone', settings.value.timezone],
      ['agent_offline_timeout', settings.value.agent_offline_timeout],
      ['max_logs_per_request', settings.value.max_logs_per_request],
      ['enable_auto_discovery', settings.value.enable_auto_discovery],
      ['log_retention_days', retentionDays.value]
    ]
    
    for (const [key, value] of settingsToSave) {
      await authStore.api(`/api/settings/${key}`, {
        method: 'PUT',
        body: { value }
      })
    }
    
    saveMessage.value = 'âœ“ Einstellungen gespeichert!'
    setTimeout(() => { saveMessage.value = '' }, 3000)
  } catch (e) {
    saveError.value = true
    saveMessage.value = 'Fehler: ' + e.message
  } finally {
    saving.value = false
  }
}

async function previewRetention() {
  try {
    retentionPreview.value = await authStore.api(`/api/settings/retention/preview?days=${retentionDays.value}`, {
      method: 'POST'
    })
  } catch (e) {
    alert('Fehler: ' + e.message)
  }
}

async function executeRetention() {
  if (!confirm(`Wirklich ${retentionPreview.value.logs_to_delete.toLocaleString()} Logs löschen?`)) return
  
  try {
    const result = await authStore.api(`/api/settings/retention/execute?days=${retentionDays.value}`, {
      method: 'POST'
    })
    alert(result.message)
    retentionPreview.value = null
  } catch (e) {
    alert('Fehler: ' + e.message)
  }
}

async function deleteAllLogs() {
  const confirm1 = prompt('Diese Aktion löscht ALLE Logs! Geben Sie "DELETE_ALL_LOGS" ein, um zu bestätigen:')
  if (confirm1 !== 'DELETE_ALL_LOGS') return
  
  deletingAllLogs.value = true
  deleteAllMessage.value = ''
  deleteAllError.value = false
  try {
    const result = await authStore.api('/api/settings/logs/all?confirm=DELETE_ALL_LOGS', {
      method: 'DELETE'
    })
    deleteAllMessage.value = result?.message || 'Alle Logs wurden gelöscht.'
  } catch (e) {
    deleteAllError.value = true
    deleteAllMessage.value = 'Fehler: ' + e.message
  }
  deletingAllLogs.value = false
}

async function compactLogs() {
  const confirm1 = prompt('VACUUM FULL sperrt die Tabelle kurz. Geben Sie "COMPACT_LOGS" ein, um zu bestätigen:')
  if (confirm1 !== 'COMPACT_LOGS') return

  compactingLogs.value = true
  compactMessage.value = ''
  compactError.value = false
  try {
    const result = await authStore.api('/api/settings/logs/compact?confirm=COMPACT_LOGS', {
      method: 'POST'
    })
    compactMessage.value = result?.message || 'VACUUM FULL abgeschlossen.'
  } catch (e) {
    compactError.value = true
    compactMessage.value = 'Fehler: ' + e.message
  }
  compactingLogs.value = false
}

async function rebootSystem() {
  if (!confirm('System jetzt neu starten? Alle Benutzer werden getrennt.')) return
  
  rebooting.value = true
  rebootMessage.value = ''
  rebootError.value = false
  
  try {
    const result = await authStore.api('/api/settings/reboot', { method: 'POST' })
    rebootMessage.value = result?.message || 'Neustart ausgelöst.'
  } catch (e) {
    rebootError.value = true
    rebootMessage.value = 'Fehler: ' + e.message
  } finally {
    rebooting.value = false
  }
}

async function changePassword() {
  if (newPassword.value !== confirmPassword.value) {
    alert('Passwörter stimmen nicht überein!')
    return
  }
  
  try {
    await authStore.api(`/api/users/${authStore.user.id}`, {
      method: 'PUT',
      body: { password: newPassword.value }
    })
    alert('Passwort geändert!')
    newPassword.value = ''
    confirmPassword.value = ''
  } catch (e) {
    alert('Fehler: ' + e.message)
  }
}

function formatDate(timestamp) {
  if (!timestamp) return '-'
  return new Date(timestamp).toLocaleString('de-DE')
}

async function copyHttpLink() {
  if (!httpLink.value) return
  try {
    await navigator.clipboard.writeText(httpLink.value)
    httpCopyMessage.value = 'Link kopiert'
    setTimeout(() => { httpCopyMessage.value = '' }, 2000)
  } catch (e) {
    httpCopyMessage.value = 'Kopieren fehlgeschlagen'
    setTimeout(() => { httpCopyMessage.value = '' }, 2000)
  }
}
</script>

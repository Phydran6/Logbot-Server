<!-- ==============================================================================
     Name:        Philipp Fischer
     Kontakt:     p.fischer@itconex.de
     Version:     2026.04.05
     Beschreibung: LogBot - Datenschutzerklärung (DSGVO)
     ============================================================================== -->

<template>
  <div class="min-h-screen py-12 px-4" :style="{ backgroundColor: 'var(--color-bg)' }">
    <div class="max-w-3xl mx-auto rounded-lg p-8" :style="{ backgroundColor: 'var(--color-surface)', color: 'var(--color-text-primary)' }">

      <div class="flex items-center gap-3 mb-8">
        <router-link to="/login" class="text-sm px-3 py-1 rounded" :style="{ backgroundColor: 'var(--color-surface-elevated)', color: 'var(--color-text-secondary)' }">
          ← Zurück
        </router-link>
        <h1 class="text-2xl font-bold">Datenschutzerklärung</h1>
      </div>

      <section class="mb-6">
        <h2 class="text-lg font-semibold mb-2">1. Datenschutz auf einen Blick</h2>
        <h3 class="font-medium mb-1">Allgemeine Hinweise</h3>
        <p class="text-sm mb-4" :style="{ color: 'var(--color-text-muted)' }">
          Die folgenden Hinweise geben einen einfachen Überblick darüber, was mit Ihren personenbezogenen Daten
          passiert, wenn Sie diese Anwendung nutzen. Personenbezogene Daten sind alle Daten, mit denen Sie
          persönlich identifiziert werden können. Ausführliche Informationen zum Thema Datenschutz entnehmen
          Sie unserer unter diesem Text aufgeführten Datenschutzerklärung.
        </p>

        <h3 class="font-medium mb-1">Datenerfassung in dieser Anwendung</h3>
        <p class="text-sm mb-2" :style="{ color: 'var(--color-text-muted)' }">
          <strong>Wer ist verantwortlich für die Datenerfassung?</strong><br>
          Die Datenverarbeitung in dieser Anwendung erfolgt durch den Betreiber. Dessen Kontaktdaten
          können Sie dem Impressum dieser Anwendung entnehmen.
        </p>
        <p class="text-sm mb-2" :style="{ color: 'var(--color-text-muted)' }">
          <strong>Wie erfassen wir Ihre Daten?</strong><br>
          Ihre Daten werden zum einen dadurch erhoben, dass Sie uns diese mitteilen. Hierbei kann es
          sich z. B. um Daten handeln, die Sie in ein Anmeldeformular eingeben. Andere Daten werden
          automatisch beim Nutzen der Anwendung durch unsere IT-Systeme erfasst. Das sind vor allem
          technische Daten (z. B. Internetbrowser, Betriebssystem oder Uhrzeit des Seitenaufrufs).
          Die Erfassung dieser Daten erfolgt automatisch, sobald Sie die Anwendung nutzen.
        </p>
        <p class="text-sm" :style="{ color: 'var(--color-text-muted)' }">
          <strong>Wofür nutzen wir Ihre Daten?</strong><br>
          Ein Teil der Daten wird erhoben, um eine fehlerfreie Bereitstellung der Anwendung zu gewährleisten.
          Andere Daten können zur Analyse Ihres Nutzerverhaltens verwendet werden.
        </p>
      </section>

      <section class="mb-6">
        <h2 class="text-lg font-semibold mb-2">2. Verantwortliche Stelle</h2>
        <p class="text-sm" :style="{ color: 'var(--color-text-muted)' }">
          Die verantwortliche Stelle für die Datenverarbeitung in dieser Anwendung ist:<br><br>
          Philipp Fischer<br>
          IT Conex<br>
          Musterstraße 1<br>
          12345 Musterstadt<br><br>
          E-Mail: p.fischer@itconex.de
        </p>
      </section>

      <section class="mb-6">
        <h2 class="text-lg font-semibold mb-2">3. Ihre Rechte</h2>
        <p class="text-sm mb-3" :style="{ color: 'var(--color-text-muted)' }">
          Sie haben jederzeit das Recht, unentgeltlich Auskunft über Herkunft, Empfänger und Zweck Ihrer
          gespeicherten personenbezogenen Daten zu erhalten. Sie haben außerdem ein Recht, die Berichtigung
          oder Löschung dieser Daten zu verlangen. Wenn Sie eine Einwilligung zur Datenverarbeitung erteilt
          haben, können Sie diese Einwilligung jederzeit für die Zukunft widerrufen. Außerdem haben Sie das
          Recht, unter bestimmten Umständen die Einschränkung der Verarbeitung Ihrer personenbezogenen Daten
          zu verlangen. Des Weiteren steht Ihnen ein Beschwerderecht bei der zuständigen Aufsichtsbehörde zu.
        </p>
        <p class="text-sm" :style="{ color: 'var(--color-text-muted)' }">
          Hierzu sowie zu weiteren Fragen zum Thema Datenschutz können Sie sich jederzeit an uns wenden.
        </p>
      </section>

      <section class="mb-6">
        <h2 class="text-lg font-semibold mb-2">4. Datenerfassung in dieser Anwendung</h2>

        <h3 class="font-medium mb-1">Cookies und lokaler Speicher</h3>
        <p class="text-sm mb-4" :style="{ color: 'var(--color-text-muted)' }">
          Diese Anwendung verwendet technisch notwendige Speichermechanismen (localStorage). Dabei werden
          folgende Daten gespeichert:
        </p>
        <ul class="text-sm list-disc list-inside mb-4 space-y-1" :style="{ color: 'var(--color-text-muted)' }">
          <li><strong>Authentifizierungs-Token</strong>: Für die Sitzungsverwaltung nach dem Login (technisch notwendig)</li>
          <li><strong>Theme-Einstellung</strong>: Ihre Darstellungspräferenz (hell/dunkel) für eine bessere Nutzererfahrung</li>
          <li><strong>Cookie-Einstellungen</strong>: Ihre Zustimmung zur Cookie-Nutzung</li>
        </ul>
        <p class="text-sm" :style="{ color: 'var(--color-text-muted)' }">
          Diese Daten verlassen Ihren Browser nicht und werden nicht an Dritte weitergegeben.
          Die Rechtsgrundlage ist Art. 6 Abs. 1 lit. f DSGVO (berechtigtes Interesse am Betrieb
          der Anwendung).
        </p>

        <h3 class="font-medium mt-4 mb-1">Server-Log-Dateien</h3>
        <p class="text-sm mb-4" :style="{ color: 'var(--color-text-muted)' }">
          Der Server-Betreiber dieser Anwendung kann automatisch Informationen in sogenannten
          Server-Log-Dateien speichern, die Ihr Browser automatisch übermittelt. Dies sind:
        </p>
        <ul class="text-sm list-disc list-inside mb-4 space-y-1" :style="{ color: 'var(--color-text-muted)' }">
          <li>Browsertyp und Browserversion</li>
          <li>Verwendetes Betriebssystem</li>
          <li>Referrer URL</li>
          <li>Hostname des zugreifenden Rechners</li>
          <li>Uhrzeit der Serveranfrage</li>
          <li>IP-Adresse</li>
        </ul>
        <p class="text-sm" :style="{ color: 'var(--color-text-muted)' }">
          Eine Zusammenführung dieser Daten mit anderen Datenquellen wird nicht vorgenommen.
          Die Erfassung dieser Daten erfolgt auf Grundlage von Art. 6 Abs. 1 lit. f DSGVO.
        </p>

        <h3 class="font-medium mt-4 mb-1">Nutzerdaten</h3>
        <p class="text-sm" :style="{ color: 'var(--color-text-muted)' }">
          Zur Nutzung dieser Anwendung ist eine Anmeldung erforderlich. Im Rahmen der Anmeldung
          werden Benutzername und Passwort (verschlüsselt gespeichert) verarbeitet. Diese Daten
          werden ausschließlich für die Authentifizierung und Autorisierung innerhalb der Anwendung
          verwendet. Die Rechtsgrundlage für die Verarbeitung ist Art. 6 Abs. 1 lit. b DSGVO
          (Vertragserfüllung).
        </p>
      </section>

      <section class="mb-6">
        <h2 class="text-lg font-semibold mb-2">5. Datenweitergabe</h2>
        <p class="text-sm" :style="{ color: 'var(--color-text-muted)' }">
          Eine Übermittlung Ihrer persönlichen Daten an Dritte zu anderen als den im Folgenden
          aufgeführten Zwecken findet nicht statt. Wir geben Ihre persönlichen Daten nur an Dritte
          weiter, wenn Sie Ihre ausdrückliche Einwilligung dazu erteilt haben, die Weitergabe nach
          Art. 6 Abs. 1 S. 1 lit. f DSGVO zur Geltendmachung, Ausübung oder Verteidigung von
          Rechtsansprüchen erforderlich ist und kein Grund zur Annahme besteht, dass Sie ein
          überwiegendes schutzwürdiges Interesse an der Nichtweitergabe Ihrer Daten haben.
        </p>
      </section>

      <section class="mb-6">
        <h2 class="text-lg font-semibold mb-2">6. Datensicherheit</h2>
        <p class="text-sm" :style="{ color: 'var(--color-text-muted)' }">
          Diese Anwendung nutzt aus Sicherheitsgründen und zum Schutz der Übertragung vertraulicher
          Inhalte eine SSL- bzw. TLS-Verschlüsselung. Eine verschlüsselte Verbindung erkennen Sie
          daran, dass die Adresszeile des Browsers von „http://" auf „https://" wechselt. Wenn die
          SSL- bzw. TLS-Verschlüsselung aktiviert ist, können die Daten, die Sie an uns übermitteln,
          nicht von Dritten mitgelesen werden.
        </p>
      </section>

      <div class="mt-8 pt-4 border-t text-sm text-center" :style="{ borderColor: 'var(--color-border)', color: 'var(--color-text-muted)' }">
        <router-link to="/datenschutz" class="hover:underline mr-4">Datenschutz</router-link>
        <router-link to="/impressum" class="hover:underline">Impressum</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useThemeStore } from '../stores/themeStore'

const themeStore = useThemeStore()

onMounted(() => {
  if (!document.documentElement.getAttribute('data-theme')) {
    themeStore.initTheme('dark')
  }
})
</script>

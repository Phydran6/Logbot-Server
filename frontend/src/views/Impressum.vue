<!-- ==============================================================================
     Name:        Phydran6
     Kontakt:     Phydran6
     Version:     2026.04.17.15.17.18
     Beschreibung: LogBot - Impressum (§5 TMG)
     ============================================================================== -->

<template>
  <div class="min-h-screen py-12 px-4" :style="{ backgroundColor: 'var(--color-bg)' }">
    <div class="max-w-3xl mx-auto rounded-lg p-8" :style="{ backgroundColor: 'var(--color-surface)', color: 'var(--color-text-primary)' }">

      <div class="flex items-center gap-3 mb-8">
        <router-link to="/login" class="text-sm px-3 py-1 rounded" :style="{ backgroundColor: 'var(--color-surface-elevated)', color: 'var(--color-text-secondary)' }">
          ← Zurück
        </router-link>
        <h1 class="text-2xl font-bold">Impressum</h1>
      </div>

      <section class="mb-6">
        <h2 class="text-lg font-semibold mb-2">Angaben gemäß § 5 TMG</h2>
        <p :style="{ color: 'var(--color-text-secondary)' }">
          Phydran6<br>
          IT Conex<br>
          Musterstraße 1<br>
          12345 Musterstadt<br>
          Deutschland
        </p>
      </section>

      <section class="mb-6">
        <h2 class="text-lg font-semibold mb-2">Kontakt</h2>
        <p :style="{ color: 'var(--color-text-secondary)' }">
          E-Mail: Phydran6
        </p>
      </section>

      <section class="mb-6">
        <h2 class="text-lg font-semibold mb-2">Verantwortlich für den Inhalt nach § 55 Abs. 2 RStV</h2>
        <p :style="{ color: 'var(--color-text-secondary)' }">
          Phydran6<br>
          Musterstraße 1<br>
          12345 Musterstadt
        </p>
      </section>

      <section class="mb-6">
        <h2 class="text-lg font-semibold mb-2">Haftungsausschluss</h2>
        <h3 class="font-medium mb-1">Haftung für Inhalte</h3>
        <p class="text-sm mb-3" :style="{ color: 'var(--color-text-muted)' }">
          Als Diensteanbieter sind wir gemäß § 7 Abs. 1 TMG für eigene Inhalte auf diesen Seiten nach den allgemeinen
          Gesetzen verantwortlich. Nach §§ 8 bis 10 TMG sind wir als Diensteanbieter jedoch nicht verpflichtet,
          übermittelte oder gespeicherte fremde Informationen zu überwachen oder nach Umständen zu forschen,
          die auf eine rechtswidrige Tätigkeit hinweisen. Verpflichtungen zur Entfernung oder Sperrung der Nutzung
          von Informationen nach den allgemeinen Gesetzen bleiben hiervon unberührt. Eine diesbezügliche Haftung
          ist jedoch erst ab dem Zeitpunkt der Kenntnis einer konkreten Rechtsverletzung möglich. Bei Bekanntwerden
          von entsprechenden Rechtsverletzungen werden wir diese Inhalte umgehend entfernen.
        </p>

        <h3 class="font-medium mb-1">Haftung für Links</h3>
        <p class="text-sm mb-3" :style="{ color: 'var(--color-text-muted)' }">
          Unser Angebot enthält Links zu externen Websites Dritter, auf deren Inhalte wir keinen Einfluss haben.
          Deshalb können wir für diese fremden Inhalte auch keine Gewähr übernehmen. Für die Inhalte der verlinkten
          Seiten ist stets der jeweilige Anbieter oder Betreiber der Seiten verantwortlich. Die verlinkten Seiten
          wurden zum Zeitpunkt der Verlinkung auf mögliche Rechtsverstöße überprüft. Rechtswidrige Inhalte waren
          zum Zeitpunkt der Verlinkung nicht erkennbar. Eine permanente inhaltliche Kontrolle der verlinkten Seiten
          ist jedoch ohne konkrete Anhaltspunkte einer Rechtsverletzung nicht zumutbar. Bei Bekanntwerden von
          Rechtsverletzungen werden wir derartige Links umgehend entfernen.
        </p>

        <h3 class="font-medium mb-1">Urheberrecht</h3>
        <p class="text-sm" :style="{ color: 'var(--color-text-muted)' }">
          Die durch die Seitenbetreiber erstellten Inhalte und Werke auf diesen Seiten unterliegen dem deutschen
          Urheberrecht. Die Vervielfältigung, Bearbeitung, Verbreitung und jede Art der Verwertung außerhalb der
          Grenzen des Urheberrechtes bedürfen der schriftlichen Zustimmung des jeweiligen Autors bzw. Erstellers.
          Downloads und Kopien dieser Seite sind nur für den privaten, nicht kommerziellen Gebrauch gestattet.
          Soweit die Inhalte auf dieser Seite nicht vom Betreiber erstellt wurden, werden die Urheberrechte Dritter
          beachtet. Insbesondere werden Inhalte Dritter als solche gekennzeichnet. Sollten Sie trotzdem auf eine
          Urheberrechtsverletzung aufmerksam werden, bitten wir um einen entsprechenden Hinweis. Bei Bekanntwerden
          von Rechtsverletzungen werden wir derartige Inhalte umgehend entfernen.
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

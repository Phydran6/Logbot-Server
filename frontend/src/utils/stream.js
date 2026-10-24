/**
 * ==============================================================================
 * LogBot - Ereignisströme und Links mit Kurzzeit-Ticket
 * ==============================================================================
 * EventSource, WebSocket und Download-Links können keinen Authorization-Kopf
 * mitschicken. Früher stand deshalb das volle Zugangstoken in der Adresse – und
 * damit im Zugriffsprotokoll des Servers. Jetzt holt die Oberfläche vorher ein
 * Ticket (60 Sekunden gültig, nur einmal benutzbar, nur für diesen Zweck).
 *
 * openTicketStream baut die Verbindung bei Abbruch selbst wieder auf – mit
 * frischem Ticket, denn das alte ist dann schon verbraucht.
 * ==============================================================================
 */
import { useAuthStore } from '../stores/auth'

export async function getTicket(purpose) {
  const auth = useAuthStore()
  const data = await auth.api('/api/auth/ticket', { method: 'POST', body: { purpose } })
  return data.ticket
}

/** Hängt ein frisches Ticket an eine Adresse (für Downloads und WebSockets). */
export async function withTicket(url, purpose) {
  const ticket = await getTicket(purpose)
  return `${url}${url.includes('?') ? '&' : '?'}ticket=${encodeURIComponent(ticket)}`
}

/**
 * Öffnet einen Server-Sent-Events-Strom.
 * handlers: { eventName: (data) => {} } – data ist bereits geparstes JSON.
 * Gibt eine Funktion zum Schließen zurück.
 */
export function openTicketStream(path, handlers = {}, options = {}) {
  let source = null
  let closed = false
  let retryTimer = null
  let attempts = 0

  async function connect() {
    if (closed) return
    try {
      const url = await withTicket(path, 'stream')
      if (closed) return
      source = new EventSource(url)
      source.onopen = () => { attempts = 0; options.onOpen?.() }
      for (const [name, handler] of Object.entries(handlers)) {
        source.addEventListener(name, (event) => {
          let data = {}
          try { data = JSON.parse(event.data) } catch { data = event.data }
          handler(data)
        })
      }
      source.onerror = () => {
        // Das Ticket ist verbraucht – der Browser würde mit demselben Link
        // erneut anklopfen und abgewiesen. Also selbst neu aufbauen.
        source?.close()
        options.onError?.()
        scheduleRetry()
      }
    } catch {
      scheduleRetry()
    }
  }

  function scheduleRetry() {
    if (closed) return
    attempts += 1
    const delay = Math.min(30000, 1000 * 2 ** Math.min(attempts, 5))
    clearTimeout(retryTimer)
    retryTimer = setTimeout(connect, options.retryDelay ?? delay)
  }

  connect()
  return () => {
    closed = true
    clearTimeout(retryTimer)
    source?.close()
  }
}

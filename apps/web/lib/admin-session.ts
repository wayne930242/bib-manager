// The management session lives in sessionStorage only; the credential itself is never stored.
const SESSION_KEY = "bibliography-private-asset-session"

export interface StoredSession {
  token: string
  expiresAt: string
}

export function readStoredSession(): StoredSession | null {
  const stored = sessionStorage.getItem(SESSION_KEY)
  if (!stored) return null
  try {
    const session = JSON.parse(stored) as StoredSession
    if (new Date(session.expiresAt).getTime() <= Date.now()) {
      sessionStorage.removeItem(SESSION_KEY)
      return null
    }
    return session
  } catch {
    sessionStorage.removeItem(SESSION_KEY)
    return null
  }
}

export function storeSession(session: StoredSession): void {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(session))
}

export function clearStoredSession(): void {
  sessionStorage.removeItem(SESSION_KEY)
}

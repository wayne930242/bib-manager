const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export interface Entry {
  key: string
  entry_type: string
  title: string | null
  author: string | null
  year: string | null
  journal: string | null
  publisher: string | null
  content: string
  notes: string | null
}

export interface EntryList {
  entries: Entry[]
  total: number
  page: number
  per_page: number
}

export interface SearchResult {
  entries: Entry[]
  query: string
}

export interface CiteFormat {
  typst: string
  bibtex: string
  apa: string | null
}

export async function getEntries(page = 1, perPage = 50): Promise<EntryList> {
  const res = await fetch(`${API_BASE}/api/entries?page=${page}&per_page=${perPage}`)
  if (!res.ok) throw new Error("Failed to fetch entries")
  return res.json()
}

export async function searchEntries(query: string, limit = 50): Promise<SearchResult> {
  const res = await fetch(`${API_BASE}/api/entries/search?q=${encodeURIComponent(query)}&limit=${limit}`)
  if (!res.ok) throw new Error("Failed to search entries")
  return res.json()
}

export async function getEntry(key: string): Promise<Entry> {
  const res = await fetch(`${API_BASE}/api/entries/${encodeURIComponent(key)}`)
  if (!res.ok) throw new Error("Entry not found")
  return res.json()
}

export async function getCiteFormat(key: string): Promise<CiteFormat> {
  const res = await fetch(`${API_BASE}/api/entries/${encodeURIComponent(key)}/cite`)
  if (!res.ok) throw new Error("Failed to get citation")
  return res.json()
}

export async function updateNotes(key: string, notes: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/entries/${encodeURIComponent(key)}/notes`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ notes }),
  })
  if (!res.ok) throw new Error("Failed to update notes")
}

export async function syncBibliography(): Promise<{ success: boolean }> {
  const res = await fetch(`${API_BASE}/api/cli/sync`, { method: "POST" })
  if (!res.ok) throw new Error("Failed to sync")
  return res.json()
}

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
  has_pdf: boolean
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

export type SourceAssetKind =
  | "published-pdf"
  | "author-manuscript-pdf"
  | "source-document"
  | "extracted-text"
  | "reading-notes"
  | "reading-summary"
  | "supplement"

export interface SourceAsset {
  id: string
  entry_key: string
  kind: SourceAssetKind
  filename: string
  media_type: string
  byte_size: number
  sha256: string
  source_url: string | null
  status: "pending" | "ready" | "failed"
  created_at: string
  updated_at: string
}

export interface AdminSession {
  token: string
  expires_at: string
}

export interface SourceAssetUploadRequest {
  kind: SourceAssetKind
  filename: string
  media_type: string
  byte_size: number
  sha256: string
  source_url?: string
}

export interface SourceAssetUpload {
  asset: SourceAsset
  upload_url: string | null
  upload_headers: Record<string, string>
  deduplicated: boolean
}

async function privateRequest<T>(
  path: string,
  token: string,
  init: RequestInit = {}
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...init.headers,
      Authorization: `Bearer ${token}`,
    },
  })
  if (response.status === 401) throw new Error("PRIVATE_SESSION_EXPIRED")
  if (!response.ok) throw new Error(`Private asset API returned ${response.status}`)
  return response.json()
}

export async function createAdminSession(
  credential: string
): Promise<AdminSession> {
  const response = await fetch(`${API_BASE}/api/admin/session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ credential }),
  })
  if (response.status === 401) throw new Error("Invalid management password")
  if (!response.ok) throw new Error(`Session API returned ${response.status}`)
  return response.json()
}

export async function getSourceAssets(
  key: string,
  token: string
): Promise<SourceAsset[]> {
  const payload = await privateRequest<{ assets: SourceAsset[] }>(
    `/api/admin/entries/${encodeURIComponent(key)}/assets`,
    token
  )
  return payload.assets
}

export async function startSourceAssetUpload(
  key: string,
  token: string,
  request: SourceAssetUploadRequest
): Promise<SourceAssetUpload> {
  return privateRequest(
    `/api/admin/entries/${encodeURIComponent(key)}/assets/uploads`,
    token,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    }
  )
}

export async function completeSourceAssetUpload(
  assetId: string,
  token: string
): Promise<SourceAsset> {
  return privateRequest(
    `/api/admin/assets/${encodeURIComponent(assetId)}/complete`,
    token,
    { method: "POST" }
  )
}

export async function accessSourceAsset(
  assetId: string,
  token: string,
  disposition: "inline" | "attachment"
): Promise<string> {
  const payload = await privateRequest<{ url: string }>(
    `/api/admin/assets/${encodeURIComponent(assetId)}/access?disposition=${disposition}`,
    token
  )
  return payload.url
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

export async function exportBibliography(): Promise<{ success: boolean }> {
  const res = await fetch(`${API_BASE}/api/cli/export`, { method: "POST" })
  if (!res.ok) throw new Error("Failed to export bibliography")
  return res.json()
}

"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { Download, Eye, FileUp, LockKeyhole } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  accessSourceAsset,
  completeSourceAssetUpload,
  createAdminSession,
  getSourceAssets,
  startSourceAssetUpload,
  type SourceAsset,
  type SourceAssetKind,
} from "@/lib/api"

const SESSION_KEY = "bibliography-private-asset-session"

const KIND_LABELS: Record<SourceAssetKind, string> = {
  "published-pdf": "Published PDF",
  "author-manuscript-pdf": "Author manuscript PDF",
  "source-document": "Source document",
  "extracted-text": "Extracted text",
  "reading-notes": "Reading notes",
  "reading-summary": "Reading summary",
  supplement: "Supplement",
}

interface StoredSession {
  token: string
  expiresAt: string
}

function readStoredSession(): StoredSession | null {
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

async function sha256(file: File): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer())
  return Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0")
  ).join("")
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KiB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MiB`
}

export function SourceAssetsPanel({ entryKey }: { entryKey: string }) {
  const [session, setSession] = useState<StoredSession | null>(null)
  const [credential, setCredential] = useState("")
  const [assets, setAssets] = useState<SourceAsset[]>([])
  const [kind, setKind] = useState<SourceAssetKind>("published-pdf")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const fileInput = useRef<HTMLInputElement>(null)

  const clearSession = useCallback(() => {
    sessionStorage.removeItem(SESSION_KEY)
    setSession(null)
    setAssets([])
  }, [])

  const handlePrivateError = useCallback(
    (caught: unknown) => {
      if (
        caught instanceof Error &&
        caught.message === "PRIVATE_SESSION_EXPIRED"
      ) {
        clearSession()
        setError("Session expired. Enter the management password again.")
        return
      }
      setError(caught instanceof Error ? caught.message : "Unexpected error")
    },
    [clearSession]
  )

  const refresh = useCallback(
    async (activeSession: StoredSession) => {
      try {
        setAssets(await getSourceAssets(entryKey, activeSession.token))
      } catch (caught) {
        handlePrivateError(caught)
      }
    },
    [entryKey, handlePrivateError]
  )

  useEffect(() => {
    const stored = readStoredSession()
    setSession(stored)
    if (stored) void refresh(stored)
  }, [refresh])

  const unlock = async () => {
    setBusy(true)
    setError("")
    try {
      const created = await createAdminSession(credential)
      const stored = { token: created.token, expiresAt: created.expires_at }
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(stored))
      setSession(stored)
      setCredential("")
      await refresh(stored)
    } catch (caught) {
      handlePrivateError(caught)
    } finally {
      setBusy(false)
    }
  }

  const upload = async () => {
    const file = fileInput.current?.files?.[0]
    if (!file || !session) return
    setBusy(true)
    setError("")
    try {
      const intent = await startSourceAssetUpload(entryKey, session.token, {
        kind,
        filename: file.name,
        media_type: file.type || "application/octet-stream",
        byte_size: file.size,
        sha256: await sha256(file),
      })
      if (intent.upload_url) {
        const uploaded = await fetch(intent.upload_url, {
          method: "PUT",
          headers: intent.upload_headers,
          body: file,
        })
        if (!uploaded.ok) throw new Error(`R2 upload returned ${uploaded.status}`)
        await completeSourceAssetUpload(intent.asset.id, session.token)
      }
      if (fileInput.current) fileInput.current.value = ""
      await refresh(session)
    } catch (caught) {
      handlePrivateError(caught)
    } finally {
      setBusy(false)
    }
  }

  const openAsset = async (
    asset: SourceAsset,
    disposition: "inline" | "attachment"
  ) => {
    if (!session) return
    setError("")
    const preview = window.open("about:blank", "_blank")
    if (preview) preview.opener = null
    try {
      const url = await accessSourceAsset(asset.id, session.token, disposition)
      if (!preview) throw new Error("The browser blocked the new tab")
      preview.location.replace(url)
    } catch (caught) {
      preview?.close()
      handlePrivateError(caught)
    }
  }

  if (!session) {
    return (
      <div className="space-y-4 rounded border border-neutral-200 p-4">
        <div className="flex items-center gap-2 text-sm font-medium">
          <LockKeyhole className="h-4 w-4" />
          Private source assets
        </div>
        <p className="text-sm text-neutral-500">
          The credential is exchanged for a short-lived session and is not
          stored.
        </p>
        <div className="flex gap-2">
          <Input
            type="password"
            value={credential}
            onChange={(event) => setCredential(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void unlock()
            }}
            placeholder="Management password"
            autoComplete="current-password"
          />
          <Button onClick={unlock} disabled={!credential || busy}>
            Unlock
          </Button>
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-2 sm:grid-cols-[12rem_1fr_auto]">
        <select
          value={kind}
          onChange={(event) => setKind(event.target.value as SourceAssetKind)}
          className="h-9 rounded-md border border-neutral-200 bg-white px-3 text-sm"
          aria-label="Source asset kind"
        >
          {Object.entries(KIND_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <Input ref={fileInput} type="file" />
        <Button onClick={upload} disabled={busy}>
          <FileUp className="h-4 w-4" />
          {busy ? "Working…" : "Upload"}
        </Button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="divide-y divide-neutral-100 rounded border border-neutral-200">
        {assets.length === 0 ? (
          <p className="p-4 text-sm text-neutral-500">No source assets yet.</p>
        ) : (
          assets.map((asset) => (
            <div
              key={asset.id}
              className="flex flex-wrap items-center justify-between gap-3 p-3"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{asset.filename}</p>
                <p className="mt-1 text-xs text-neutral-500">
                  {KIND_LABELS[asset.kind]} · {formatBytes(asset.byte_size)} · {asset.status}
                </p>
              </div>
              {asset.status === "ready" && (
                <div className="flex gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => void openAsset(asset, "inline")}
                  >
                    <Eye className="h-4 w-4" />
                    Preview
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => void openAsset(asset, "attachment")}
                  >
                    <Download className="h-4 w-4" />
                    Download
                  </Button>
                </div>
              )}
            </div>
          ))
        )}
      </div>

      <div className="flex justify-end">
        <Button variant="ghost" size="sm" onClick={clearSession}>
          Lock private assets
        </Button>
      </div>
    </div>
  )
}

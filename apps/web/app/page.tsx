"use client"

import { useState, useEffect, useCallback } from "react"
import { Search, LayoutGrid, List, RefreshCw, Copy, Check } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { EntryTable } from "@/components/entry-table"
import { EntryCard } from "@/components/entry-card"
import { EntryDialog } from "@/components/entry-dialog"
import { getEntries, searchEntries, syncBibliography, getCiteFormat, type Entry } from "@/lib/api"

function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value)
  useEffect(() => {
    const handler = setTimeout(() => setDebouncedValue(value), delay)
    return () => clearTimeout(handler)
  }, [value, delay])
  return debouncedValue
}

export default function Home() {
  const [entries, setEntries] = useState<Entry[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [query, setQuery] = useState("")
  const [view, setView] = useState<"table" | "card">("table")
  const [selectedEntry, setSelectedEntry] = useState<Entry | null>(null)
  const [copiedKey, setCopiedKey] = useState<string | null>(null)
  const [total, setTotal] = useState(0)

  const debouncedQuery = useDebounce(query, 300)

  const loadEntries = useCallback(async () => {
    setLoading(true)
    try {
      if (debouncedQuery.trim()) {
        const result = await searchEntries(debouncedQuery)
        setEntries(result.entries)
        setTotal(result.entries.length)
      } else {
        const result = await getEntries(1, 100)
        setEntries(result.entries)
        setTotal(result.total)
      }
    } catch (error) {
      console.error("Failed to load entries:", error)
    } finally {
      setLoading(false)
    }
  }, [debouncedQuery])

  useEffect(() => {
    loadEntries()
  }, [loadEntries])

  const handleSync = async () => {
    setSyncing(true)
    try {
      await syncBibliography()
      await loadEntries()
    } catch (error) {
      console.error("Sync failed:", error)
    } finally {
      setSyncing(false)
    }
  }

  const handleCopy = async (key: string, format: "typst" | "bibtex" | "apa" = "typst") => {
    try {
      if (format === "typst") {
        await navigator.clipboard.writeText(`@${key}`)
      } else {
        const cite = await getCiteFormat(key)
        await navigator.clipboard.writeText(cite[format] || "")
      }
      setCopiedKey(key)
      setTimeout(() => setCopiedKey(null), 2000)
    } catch (error) {
      console.error("Failed to copy:", error)
    }
  }

  return (
    <div className="min-h-screen bg-neutral-50">
      <header className="border-b border-neutral-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div>
            <h1 className="font-serif text-xl font-semibold text-neutral-900">
              Bibliography Manager
            </h1>
            <p className="text-sm text-neutral-500">
              {total.toLocaleString()} entries
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleSync}
            disabled={syncing}
          >
            <RefreshCw className={`h-4 w-4 ${syncing ? "animate-spin" : ""}`} />
            Sync
          </Button>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-6">
        <div className="mb-6 flex items-center gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-400" />
            <Input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by title, author, key..."
              className="pl-10 font-mono"
            />
          </div>
          <Tabs value={view} onValueChange={(v) => setView(v as "table" | "card")}>
            <TabsList>
              <TabsTrigger value="table">
                <List className="h-4 w-4" />
              </TabsTrigger>
              <TabsTrigger value="card">
                <LayoutGrid className="h-4 w-4" />
              </TabsTrigger>
            </TabsList>
          </Tabs>
        </div>

        {loading ? (
          <div className="flex h-64 items-center justify-center text-neutral-400">
            Loading...
          </div>
        ) : entries.length === 0 ? (
          <div className="flex h-64 flex-col items-center justify-center text-neutral-400">
            <p>No entries found</p>
            {query && (
              <Button
                variant="link"
                className="mt-2"
                onClick={() => setQuery("")}
              >
                Clear search
              </Button>
            )}
          </div>
        ) : view === "table" ? (
          <div className="rounded-lg border border-neutral-200 bg-white">
            <EntryTable
              entries={entries}
              onSelect={setSelectedEntry}
              onCopy={handleCopy}
            />
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {entries.map((entry, index) => (
              <EntryCard
                key={`${entry.key}-${entry.entry_type}-${index}`}
                entry={entry}
                onSelect={setSelectedEntry}
                onCopy={handleCopy}
              />
            ))}
          </div>
        )}

        {copiedKey && (
          <div className="fixed bottom-6 right-6 flex items-center gap-2 rounded-lg bg-neutral-900 px-4 py-2 text-sm text-white shadow-lg">
            <Check className="h-4 w-4" />
            Copied @{copiedKey}
          </div>
        )}
      </main>

      <EntryDialog
        entry={selectedEntry}
        onClose={() => setSelectedEntry(null)}
        onCopy={handleCopy}
      />
    </div>
  )
}

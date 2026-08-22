"use client"

import { useState, useEffect } from "react"
import { Copy, Save } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { getCiteFormat, updateNotes, type Entry, type CiteFormat } from "@/lib/api"

interface EntryDialogProps {
  entry: Entry | null
  onClose: () => void
  onCopy: (key: string) => void
}

export function EntryDialog({ entry, onClose, onCopy }: EntryDialogProps) {
  const [notes, setNotes] = useState(() => entry?.notes || "")
  const [saving, setSaving] = useState(false)
  const [citeFormats, setCiteFormats] = useState<CiteFormat | null>(null)
  const [activeTab, setActiveTab] = useState("details")

  useEffect(() => {
    if (!entry) return

    let cancelled = false
    getCiteFormat(entry.key)
      .then((formats) => {
        if (!cancelled) setCiteFormats(formats)
      })
      .catch(console.error)

    return () => {
      cancelled = true
    }
  }, [entry])

  const handleSaveNotes = async () => {
    if (!entry) return
    setSaving(true)
    try {
      await updateNotes(entry.key, notes)
    } catch (error) {
      console.error("Failed to save notes:", error)
    } finally {
      setSaving(false)
    }
  }

  const copyToClipboard = async (text: string) => {
    await navigator.clipboard.writeText(text)
  }

  if (!entry) return null

  return (
    <Dialog open={!!entry} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="font-serif text-lg">
            {entry.title || "Untitled"}
          </DialogTitle>
          <p className="text-sm text-neutral-500">
            {entry.author || "Unknown author"}
            {entry.year && ` (${entry.year})`}
          </p>
        </DialogHeader>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="w-full">
            <TabsTrigger value="details" className="flex-1">Details</TabsTrigger>
            <TabsTrigger value="cite" className="flex-1">Cite</TabsTrigger>
            <TabsTrigger value="notes" className="flex-1">Notes</TabsTrigger>
          </TabsList>

          <TabsContent value="details" className="mt-4 space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-neutral-500">Key:</span>
                <code className="ml-2 rounded bg-neutral-100 px-2 py-0.5">
                  @{entry.key}
                </code>
              </div>
              <div>
                <span className="text-neutral-500">Type:</span>
                <span className="ml-2">{entry.entry_type}</span>
              </div>
              {entry.journal && (
                <div className="col-span-2">
                  <span className="text-neutral-500">Journal:</span>
                  <span className="ml-2 italic">{entry.journal}</span>
                </div>
              )}
              {entry.publisher && (
                <div className="col-span-2">
                  <span className="text-neutral-500">Publisher:</span>
                  <span className="ml-2">{entry.publisher}</span>
                </div>
              )}
            </div>

            <div>
              <h4 className="mb-2 text-sm font-medium text-neutral-500">
                BibTeX Entry
              </h4>
              <pre className="max-h-48 overflow-auto rounded bg-neutral-50 p-3 text-xs">
                {entry.content}
              </pre>
            </div>
          </TabsContent>

          <TabsContent value="cite" className="mt-4 space-y-4">
            <div>
              <div className="mb-2 flex items-center justify-between">
                <h4 className="text-sm font-medium">Typst / LaTeX</h4>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onCopy(entry.key)}
                >
                  <Copy className="h-4 w-4" />
                </Button>
              </div>
              <code className="block rounded bg-neutral-50 p-3 font-mono text-sm">
                {citeFormats?.typst || `@${entry.key}`}
              </code>
            </div>

            {citeFormats?.apa && (
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <h4 className="text-sm font-medium">APA</h4>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => copyToClipboard(citeFormats.apa!)}
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
                <p className="rounded bg-neutral-50 p-3 text-sm">
                  {citeFormats.apa}
                </p>
              </div>
            )}

            <div>
              <div className="mb-2 flex items-center justify-between">
                <h4 className="text-sm font-medium">BibTeX</h4>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => copyToClipboard(entry.content)}
                >
                  <Copy className="h-4 w-4" />
                </Button>
              </div>
              <pre className="max-h-32 overflow-auto rounded bg-neutral-50 p-3 text-xs">
                {entry.content}
              </pre>
            </div>
          </TabsContent>

          <TabsContent value="notes" className="mt-4">
            <Textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Add notes about this entry..."
              className="min-h-[200px] font-mono text-sm"
            />
            <div className="mt-4 flex justify-end">
              <Button onClick={handleSaveNotes} disabled={saving}>
                <Save className="h-4 w-4" />
                {saving ? "Saving..." : "Save Notes"}
              </Button>
            </div>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  )
}

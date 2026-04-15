"use client"

import { Copy, FileText, ChevronDown } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import type { Entry } from "@/lib/api"

interface EntryCardProps {
  entry: Entry
  onSelect: (entry: Entry) => void
  onCopy: (key: string, format: "typst" | "bibtex" | "apa") => void
}

export function EntryCard({ entry, onSelect, onCopy }: EntryCardProps) {
  return (
    <div
      className="cursor-pointer rounded-lg border border-neutral-200 bg-white p-4 transition-shadow hover:shadow-md"
      onClick={() => onSelect(entry)}
    >
      <div className="mb-2 flex items-start justify-between">
        <code className="rounded bg-neutral-100 px-2 py-0.5 text-sm font-medium">
          @{entry.key}
        </code>
        <div className="flex items-center gap-1">
          {entry.notes && <FileText className="h-4 w-4 text-neutral-400" />}
          <DropdownMenu>
            <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
              <Button variant="ghost" size="sm" className="h-7 gap-1 px-2">
                <Copy className="h-3.5 w-3.5" />
                <ChevronDown className="h-3 w-3" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
              <DropdownMenuItem onClick={() => onCopy(entry.key, "typst")}>
                <span className="font-mono text-xs">@{entry.key}</span>
                <span className="ml-2 text-neutral-400">Typst</span>
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onCopy(entry.key, "apa")}>
                <span className="text-xs">Author (Year)</span>
                <span className="ml-2 text-neutral-400">APA</span>
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onCopy(entry.key, "bibtex")}>
                <span className="text-xs">Full entry</span>
                <span className="ml-2 text-neutral-400">BibTeX</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <h3 className="mb-1 line-clamp-2 font-serif text-base leading-tight">
        {entry.title || "Untitled"}
      </h3>

      <p className="mb-2 text-sm text-neutral-600">
        {entry.author || "Unknown author"}
        {entry.year && ` (${entry.year})`}
      </p>

      <div className="flex items-center gap-2">
        <span className="rounded bg-neutral-100 px-2 py-0.5 text-xs text-neutral-500">
          {entry.entry_type}
        </span>
        {entry.journal && (
          <span className="truncate text-xs italic text-neutral-400">
            {entry.journal}
          </span>
        )}
      </div>

      {entry.notes && (
        <p className="mt-3 line-clamp-2 border-t border-neutral-100 pt-2 text-xs text-neutral-500">
          {entry.notes}
        </p>
      )}
    </div>
  )
}

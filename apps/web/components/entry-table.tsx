"use client"

import { Copy, FileText, ChevronDown } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import type { Entry } from "@/lib/api"

interface EntryTableProps {
  entries: Entry[]
  onSelect: (entry: Entry) => void
  onCopy: (key: string, format: "typst" | "bibtex" | "apa") => void
}

export function EntryTable({ entries, onSelect, onCopy }: EntryTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[140px] font-mono">Key</TableHead>
          <TableHead className="w-[80px]">Type</TableHead>
          <TableHead>Title</TableHead>
          <TableHead className="w-[180px]">Author</TableHead>
          <TableHead className="w-[60px]">Year</TableHead>
          <TableHead className="w-[100px]">Copy</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {entries.map((entry, index) => (
          <TableRow
            key={`${entry.key}-${entry.entry_type}-${index}`}
            className="cursor-pointer hover:bg-neutral-50"
            onClick={() => onSelect(entry)}
          >
            <TableCell className="font-mono text-sm">{entry.key}</TableCell>
            <TableCell className="text-xs text-neutral-500">
              {entry.entry_type}
            </TableCell>
            <TableCell className="max-w-[400px] truncate" title={entry.title || ""}>
              {entry.title || "—"}
              {entry.notes && (
                <FileText className="ml-2 inline h-3 w-3 text-neutral-400" />
              )}
            </TableCell>
            <TableCell className="max-w-[180px] truncate text-sm text-neutral-600">
              {entry.author || "—"}
            </TableCell>
            <TableCell className="text-sm">{entry.year || "—"}</TableCell>
            <TableCell>
              <DropdownMenu>
                <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                  <Button variant="ghost" size="sm" className="h-8 gap-1 px-2">
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
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

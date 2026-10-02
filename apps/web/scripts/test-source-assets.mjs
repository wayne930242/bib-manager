import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import test from "node:test"

const apiUrl = new URL("../lib/api.ts", import.meta.url)
const panelUrl = new URL(
  "../components/source-assets-panel.tsx",
  import.meta.url
)
const dialogUrl = new URL("../components/entry-dialog.tsx", import.meta.url)
const sessionUrl = new URL("../lib/admin-session.ts", import.meta.url)

test("source assets use a session-only management credential", async () => {
  const [api, panel, session] = await Promise.all([
    readFile(apiUrl, "utf8"),
    readFile(panelUrl, "utf8"),
    readFile(sessionUrl, "utf8"),
  ])

  assert.match(api, /\/api\/admin\/session/)
  assert.match(session, /sessionStorage\.setItem/)
  assert.match(session, /sessionStorage\.removeItem/)
  assert.doesNotMatch(session, /localStorage/)
  assert.match(panel, /storeSession\(/)
  assert.match(panel, /crypto\.subtle\.digest\("SHA-256"/)
})

test("bibliography writes send the management session", async () => {
  const api = await readFile(apiUrl, "utf8")

  assert.match(api, /updateNotes\([\s\S]*?token: string[\s\S]*?privateRequest\(/)
  assert.match(
    api,
    /exportBibliography\([\s\S]*?token: string[\s\S]*?privateRequest\("\/api\/cli\/export"/
  )
})

test("entry dialog integrates upload, preview, and download", async () => {
  const [panel, dialog] = await Promise.all([
    readFile(panelUrl, "utf8"),
    readFile(dialogUrl, "utf8"),
  ])

  assert.match(dialog, /TabsTrigger value="assets"/)
  assert.match(dialog, /SourceAssetsPanel/)
  assert.match(panel, /published-pdf/)
  assert.match(panel, /author-manuscript-pdf/)
  assert.match(panel, /Preview/)
  assert.match(panel, /Download/)
  assert.match(panel, /window\.open\("about:blank"/)
})

import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import test from "node:test"

const apiUrl = new URL("../lib/api.ts", import.meta.url)
const panelUrl = new URL(
  "../components/source-assets-panel.tsx",
  import.meta.url
)
const dialogUrl = new URL("../components/entry-dialog.tsx", import.meta.url)

test("source assets use a session-only management credential", async () => {
  const [api, panel] = await Promise.all([
    readFile(apiUrl, "utf8"),
    readFile(panelUrl, "utf8"),
  ])

  assert.match(api, /\/api\/admin\/session/)
  assert.match(panel, /sessionStorage\.setItem/)
  assert.match(panel, /sessionStorage\.removeItem/)
  assert.doesNotMatch(panel, /localStorage/)
  assert.match(panel, /crypto\.subtle\.digest\("SHA-256"/)
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

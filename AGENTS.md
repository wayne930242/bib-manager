# bib-manager

以繁體中文溝通。這是 pnpm／Turbo monorepo：`apps/api/` 是 Python API，`apps/web/` 是 Next.js 前端。
資料流、環境與部署細節以 [README.md](README.md) 為準。

## 資料與存取界線

- SQL 資料庫是書目權威；`../../literature/references/bibliography.bib` 是衍生匯出。
- 文獻搜尋僅供發現，明確選取後才儲存。匯入 `.bib` 屬明確遷移，不當作正常同步來源。
- 公開 API 只提供公開書目資料；原始 PDF、擷取文字、儲存金鑰與存取網址遵守私有資產界線。
- 私有資產管理 session 與 Blog 同步 token 分開；不在版本控制、日誌或回覆中暴露秘密。
- 本機 SQLite 留在 WSL Linux 檔案系統，Windows 用 HTTP API；不把使用中的資料庫放到 vault 或同步磁碟。

## 執行與驗證

在此機 WSL 使用 `corepack pnpm`。依變更選擇已有驗證：

- API：`corepack pnpm test:api`，使用專案 wrapper 保持測試暫存檔在 Linux。
- 前端型別：`corepack pnpm --dir apps/web exec tsc --noEmit --incremental false`。
- 前端 lint：`corepack pnpm --dir apps/web lint`。
- 私有資產前端行為：`corepack pnpm --dir apps/web test:source-assets`。
- 編譯驗證：需要時執行 `corepack pnpm build`。

閱讀目標檔與既有測試後再改動；遷移、資料寫入及部署依本次授權範圍。
提交只暫存本次檔案；含父層 gitlink 的交付先完成本 submodule，再處理 phd-essay 及主專案。

## Codex

技能位於 `.agents/skills/`；MCP 與 hooks 分別使用 literature 與 phd-essay 共用設定的同步副本。
此 checkout 的啟動、信任及檢查限制見 [../../.codex/README.md](../../.codex/README.md)。
檢查工具缺失或逾時要回報未完成；shell 編輯不會觸發只匹配 apply_patch 的 hook，須手動驗證。

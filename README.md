# Bibliography manager

The bibliography is **database-first**:

- The canonical library is a SQL database. Production uses managed
  PostgreSQL; local development can fall back to SQLite.
- `literature/references/bibliography.bib` is a generated Typst/interchange
  artifact, never an input during normal operation.
- Importing a `.bib` file is an explicit migration operation.
- Discovery results are saved to the DB only when selected; searches do not
  automatically pollute the library.

## Database and Windows/WSL

Set `DATABASE_URL` to a pooled PostgreSQL connection string in every deployed
or shared environment (`BIB_DATABASE_URL` remains an optional override). The implementation is provider-neutral; Neon is the
recommended free hosted default without making its SDK part of the app.

If `BIB_DATABASE_URL` is unset, development uses
`~/.local/share/knowledge-base/library.sqlite3`. Keep that fallback file on the
WSL Linux filesystem: do not place it under `/mnt/c`, an Obsidian vault,
OneDrive, Syncthing, or another file-sync/network mount while it is live.
Windows and mobile clients use the HTTP API rather than opening DB files.

Database files and credentials are intentionally excluded from Git.
Before exposing a hosted API publicly, add authentication and set
`BIB_CORS_ORIGINS` to the deployed frontend origin; the current setup is a
private data foundation, not a public multi-user service.

Schema changes are versioned in `apps/api/migrations`. Use the unpooled direct
connection for migrations:

```bash
uv run --project apps/api --directory apps/api alembic upgrade head
```

## Data flow

```text
paper discovery -> explicit save -> PostgreSQL -> selected/full export -> .bib -> Typst
legacy .bib ------------------------^ (one-time or explicit import only)
```

API operations:

- `POST /api/entries` and `/api/entries/batch`: canonical DB writes.
- `POST /api/entries/export`: render selected keys without writing a file.
- `POST /api/cli/export`: regenerate the shared `bibliography.bib` from DB.
- `POST /api/cli/import-legacy`: explicit one-way legacy import.
- `POST /api/sync/blog-posts`: replace bibliography-linked public posts.

The sync endpoint requires `Authorization: Bearer $BIB_SYNC_TOKEN`. The `blog`
repository runs its sync workflow after related content reaches `main`; it uses
a GitHub variable named
`BIB_MANAGER_API_URL` and a GitHub secret named `BIB_SYNC_TOKEN`.

For a repeatable Vercel deployment, set `BIB_SYNC_TOKEN` alongside the Neon
variables in `.env.local`, authenticate `vercel` and `gh`, then run:

```bash
pnpm deploy:api
```

The script configures encrypted Production/Preview variables, synchronizes the
shared GitHub secret, and deploys `apps/api`. Local development continues to
read `.env.local`; Vercel does not accept Sensitive variables for Development.

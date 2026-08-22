#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_ROOT="$REPO_ROOT/apps/api"
ENV_FILE="${BIB_ENV_FILE:-$REPO_ROOT/.env.local}"
VERCEL_PROJECT="${VERCEL_API_PROJECT:-bib-manager-api}"
VERCEL_COMMAND="${VERCEL_BIN:-vercel}"
CORS_ORIGINS="${BIB_CORS_ORIGINS:-https://wayneh.tw,https://www.wayneh.tw,http://localhost:3000,http://localhost:3001}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

for name in DATABASE_URL DATABASE_URL_UNPOOLED BIB_SYNC_TOKEN; do
  if [[ -z "${!name:-}" ]]; then
    echo "$name is required (environment or $ENV_FILE)." >&2
    exit 1
  fi
done

if [[ ! -f "$API_ROOT/.vercel/project.json" ]]; then
  "$VERCEL_COMMAND" link --cwd "$API_ROOT" --yes --project "$VERCEL_PROJECT"
fi

for target in production preview; do
  printf '%s' "$DATABASE_URL" | "$VERCEL_COMMAND" env add DATABASE_URL "$target" --sensitive --force --cwd "$API_ROOT"
  printf '%s' "$DATABASE_URL_UNPOOLED" | "$VERCEL_COMMAND" env add DATABASE_URL_UNPOOLED "$target" --sensitive --force --cwd "$API_ROOT"
  printf '%s' "$BIB_SYNC_TOKEN" | "$VERCEL_COMMAND" env add BIB_SYNC_TOKEN "$target" --sensitive --force --cwd "$API_ROOT"
  printf '%s' "$CORS_ORIGINS" | "$VERCEL_COMMAND" env add BIB_CORS_ORIGINS "$target" --force --cwd "$API_ROOT"
done

printf '%s' "$BIB_SYNC_TOKEN" | gh secret set BIB_SYNC_TOKEN --repo wayne930242/bib-manager
printf '%s' "$BIB_SYNC_TOKEN" | gh secret set BIB_SYNC_TOKEN --repo wayne930242/blog

"$VERCEL_COMMAND" deploy --cwd "$API_ROOT" --prod --yes

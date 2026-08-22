#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_ROOT="$REPO_ROOT/apps/api"
TEST_TMPDIR="${BIB_TEST_TMPDIR:-/tmp}"
UV_COMMAND="${UV_BIN:-uv}"

# Windows TEMP/TMP paths inherited by WSL can cause pytest capture files to
# disappear or inherit incompatible permissions. Keep test I/O on Linux.
export TMPDIR="$TEST_TMPDIR"
export TMP="$TEST_TMPDIR"
export TEMP="$TEST_TMPDIR"
export PYTHONPATH="$API_ROOT${PYTHONPATH:+:$PYTHONPATH}"

mkdir -p "$TEST_TMPDIR"
exec "$UV_COMMAND" run --project "$API_ROOT" pytest -q "$API_ROOT/tests"

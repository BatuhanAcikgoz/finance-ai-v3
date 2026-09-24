#!/usr/bin/env bash
# =============================================================================
# scripts/publish.sh — create the GitHub repo and push
# Usage:
#   ./scripts/publish.sh BatuhanAcikgoz/finance-ai-v3
#   ./scripts/publish.sh BatuhanAcikgoz/finance-ai-v3 --public
#   ./scripts/publish.sh BatuhanAcikgoz/finance-ai-v3 --private
#
# Requires: gh CLI authenticated (`gh auth login`).
# Exits non-zero on any failure.
# =============================================================================
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <owner/repo> [--public|--private]" >&2
  exit 64
fi

SLUG="$1"
VISIBILITY_FLAG=""
shift || true
if [[ $# -gt 0 ]]; then
  case "$1" in
    --public|--private) VISIBILITY_FLAG="--$1" ;;
    *) echo "unknown flag: $1" >&2; exit 64 ;;
  esac
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI not found. Install: https://cli.github.com/" >&2
  exit 127
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "gh CLI is not authenticated. Run: gh auth login" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# --- Safety: ensure clean working tree (or only known files) ----------------
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "not inside a git repo: $ROOT_DIR" >&2
  exit 1
fi

BRANCH="$(git symbolic-ref --short HEAD 2>/dev/null || echo main)"
echo "→ current branch: $BRANCH"

# --- Create the repo (idempotent if it already exists) -----------------------
echo "→ creating GitHub repo: $SLUG ${VISIBILITY_FLAG:-(default visibility)}"
if ! gh repo create "$SLUG" $VISIBILITY_FLAG --source=. --remote=origin --push 2>/dev/null; then
  echo "  (repo may already exist — adding remote and pushing instead)"
  git remote remove origin 2>/dev/null || true
  git remote add origin "https://github.com/${SLUG}.git"
  git push -u origin "$BRANCH"
fi

echo
echo "✓ published: https://github.com/${SLUG}"

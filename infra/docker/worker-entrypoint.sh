#!/usr/bin/env bash
# Entrypoint for worker containers.
# Runs `python -m <SERVICE_PACKAGE>` with SIGTERM forwarded.
set -euo pipefail

: "${SERVICE_PACKAGE:?SERVICE_PACKAGE env var must be set (set by docker build arg)}"

exec python -m "${SERVICE_PACKAGE}"

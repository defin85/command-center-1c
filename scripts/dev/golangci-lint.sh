#!/bin/bash

set -euo pipefail

if command -v golangci-lint >/dev/null 2>&1; then
  exec golangci-lint "$@"
fi

if ! command -v go >/dev/null 2>&1; then
  echo "golangci-lint: not found in PATH, and go is not available to run it" >&2
  exit 127
fi

# Fallback: run pinned version via `go run` (no preinstalled binary required).
exec go run github.com/golangci/golangci-lint/cmd/golangci-lint@v1.64.8 "$@"


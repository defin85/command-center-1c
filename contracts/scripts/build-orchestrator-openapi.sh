#!/bin/bash
# Build/check orchestrator OpenAPI bundle from modular sources.
# Usage: ./contracts/scripts/build-orchestrator-openapi.sh [build|check]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTRACTS_DIR="$(dirname "$SCRIPT_DIR")"
ORCHESTRATOR_DIR="$CONTRACTS_DIR/orchestrator"
SRC_DIR="$ORCHESTRATOR_DIR/src"
SRC_ROOT="$SRC_DIR/openapi.yaml"
BUNDLE_FILE="$ORCHESTRATOR_DIR/openapi.yaml"
REDOCLY_VERSION="${REDOCLY_VERSION:-2.19.1}"
MODE="${1:-build}"

usage() {
    echo "Usage: $0 [build|check]"
    echo "  build (default): regenerate contracts/orchestrator/openapi.yaml from src/"
    echo "  check: fail if bundle is missing or out of date"
}

if [[ $# -gt 1 ]]; then
    usage
    exit 1
fi

if [[ ! -d "$SRC_DIR" ]] || [[ ! -f "$SRC_ROOT" ]]; then
    echo "Error: modular source is missing: $SRC_ROOT" >&2
    echo "Expected contracts/orchestrator/src/** as source of truth." >&2
    exit 1
fi

if command -v redocly >/dev/null 2>&1; then
    REDOCLY_CMD=(redocly)
elif command -v npx >/dev/null 2>&1; then
    REDOCLY_CMD=(npx --yes --quiet "@redocly/cli@${REDOCLY_VERSION}")
else
    echo "Error: neither redocly nor npx is available in PATH" >&2
    exit 1
fi

TMP_BUNDLE="$(mktemp "${TMPDIR:-/tmp}/orchestrator-openapi.bundle.XXXXXX.yaml")"
cleanup() {
    rm -f "$TMP_BUNDLE"
}
trap cleanup EXIT INT TERM

"${REDOCLY_CMD[@]}" bundle "$SRC_ROOT" --output "$TMP_BUNDLE" --ext yaml

case "$MODE" in
    build)
        mkdir -p "$(dirname "$BUNDLE_FILE")"
        if [[ -f "$BUNDLE_FILE" ]] && cmp -s "$TMP_BUNDLE" "$BUNDLE_FILE"; then
            echo "Bundle is up to date: $BUNDLE_FILE"
            exit 0
        fi
        mv "$TMP_BUNDLE" "$BUNDLE_FILE"
        trap - EXIT INT TERM
        echo "Bundle updated: $BUNDLE_FILE"
        ;;
    check)
        if [[ ! -f "$BUNDLE_FILE" ]]; then
            echo "Error: bundle file is missing: $BUNDLE_FILE" >&2
            echo "Run: ./contracts/scripts/build-orchestrator-openapi.sh build" >&2
            exit 1
        fi
        if cmp -s "$TMP_BUNDLE" "$BUNDLE_FILE"; then
            echo "Bundle is up to date: $BUNDLE_FILE"
            exit 0
        fi
        echo "Error: bundle is out of date: $BUNDLE_FILE" >&2
        echo "Run: ./contracts/scripts/build-orchestrator-openapi.sh build" >&2
        exit 1
        ;;
    *)
        usage
        exit 1
        ;;
esac

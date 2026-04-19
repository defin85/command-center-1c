#!/usr/bin/env bash

set -euo pipefail

cc1c_require_python() {
  if ! command -v python3 >/dev/null 2>&1; then
    echo "Missing required executable: python3" >&2
    exit 1
  fi
}

cc1c_api_base_url() {
  local base_url="${CC1C_BASE_URL:-http://localhost:15173}"
  printf '%s' "${base_url%/}"
}

cc1c_access_token() {
  if [[ -n "${CC1C_ACCESS_TOKEN:-}" ]]; then
    printf '%s' "$CC1C_ACCESS_TOKEN"
    return 0
  fi

  if [[ -n "${ACCESS_TOKEN:-}" ]]; then
    printf '%s' "$ACCESS_TOKEN"
    return 0
  fi

  if [[ -z "${CC1C_UI_USER:-}" || -z "${CC1C_UI_PASSWORD:-}" ]]; then
    echo "Set CC1C_ACCESS_TOKEN (or ACCESS_TOKEN), or provide CC1C_UI_USER and CC1C_UI_PASSWORD for automatic login." >&2
    exit 1
  fi

  cc1c_require_python

  local response_file
  response_file="$(mktemp)"
  local auth_body
  auth_body="$(python3 -c 'import json, os; print(json.dumps({"username": os.environ["CC1C_UI_USER"], "password": os.environ["CC1C_UI_PASSWORD"]}))')"
  local auth_status
  auth_status="$(
    curl --noproxy '*' -sS \
      -o "$response_file" \
      -w '%{http_code}' \
      -H 'Content-Type: application/json' \
      -d "$auth_body" \
      "$(cc1c_api_base_url)/api/token"
  )"

  if (( auth_status >= 400 )); then
    cat "$response_file" >&2
    rm -f "$response_file"
    echo "Automatic login failed with HTTP $auth_status." >&2
    exit 1
  fi

  python3 -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["access"])' "$response_file"
  rm -f "$response_file"
}

cc1c_build_query_string() {
  if [[ $# -eq 0 ]]; then
    return 0
  fi

  cc1c_require_python
  python3 -c '
import sys
from urllib.parse import urlencode

pairs = []
for raw in sys.argv[1:]:
    if "=" not in raw:
        raise SystemExit(f"Expected key=value filter, got: {raw}")
    key, value = raw.split("=", 1)
    if not key:
        raise SystemExit(f"Empty query key in: {raw}")
    if value == "":
        continue
    pairs.append((key, value))
print(urlencode(pairs, doseq=True))
' "$@"
}

cc1c_print_json_file() {
  local response_file="$1"

  cc1c_require_python
  if python3 -m json.tool "$response_file" >/dev/null 2>&1; then
    python3 -m json.tool "$response_file"
    return 0
  fi

  cat "$response_file"
}

cc1c_api_get_json() {
  if [[ $# -lt 2 ]]; then
    echo "cc1c_api_get_json requires <endpoint> <require_tenant:0|1> [key=value ...]" >&2
    exit 1
  fi

  local endpoint="$1"
  local require_tenant="$2"
  shift 2

  local token
  token="$(cc1c_access_token)"

  local headers=(
    -H "Authorization: Bearer $token"
    -H 'Accept: application/json'
  )

  if [[ "$require_tenant" == "1" ]]; then
    if [[ -z "${CC1C_TENANT_ID:-}" ]]; then
      echo "Set CC1C_TENANT_ID for tenant-scoped UI observability queries." >&2
      exit 1
    fi
    headers+=(-H "X-CC1C-Tenant-ID: $CC1C_TENANT_ID")
  elif [[ -n "${CC1C_TENANT_ID:-}" ]]; then
    headers+=(-H "X-CC1C-Tenant-ID: $CC1C_TENANT_ID")
  fi

  local query=""
  if [[ $# -gt 0 ]]; then
    query="$(cc1c_build_query_string "$@")"
  fi

  local url
  url="$(cc1c_api_base_url)$endpoint"
  if [[ -n "$query" ]]; then
    url="$url?$query"
  fi

  local response_file
  response_file="$(mktemp)"
  local http_status
  http_status="$(
    curl --noproxy '*' -sS \
      -o "$response_file" \
      -w '%{http_code}' \
      "${headers[@]}" \
      "$url"
  )"

  cc1c_print_json_file "$response_file"
  rm -f "$response_file"

  if (( http_status >= 400 )); then
    echo "HTTP $http_status for $endpoint" >&2
    return 1
  fi
}

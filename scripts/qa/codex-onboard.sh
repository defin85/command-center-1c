#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"

printf '# Codex Onboard\n\n'
printf 'Canonical onboarding router: docs/agent/INDEX.md\n'
printf 'First verification entrypoint: make agent-verify\n'
printf 'Feature pack root: ai/features/\n'
printf 'Primary repo docs:\n'
printf -- '- docs/agent/ARCHITECTURE_MAP.md\n'
printf -- '- docs/agent/DOMAIN_MAP.md\n'
printf -- '- docs/agent/RUNBOOK.md\n'
printf -- '- docs/agent/VERIFY.md\n'
printf -- '- docs/agent/TASK_ROUTING.md\n'

printf '\nAvailable feature packs:\n'
found=0
while IFS= read -r feature_dir; do
  feature_name="$(basename "$feature_dir")"
  found=1
  printf -- '- %s\n' "$feature_name"
done < <(find "$ROOT/ai/features" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | LC_ALL=C sort)

if [ "$found" -eq 0 ]; then
  printf -- '- none detected\n'
fi

cat <<'EOF'

Next commands:
- make agent-verify
- make validate-feature FEATURE=<feature-id>
- make feature-start FEATURE=<feature-id>
- make feature-baseline FEATURE=<feature-id> RUN_ID=<run-id>
- make feature-iteration FEATURE=<feature-id> RUN_ID=<run-id>
- make feature-holdout FEATURE=<feature-id> RUN_ID=<run-id>
- make feature-ci-replay RUN_ID=<run-id> [PHASE=both]
EOF

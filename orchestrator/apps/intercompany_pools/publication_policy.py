from __future__ import annotations

# API-level retry contract bounds for publication workflow path.
# Publication side effects are worker-owned after cutover, but facade validation
# keeps stable limits for backward-compatible request semantics.
MAX_PUBLICATION_ATTEMPTS = 5
MAX_RETRY_INTERVAL_SECONDS = 120


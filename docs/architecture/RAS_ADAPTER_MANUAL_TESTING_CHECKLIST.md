# RAS Adapter - Manual Testing Checklist (v2)

**Purpose:** Быстрая ручная проверка `/api/v2/*` endpoints ras-adapter перед релизом/регрессией.

## Prerequisites

```bash
# Start ras-adapter
./scripts/dev/start-all.sh

# Optional: point to your RAS server
export TEST_RAS_SERVER="localhost:1545"
```

## Endpoints

### 1) Health

```bash
curl -sf http://localhost:8088/health
```

### 2) List clusters

```bash
curl -sf "http://localhost:8088/api/v2/list-clusters?server=${TEST_RAS_SERVER}"
```

Extract first `cluster_id`:

```bash
CLUSTER_ID="$(curl -sf "http://localhost:8088/api/v2/list-clusters?server=${TEST_RAS_SERVER}" | python - <<'PY'
import json, sys
data = json.load(sys.stdin)
clusters = data.get("clusters", [])
print((clusters[0] or {}).get("uuid", "") if clusters else "")
PY
)"
echo "$CLUSTER_ID"
```

### 3) List infobases

```bash
curl -sf "http://localhost:8088/api/v2/list-infobases?cluster_id=${CLUSTER_ID}"
```

### 4) Lock/Unlock infobase (scheduled jobs)

> Требуются права администратора кластера/базы.

```bash
INFOBASE_ID="<UUID>"

curl -sf -X POST "http://localhost:8088/api/v2/lock-infobase?cluster_id=${CLUSTER_ID}&infobase_id=${INFOBASE_ID}" \
  -H "Content-Type: application/json" \
  -d '{"db_user":"admin","db_password":"secret"}'

curl -sf -X POST "http://localhost:8088/api/v2/unlock-infobase?cluster_id=${CLUSTER_ID}&infobase_id=${INFOBASE_ID}" \
  -H "Content-Type: application/json" \
  -d '{"db_user":"admin","db_password":"secret"}'
```

### 5) List sessions

```bash
curl -sf "http://localhost:8088/api/v2/list-sessions?cluster_id=${CLUSTER_ID}&infobase_id=${INFOBASE_ID}"
```

### 6) Terminate all sessions

```bash
curl -sf -X POST "http://localhost:8088/api/v2/terminate-sessions?cluster_id=${CLUSTER_ID}&infobase_id=${INFOBASE_ID}"
```

## Notes

- Полный reference по v2 endpoints: `go-services/ras-adapter/internal/api/rest/v2/README.md`.
- v1 endpoints удалены (если нужен старый чеклист — `docs/archive/architecture/RAS_ADAPTER_MANUAL_TESTING_CHECKLIST_V1.md`).

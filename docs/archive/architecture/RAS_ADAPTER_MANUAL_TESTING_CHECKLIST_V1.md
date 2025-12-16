# RAS Adapter - Manual Testing Checklist (Archived v1)

**Version:** 1.0
**Date:** 2025-11-19
**Purpose:** Comprehensive manual validation of RAS Adapter (historical)

> Архив: этот чеклист был написан под v1 REST endpoints, которые удалены. Для актуального v2 checklist см. `docs/architecture/RAS_ADAPTER_MANUAL_TESTING_CHECKLIST.md`.

---

## Testing Environment Setup

### Prerequisites

```bash
# 1. Start RAS Server (if not running)
cd /c/1CProject/ras-grpc-gw
./start-ras.sh  # или как запускается у вас

# 2. Start RAS Adapter
cd /c/1CProject/command-center-1c/go-services/ras-adapter
go run cmd/main.go

# 3. Verify health
curl http://localhost:8088/health
# Expected: {"status":"healthy","service":"ras-adapter","version":"v2.0.0"}

curl http://localhost:9090/health
# Expected: gRPC health check OK
```

### Test Data Preparation

```bash
# Get real cluster and infobase IDs from your 1C environment
export TEST_CLUSTER_ID="c3e50859-3d41-4383-b0d7-4ee20272b69d"
export TEST_INFOBASE_ID="60e7713e-b933-49e0-a3ae-5107ef56560c"
export TEST_RAS_SERVER="localhost:1545"
```

---

## REST API Testing

### 1. Health Check Endpoint

**Endpoint:** `GET /health`

```bash
curl http://localhost:8088/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "service": "ras-adapter",
  "version": "v2.0.0",
  "timestamp": "2025-01-15T10:30:00Z"
}
```

**Checklist:**
- [ ] Returns HTTP 200
- [ ] JSON response is valid
- [ ] Contains all expected fields
- [ ] Response time < 100ms

---

### 2. Get Clusters

**Endpoint:** `GET /api/v1/clusters?server={rasServer}`

```bash
curl "http://localhost:8088/api/v1/clusters?server=${TEST_RAS_SERVER}"
```

**Expected Response:**
```json
{
  "clusters": [
    {
      "uuid": "c3e50859-3d41-4383-b0d7-4ee20272b69d",
      "name": "Local cluster",
      "server": "localhost:1541"
    }
  ]
}
```

**Checklist:**
- [ ] Returns HTTP 200
- [ ] Returns at least 1 cluster
- [ ] Cluster UUID is valid
- [ ] Cluster name is not empty
- [ ] Response time < 2s

**Error Cases:**

```bash
# Missing server parameter
curl "http://localhost:8088/api/v1/clusters"
# Expected: HTTP 400 {"error": "server parameter is required"}

# Invalid RAS server
curl "http://localhost:8088/api/v1/clusters?server=invalid:9999"
# Expected: HTTP 500 {"error": "failed to connect to RAS server"}
```

**Checklist:**
- [ ] Returns HTTP 400 for missing server
- [ ] Returns HTTP 500 for invalid server
- [ ] Error messages are clear

---

### 3. Get Infobases

**Endpoint:** `GET /api/v1/infobases?cluster_id={clusterId}`

```bash
curl "http://localhost:8088/api/v1/infobases?cluster_id=${TEST_CLUSTER_ID}"
```

**Expected Response:**
```json
{
  "infobases": [
    {
      "uuid": "60e7713e-b933-49e0-a3ae-5107ef56560c",
      "name": "БухУчет_База001",
      "description": "Бухгалтерия предприятия",
      "scheduled_jobs_deny": false,
      "sessions_deny": false
    },
    {
      "uuid": "...",
      "name": "БухУчет_База002",
      "...": "..."
    }
  ]
}
```

**Checklist:**
- [ ] Returns HTTP 200
- [ ] Returns at least 1 infobase
- [ ] Infobase UUID is valid
- [ ] Infobase name is not empty
- [ ] scheduled_jobs_deny is boolean
- [ ] sessions_deny is boolean
- [ ] Response time < 5s

**Error Cases:**

```bash
# Missing cluster_id
curl "http://localhost:8088/api/v1/infobases"
# Expected: HTTP 400

# Invalid cluster_id
curl "http://localhost:8088/api/v1/infobases?cluster_id=invalid-uuid"
# Expected: HTTP 404 or 500
```

**Checklist:**
- [ ] Returns HTTP 400 for missing cluster_id
- [ ] Returns HTTP 404/500 for invalid cluster_id

---

### 4. Lock Infobase (NEW IMPLEMENTATION - CRITICAL!)

**Endpoint:** `POST /api/v1/infobases/{infobaseId}/lock`

```bash
curl -X POST "http://localhost:8088/api/v1/infobases/${TEST_INFOBASE_ID}/lock" \
  -H "Content-Type: application/json" \
  -d "{
    \"cluster_id\": \"${TEST_CLUSTER_ID}\",
    \"scheduled_jobs_deny\": true
  }"
```

**Expected Response:**
```json
{
  "success": true,
  "message": "Infobase locked successfully"
}
```

**Checklist:**
- [ ] Returns HTTP 200
- [ ] success is true
- [ ] message is not empty
- [ ] Response time < 2s

**CRITICAL VALIDATION:**

После lock запроса, проверь что infobase действительно заблокирована:

```bash
# Get infobase info
curl "http://localhost:8088/api/v1/infobases?cluster_id=${TEST_CLUSTER_ID}" | jq '.infobases[] | select(.uuid == "'$TEST_INFOBASE_ID'")'

# Expected:
# {
#   "uuid": "...",
#   "scheduled_jobs_deny": true  ← ДОЛЖНО БЫТЬ true!
# }
```

**Checklist:**
- [ ] ✅ scheduled_jobs_deny изменилось на true
- [ ] ✅ sessions_deny осталось false (мы НЕ блокируем пользователей)

**Error Cases:**

```bash
# Missing cluster_id
curl -X POST "http://localhost:8088/api/v1/infobases/${TEST_INFOBASE_ID}/lock" \
  -H "Content-Type: application/json" \
  -d '{"scheduled_jobs_deny": true}'
# Expected: HTTP 400

# Invalid infobase_id
curl -X POST "http://localhost:8088/api/v1/infobases/invalid-uuid/lock" \
  -H "Content-Type: application/json" \
  -d "{\"cluster_id\": \"${TEST_CLUSTER_ID}\"}"
# Expected: HTTP 404 or 500
```

**Checklist:**
- [ ] Returns HTTP 400 for missing cluster_id
- [ ] Returns HTTP 404/500 for invalid infobase_id
- [ ] Error messages are clear

---

### 5. Unlock Infobase (NEW IMPLEMENTATION - CRITICAL!)

**Endpoint:** `POST /api/v1/infobases/{infobaseId}/unlock`

```bash
curl -X POST "http://localhost:8088/api/v1/infobases/${TEST_INFOBASE_ID}/unlock" \
  -H "Content-Type: application/json" \
  -d "{
    \"cluster_id\": \"${TEST_CLUSTER_ID}\"
  }"
```

**Expected Response:**
```json
{
  "success": true,
  "message": "Infobase unlocked successfully"
}
```

**Checklist:**
- [ ] Returns HTTP 200
- [ ] success is true
- [ ] message is not empty
- [ ] Response time < 2s

**CRITICAL VALIDATION:**

После unlock запроса, проверь что infobase действительно разблокирована:

```bash
curl "http://localhost:8088/api/v1/infobases?cluster_id=${TEST_CLUSTER_ID}" | jq '.infobases[] | select(.uuid == "'$TEST_INFOBASE_ID'")'

# Expected:
# {
#   "uuid": "...",
#   "scheduled_jobs_deny": false  ← ДОЛЖНО БЫТЬ false!
# }
```

**Checklist:**
- [ ] ✅ scheduled_jobs_deny изменилось на false

---

### 6. Get Sessions

**Endpoint:** `GET /api/v1/sessions?cluster_id={clusterId}`

```bash
curl "http://localhost:8088/api/v1/sessions?cluster_id=${TEST_CLUSTER_ID}"
```

**Expected Response:**
```json
{
  "sessions": [
    {
      "uuid": "abc123",
      "infobase_id": "60e7713e-b933-49e0-a3ae-5107ef56560c",
      "user_name": "Администратор",
      "application": "1CV8C",
      "started_at": "2025-01-15T10:00:00Z"
    }
  ]
}
```

**Checklist:**
- [ ] Returns HTTP 200
- [ ] Returns sessions array (может быть пустой)
- [ ] Session fields are valid
- [ ] Response time < 3s

---

### 7. Terminate Session

**Endpoint:** `POST /api/v1/sessions/{sessionId}/terminate`

**⚠️ CRITICAL:** Этот endpoint убивает реальную сессию! Тестируй осторожно.

```bash
# Сначала получи список сессий
curl "http://localhost:8088/api/v1/sessions?cluster_id=${TEST_CLUSTER_ID}"

# Выбери тестовую сессию (НЕ свою!)
export TEST_SESSION_ID="abc123"

# Terminate
curl -X POST "http://localhost:8088/api/v1/sessions/${TEST_SESSION_ID}/terminate" \
  -H "Content-Type: application/json" \
  -d "{
    \"cluster_id\": \"${TEST_CLUSTER_ID}\"
  }"
```

**Expected Response:**
```json
{
  "success": true,
  "message": "Session terminated successfully"
}
```

**Checklist:**
- [ ] Returns HTTP 200
- [ ] success is true
- [ ] Session disappeared from session list

**⚠️ Skip this test if no test sessions available**

---

## gRPC API Testing

### Prerequisites

```bash
# Install grpcurl (if not installed)
go install github.com/fullstorydev/grpcurl/cmd/grpcurl@latest

# Test gRPC health
grpcurl -plaintext localhost:9090 grpc.health.v1.Health/Check
```

### 1. LockInfobase (gRPC)

```bash
grpcurl -plaintext \
  -d '{
    "cluster_id": "'$TEST_CLUSTER_ID'",
    "infobase_id": "'$TEST_INFOBASE_ID'",
    "scheduled_jobs_deny": true
  }' \
  localhost:9090 rasadapter.InfobaseService/LockInfobase
```

**Expected Response:**
```json
{
  "success": true,
  "message": "Infobase locked successfully"
}
```

**Checklist:**
- [ ] gRPC call succeeds
- [ ] Response matches REST API response
- [ ] Infobase is locked (verify via REST API)

---

### 2. UnlockInfobase (gRPC)

```bash
grpcurl -plaintext \
  -d '{
    "cluster_id": "'$TEST_CLUSTER_ID'",
    "infobase_id": "'$TEST_INFOBASE_ID'"
  }' \
  localhost:9090 rasadapter.InfobaseService/UnlockInfobase
```

**Expected Response:**
```json
{
  "success": true,
  "message": "Infobase unlocked successfully"
}
```

**Checklist:**
- [ ] gRPC call succeeds
- [ ] Response matches REST API response
- [ ] Infobase is unlocked (verify via REST API)

---

### 3. GetInfobases (gRPC)

```bash
grpcurl -plaintext \
  -d '{"cluster_id": "'$TEST_CLUSTER_ID'"}' \
  localhost:9090 rasadapter.InfobaseService/GetInfobases
```

**Checklist:**
- [ ] gRPC call succeeds
- [ ] Returns list of infobases
- [ ] Response matches REST API response

---

## End-to-End Workflow Testing

### Test 1: Lock → Verify → Unlock Workflow

```bash
echo "=== Test 1: Lock → Verify → Unlock Workflow ==="

# Step 1: Get initial state
echo "Step 1: Getting initial state..."
curl -s "http://localhost:8088/api/v1/infobases?cluster_id=${TEST_CLUSTER_ID}" | \
  jq '.infobases[] | select(.uuid == "'$TEST_INFOBASE_ID'") | {uuid, scheduled_jobs_deny}'

# Step 2: Lock infobase
echo "Step 2: Locking infobase..."
curl -s -X POST "http://localhost:8088/api/v1/infobases/${TEST_INFOBASE_ID}/lock" \
  -H "Content-Type: application/json" \
  -d '{"cluster_id": "'$TEST_CLUSTER_ID'", "scheduled_jobs_deny": true}' | jq

# Step 3: Verify lock
echo "Step 3: Verifying lock..."
curl -s "http://localhost:8088/api/v1/infobases?cluster_id=${TEST_CLUSTER_ID}" | \
  jq '.infobases[] | select(.uuid == "'$TEST_INFOBASE_ID'") | {uuid, scheduled_jobs_deny}'
# Expected: scheduled_jobs_deny = true

# Step 4: Unlock infobase
echo "Step 4: Unlocking infobase..."
curl -s -X POST "http://localhost:8088/api/v1/infobases/${TEST_INFOBASE_ID}/unlock" \
  -H "Content-Type: application/json" \
  -d '{"cluster_id": "'$TEST_CLUSTER_ID'"}' | jq

# Step 5: Verify unlock
echo "Step 5: Verifying unlock..."
curl -s "http://localhost:8088/api/v1/infobases?cluster_id=${TEST_CLUSTER_ID}" | \
  jq '.infobases[] | select(.uuid == "'$TEST_INFOBASE_ID'") | {uuid, scheduled_jobs_deny}'
# Expected: scheduled_jobs_deny = false

echo "=== Test 1: PASSED ==="
```

**Checklist:**
- [ ] ✅ Initial state retrieved
- [ ] ✅ Lock succeeded
- [ ] ✅ scheduled_jobs_deny = true after lock
- [ ] ✅ Unlock succeeded
- [ ] ✅ scheduled_jobs_deny = false after unlock

---

### Test 2: Multiple Lock/Unlock Cycles

```bash
echo "=== Test 2: Multiple Lock/Unlock Cycles ==="

for i in {1..5}; do
  echo "Cycle $i:"

  # Lock
  curl -s -X POST "http://localhost:8088/api/v1/infobases/${TEST_INFOBASE_ID}/lock" \
    -H "Content-Type: application/json" \
    -d '{"cluster_id": "'$TEST_CLUSTER_ID'", "scheduled_jobs_deny": true}' | jq .success

  # Verify
  LOCKED=$(curl -s "http://localhost:8088/api/v1/infobases?cluster_id=${TEST_CLUSTER_ID}" | \
    jq -r '.infobases[] | select(.uuid == "'$TEST_INFOBASE_ID'") | .scheduled_jobs_deny')
  echo "  Locked: $LOCKED"

  # Unlock
  curl -s -X POST "http://localhost:8088/api/v1/infobases/${TEST_INFOBASE_ID}/unlock" \
    -H "Content-Type: application/json" \
    -d '{"cluster_id": "'$TEST_CLUSTER_ID'"}' | jq .success

  # Verify
  UNLOCKED=$(curl -s "http://localhost:8088/api/v1/infobases?cluster_id=${TEST_CLUSTER_ID}" | \
    jq -r '.infobases[] | select(.uuid == "'$TEST_INFOBASE_ID'") | .scheduled_jobs_deny')
  echo "  Unlocked: $UNLOCKED"
done

echo "=== Test 2: PASSED ==="
```

**Checklist:**
- [ ] ✅ All 5 cycles completed without errors
- [ ] ✅ No state corruption

---

### Test 3: Concurrent Requests

```bash
echo "=== Test 3: Concurrent Requests ==="

# Launch 10 parallel lock requests
for i in {1..10}; do
  (curl -s -X POST "http://localhost:8088/api/v1/infobases/${TEST_INFOBASE_ID}/lock" \
    -H "Content-Type: application/json" \
    -d '{"cluster_id": "'$TEST_CLUSTER_ID'", "scheduled_jobs_deny": true}' &)
done

wait

# Verify final state
curl -s "http://localhost:8088/api/v1/infobases?cluster_id=${TEST_CLUSTER_ID}" | \
  jq '.infobases[] | select(.uuid == "'$TEST_INFOBASE_ID'") | {uuid, scheduled_jobs_deny}'

# Expected: scheduled_jobs_deny = true (no race condition)

echo "=== Test 3: PASSED ==="
```

**Checklist:**
- [ ] ✅ No errors from concurrent requests
- [ ] ✅ Final state is consistent (locked)
- [ ] ✅ No race conditions

---

### Test 4: REST vs gRPC Consistency

```bash
echo "=== Test 4: REST vs gRPC Consistency ==="

# Lock via REST
echo "Lock via REST..."
curl -s -X POST "http://localhost:8088/api/v1/infobases/${TEST_INFOBASE_ID}/lock" \
  -H "Content-Type: application/json" \
  -d '{"cluster_id": "'$TEST_CLUSTER_ID'", "scheduled_jobs_deny": true}' | jq

# Verify via gRPC
echo "Verify via gRPC..."
grpcurl -plaintext -d '{"cluster_id": "'$TEST_CLUSTER_ID'"}' \
  localhost:9090 rasadapter.InfobaseService/GetInfobases | \
  jq '.infobases[] | select(.uuid == "'$TEST_INFOBASE_ID'") | {uuid, scheduledJobsDeny}'

# Unlock via gRPC
echo "Unlock via gRPC..."
grpcurl -plaintext \
  -d '{"cluster_id": "'$TEST_CLUSTER_ID'", "infobase_id": "'$TEST_INFOBASE_ID'"}' \
  localhost:9090 rasadapter.InfobaseService/UnlockInfobase

# Verify via REST
echo "Verify via REST..."
curl -s "http://localhost:8088/api/v1/infobases?cluster_id=${TEST_CLUSTER_ID}" | \
  jq '.infobases[] | select(.uuid == "'$TEST_INFOBASE_ID'") | {uuid, scheduled_jobs_deny}'

echo "=== Test 4: PASSED ==="
```

**Checklist:**
- [ ] ✅ Lock via REST works
- [ ] ✅ gRPC sees locked state
- [ ] ✅ Unlock via gRPC works
- [ ] ✅ REST sees unlocked state
- [ ] ✅ REST and gRPC are consistent

---

## Performance Testing

### Test 1: Response Time

```bash
echo "=== Performance Test: Response Time ==="

# Test GetClusters
time curl -s "http://localhost:8088/api/v1/clusters?server=${TEST_RAS_SERVER}" > /dev/null

# Test GetInfobases
time curl -s "http://localhost:8088/api/v1/infobases?cluster_id=${TEST_CLUSTER_ID}" > /dev/null

# Test LockInfobase
time curl -s -X POST "http://localhost:8088/api/v1/infobases/${TEST_INFOBASE_ID}/lock" \
  -H "Content-Type: application/json" \
  -d '{"cluster_id": "'$TEST_CLUSTER_ID'", "scheduled_jobs_deny": true}' > /dev/null
```

**Checklist:**
- [ ] GetClusters < 2s
- [ ] GetInfobases < 5s
- [ ] LockInfobase < 2s
- [ ] UnlockInfobase < 2s

---

### Test 2: Throughput

```bash
echo "=== Performance Test: Throughput ==="

# Run 100 sequential requests
START=$(date +%s)
for i in {1..100}; do
  curl -s "http://localhost:8088/health" > /dev/null
done
END=$(date +%s)

DURATION=$((END - START))
THROUGHPUT=$((100 / DURATION))

echo "100 requests in ${DURATION}s = ${THROUGHPUT} req/s"
```

**Checklist:**
- [ ] Throughput > 10 req/s for health checks
- [ ] No errors during load

---

## Error Handling Testing

### Test 1: RAS Server Down

```bash
echo "=== Error Test: RAS Server Down ==="

# Stop RAS server
# (manually stop RAS)

# Try to get clusters
curl "http://localhost:8088/api/v1/clusters?server=localhost:1545"

# Expected: HTTP 500 with clear error message
```

**Checklist:**
- [ ] Returns HTTP 500
- [ ] Error message indicates RAS connection failure
- [ ] Service doesn't crash

---

### Test 2: Invalid Input

```bash
echo "=== Error Test: Invalid Input ==="

# Invalid cluster_id format
curl "http://localhost:8088/api/v1/infobases?cluster_id=not-a-uuid"

# Missing required field
curl -X POST "http://localhost:8088/api/v1/infobases/${TEST_INFOBASE_ID}/lock" \
  -H "Content-Type: application/json" \
  -d '{}'

# Invalid JSON
curl -X POST "http://localhost:8088/api/v1/infobases/${TEST_INFOBASE_ID}/lock" \
  -H "Content-Type: application/json" \
  -d 'invalid json'
```

**Checklist:**
- [ ] Returns HTTP 400 for invalid input
- [ ] Error messages are descriptive
- [ ] Service doesn't crash

---

## Final Validation Checklist

### Functional Requirements

- [ ] ✅ All REST endpoints work
- [ ] ✅ All gRPC endpoints work
- [ ] ✅ Lock/Unlock implementation works (NEW IMPL)
- [ ] ✅ Lock changes scheduled_jobs_deny to true
- [ ] ✅ Unlock changes scheduled_jobs_deny to false
- [ ] ✅ REST and gRPC are consistent
- [ ] ✅ Multiple lock/unlock cycles work
- [ ] ✅ Concurrent requests handled correctly

### Performance Requirements

- [ ] ✅ GetClusters < 2s
- [ ] ✅ GetInfobases < 5s
- [ ] ✅ LockInfobase < 2s
- [ ] ✅ UnlockInfobase < 2s
- [ ] ✅ Health check < 100ms
- [ ] ✅ Throughput > 10 req/s

### Error Handling

- [ ] ✅ RAS server down handled gracefully
- [ ] ✅ Invalid input returns HTTP 400
- [ ] ✅ Error messages are clear
- [ ] ✅ Service doesn't crash on errors

### Code Quality

- [ ] ✅ Logs are structured (JSON)
- [ ] ✅ Logs include correlation IDs
- [ ] ✅ No sensitive data in logs
- [ ] ✅ Unit tests coverage > 70%

---

## Sign-off

**Tested by:** _______________________
**Date:** _______________________
**Status:** ✅ PASSED / ❌ FAILED

**Notes:**
```
...any issues or observations...
```

---

## Next Steps After Sign-off

✅ **If all tests PASSED:**
- Proceed to Week 5: Tracing Infrastructure
- Start OpenTelemetry + Jaeger deployment

❌ **If any tests FAILED:**
- Document failures
- Fix issues
- Re-run this checklist
- Do NOT proceed until all tests pass

---

**Version History:**

- v1.0 (2025-11-19): Initial checklist for RAS Adapter MVP validation

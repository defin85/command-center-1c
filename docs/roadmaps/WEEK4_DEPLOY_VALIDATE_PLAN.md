# Week 4: Deploy & Validate - Architectural Plan

**Date:** 2025-11-20
**Version:** 1.0
**Status:** DRAFT - Ready for Review

---

## Executive Summary

**Goal:** Deploy RAS Adapter to development environment in parallel with cluster-service, validate performance, perform cutover to deprecate old services.

**Key Decisions:**
- ✅ **Deploy on host** (not Docker) - consistent with current dev workflow
- ✅ **Parallel deployment** - RAS Adapter (8088) alongside cluster-service (8089 temporary)
- ✅ **Zero-downtime cutover** - Worker uses same Redis channels
- ✅ **Comprehensive validation** - Manual testing gate before production

**Timeline:** 2-3 days
**Risk Level:** LOW (rollback plan ready)

---

## 1. Deployment Strategy

### 1.1 Current Infrastructure Analysis

**Findings:**

| Component | Location | Deployment | Port | Status |
|-----------|----------|------------|------|--------|
| **cluster-service** | `go-services/cluster-service/` | Host (start-all.sh) | 8088 | Active |
| **ras-grpc-gw** | `../ras-grpc-gw/` (external fork) | Host (manual start) | 9999 (gRPC), 8081 (HTTP) | Active |
| **ras-adapter** | `go-services/ras-adapter/` | NOT deployed | - | Built (bin/cc1c-ras-adapter.exe) |
| **PostgreSQL, Redis** | docker-compose.local.yml | Docker | 5432, 6379 | Active |
| **Worker** | go-services/worker/ | Host (start-all.sh) | - | Active |

**cluster-service Architecture (OLD):**
```
Worker → Redis Pub/Sub → cluster-service (Go:8088)
                             ↓
                        gRPC client → ras-grpc-gw (Go:9999)
                                         ↓
                                      RAS binary protocol → 1C RAS (1545)
```

**ras-adapter Architecture (NEW):**
```
Worker → Redis Pub/Sub → ras-adapter (Go:8088)
                             ↓
                        khorevaa/ras-client (direct RAS protocol) → 1C RAS (1545)
```

**Key Differences:**
- ✅ **Network hops:** 2 → 1 (removed ras-grpc-gw middleman)
- ✅ **Services count:** 7 → 6 (deprecate cluster-service + ras-grpc-gw)
- ✅ **Latency:** Expected reduction 30-50% (one less network hop)
- ✅ **Complexity:** Lower (fewer moving parts)

**Redis Channels (UNCHANGED):**

| Direction | Channel | Publisher | Subscriber |
|-----------|---------|-----------|------------|
| Command | `commands:cluster-service:infobase:lock` | Worker | cluster-service / ras-adapter |
| Event | `events:cluster-service:infobase:locked` | cluster-service / ras-adapter | Worker |
| Command | `commands:cluster-service:infobase:unlock` | Worker | cluster-service / ras-adapter |
| Event | `events:cluster-service:infobase:unlocked` | cluster-service / ras-adapter | Worker |
| Command | `commands:cluster-service:sessions:terminate` | Worker | cluster-service / ras-adapter |
| Event | `events:cluster-service:sessions:closed` | cluster-service / ras-adapter | Worker |

**Critical Insight:** RAS Adapter uses **SAME Redis channels** as cluster-service → zero Worker code changes needed!

### 1.2 Chosen Approach

**Deployment Strategy: VARIANT A - Deploy on Host (Hybrid Mode)**

**Rationale:**

✅ **Consistent with current dev workflow:**
- All Go services (api-gateway, worker, cluster-service) run on host via `scripts/dev/start-all.sh`
- Easy debugging (no Docker rebuild required)
- Fast iteration cycle (build → restart)

✅ **Minimal changes to infrastructure:**
- Reuse existing build system (`bin/cc1c-ras-adapter.exe` already built)
- Reuse existing scripts/dev/*.sh framework
- Environment variables loaded from `.env.local` (same as other services)

✅ **No Docker complexity:**
- No need for Dockerfile, docker-compose updates
- No network isolation issues (host networking)
- No volume mounts for binaries

❌ **Disadvantages (acceptable for dev environment):**
- Less production-like (production will be Kubernetes)
- No process isolation (but we have PID files)

**Decision: VARIANT A**

### 1.3 Deployment Steps

#### Phase 1: Preparation (10 min)

1. **Build RAS Adapter binary** (if not already built):
   ```bash
   cd /c/1CProject/command-center-1c/go-services/ras-adapter
   go build -o ../../bin/cc1c-ras-adapter.exe cmd/main.go

   # Verify binary
   ../../bin/cc1c-ras-adapter.exe --version
   # Expected: Service: cc1c-ras-adapter, Version: vX.Y.Z
   ```

2. **Verify environment variables** in `.env.local`:
   ```bash
   # Required for ras-adapter:
   RAS_SERVER_ADDR=localhost:1545      # 1C RAS server address
   SERVER_PORT=8088                    # HTTP server port (same as cluster-service)
   REDIS_HOST=localhost                # Redis host
   REDIS_PORT=6379                     # Redis port
   LOG_LEVEL=info                      # Log level
   RAS_MAX_CONNECTIONS=10              # Connection pool size
   RAS_CONN_TIMEOUT=5s                 # Connection timeout
   RAS_REQUEST_TIMEOUT=10s             # Request timeout
   REDIS_PUBSUB_ENABLED=true           # Enable event handlers
   ```

3. **Verify prerequisites running**:
   ```bash
   # PostgreSQL
   docker ps | grep postgres

   # Redis
   docker exec -it redis redis-cli ping
   # Expected: PONG

   # 1C RAS server
   telnet localhost 1545
   # Expected: connection established
   ```

#### Phase 2: Parallel Deployment (5 min)

**Strategy:** Run RAS Adapter on port 8088 (target), temporarily move cluster-service to 8089

1. **Stop cluster-service** (if running):
   ```bash
   ./scripts/dev/stop-all.sh
   # или
   kill $(cat pids/cluster-service.pid)
   rm pids/cluster-service.pid
   ```

2. **Update start-all.sh** to include ras-adapter:

   **File:** `scripts/dev/start-all.sh`

   **Changes:**
   ```bash
   ##############################################################################
   # Шаг 10: RAS Adapter (Go) - НОВЫЙ, заменяет cluster-service
   ##############################################################################
   echo -e "${BLUE}[10/12] Запуск RAS Adapter (port 8088)...${NC}"

   # Бинарник гарантированно существует после Phase 1
   BINARY_PATH="$BIN_DIR/cc1c-ras-adapter.exe"

   # .env.local уже загружен в начале скрипта

   # Переопределить порт для ras-adapter (default 8088)
   export SERVER_PORT=8088

   nohup "$BINARY_PATH" > "$LOGS_DIR/ras-adapter.log" 2>&1 &
   RAS_ADAPTER_PID=$!
   echo $RAS_ADAPTER_PID > "$PIDS_DIR/ras-adapter.pid"

   sleep 3
   if kill -0 $RAS_ADAPTER_PID 2>/dev/null; then
       echo -e "${GREEN}✓ RAS Adapter запущен (PID: $RAS_ADAPTER_PID)${NC}"
   else
       echo -e "${RED}✗ Не удалось запустить RAS Adapter${NC}"
       cat "$LOGS_DIR/ras-adapter.log"
       exit 1
   fi
   echo ""
   ```

3. **OPTIONAL: Keep cluster-service for comparison** (parallel deployment):

   **Add to start-all.sh** (before RAS Adapter section):
   ```bash
   ##############################################################################
   # Шаг 9.5: Cluster Service (Go) - LEGACY, на порту 8089 для сравнения
   ##############################################################################
   echo -e "${YELLOW}[9.5/12] Запуск Cluster Service LEGACY (port 8089)...${NC}"

   BINARY_PATH="$BIN_DIR/cc1c-cluster-service.exe"

   # Временно на порту 8089 для parallel testing
   export SERVER_PORT=8089

   nohup "$BINARY_PATH" > "$LOGS_DIR/cluster-service-legacy.log" 2>&1 &
   CLUSTER_SERVICE_LEGACY_PID=$!
   echo $CLUSTER_SERVICE_LEGACY_PID > "$PIDS_DIR/cluster-service-legacy.pid"

   sleep 2
   if kill -0 $CLUSTER_SERVICE_LEGACY_PID 2>/dev/null; then
       echo -e "${GREEN}✓ Cluster Service LEGACY запущен (PID: $CLUSTER_SERVICE_LEGACY_PID)${NC}"
   else
       echo -e "${YELLOW}⚠ Cluster Service LEGACY не запустился (это OK, тестируем новый RAS Adapter)${NC}"
   fi
   echo ""
   ```

4. **Start services**:
   ```bash
   ./scripts/dev/start-all.sh

   # Verify both services running (if parallel deployment):
   curl http://localhost:8088/health   # ras-adapter
   curl http://localhost:8089/health   # cluster-service (legacy)
   ```

5. **Check logs**:
   ```bash
   ./scripts/dev/logs.sh ras-adapter
   # Expected: "starting RAS Adapter", "RAS connection pool initialized", "HTTP server listening on 0.0.0.0:8088"
   ```

#### Phase 3: Validation (covered in Section 3)

---

## 2. Parallel Deployment (Testing Phase)

### 2.1 Port Configuration

**Production Configuration (after cutover):**

| Service | Port | Status |
|---------|------|--------|
| ras-adapter | 8088 | ✅ ACTIVE |
| cluster-service | - | ❌ DEPRECATED (stopped) |
| ras-grpc-gw | - | ❌ DEPRECATED (stopped) |

**Testing Configuration (parallel deployment OPTIONAL):**

| Service | Port | Status | Purpose |
|---------|------|--------|---------|
| ras-adapter | 8088 | ✅ ACTIVE | New implementation (target) |
| cluster-service | 8089 | 🟡 LEGACY | Old implementation (comparison only) |
| ras-grpc-gw | 9999 (gRPC) | 🟡 LEGACY | Required by cluster-service |

**Note:** Parallel deployment is OPTIONAL. Recommended approach:
1. Stop cluster-service completely
2. Deploy ras-adapter on 8088
3. Test thoroughly (smoke tests)
4. If issues found → rollback to cluster-service

### 2.2 Routing Strategy

**Worker → RAS Adapter routing:**

**No changes needed to Worker code!** Worker uses Redis Pub/Sub channels, which are service-agnostic:

```go
// Worker publishes command (go-services/worker/internal/statemachine/handlers.go)
sm.publishCommand(ctx, "commands:cluster-service:infobase:lock", payload)

// RAS Adapter subscribes to same channel (ras-adapter/internal/eventhandlers/lock_handler.go)
subscriber.Subscribe(ctx, "commands:cluster-service:infobase:lock")

// RAS Adapter publishes event
publisher.Publish(ctx, "events:cluster-service:infobase:locked", result)

// Worker receives event (go-services/worker/internal/statemachine/state_machine.go)
sm.waitForEvent(ctx, "events:cluster-service:infobase:locked")
```

**Routing diagram:**
```
┌──────────┐
│  Worker  │
└────┬─────┘
     │ PUBLISH: commands:cluster-service:infobase:lock
     ▼
┌────────────┐
│   Redis    │
│  Pub/Sub   │
└──┬─────┬───┘
   │     │
   │     └──────────────────────┐
   │                            │
   ▼ SUBSCRIBE                  ▼ SUBSCRIBE (if parallel deployment)
┌──────────────┐          ┌──────────────────┐
│ ras-adapter  │          │ cluster-service  │
│ (port 8088)  │          │ (port 8089)      │
└──────┬───────┘          └──────────────────┘
       │ PUBLISH: events:cluster-service:infobase:locked
       ▼
   ┌────────────┐
   │   Redis    │
   └────┬───────┘
        │ SUBSCRIBE
        ▼
   ┌──────────┐
   │  Worker  │
   └──────────┘
```

**Critical:** If parallel deployment with both services subscribing to same Redis channels:
- ✅ Both services will receive command
- ✅ Both services will publish event
- ⚠️ Worker will receive **duplicate events** (locked, locked)
- ❌ This can cause state machine issues

**Solution:** If parallel deployment needed:
1. **Use only ras-adapter** (stop cluster-service)
2. **OR use different Redis channels** (requires Worker code change - NOT RECOMMENDED)

**Recommendation: SINGLE SERVICE DEPLOYMENT** (no parallel)

### 2.3 Comparison Testing

**Goal:** Compare old architecture (cluster-service → ras-grpc-gw) vs new (ras-adapter)

**Methodology:**

1. **Baseline measurement** (BEFORE cutover):
   ```bash
   # Ensure cluster-service is running on 8088
   curl http://localhost:8088/health

   # Run benchmark
   cd /c/1CProject/command-center-1c/go-services/cluster-service
   go test -bench=. -benchtime=10s ./...

   # Save results
   go test -bench=. -benchtime=10s ./... > baseline_cluster_service.txt
   ```

2. **New implementation measurement** (AFTER deployment):
   ```bash
   # Ensure ras-adapter is running on 8088
   curl http://localhost:8088/health

   # Run benchmark (same tests)
   cd /c/1CProject/command-center-1c/go-services/ras-adapter
   go test -bench=. -benchtime=10s ./...

   # Save results
   go test -bench=. -benchtime=10s ./... > benchmark_ras_adapter.txt
   ```

3. **Manual timing comparison**:
   ```bash
   # Test Lock/Unlock latency

   # OLD (cluster-service on 8089):
   time curl -X POST http://localhost:8089/api/v1/infobases/{id}/lock \
     -H "Content-Type: application/json" \
     -d '{"cluster_id": "..."}'

   # NEW (ras-adapter on 8088):
   time curl -X POST http://localhost:8088/api/v1/infobases/{id}/lock \
     -H "Content-Type: application/json" \
     -d '{"cluster_id": "..."}'
   ```

4. **Load testing** (Apache Bench):
   ```bash
   # Prepare test data
   cat > lock_payload.json << EOF
   {
     "cluster_id": "00000000-0000-0000-0000-000000000000",
     "infobase_id": "11111111-1111-1111-1111-111111111111"
   }
   EOF

   # OLD architecture
   ab -n 100 -c 10 -p lock_payload.json -T application/json \
     http://localhost:8089/api/v1/infobases/11111111-1111-1111-1111-111111111111/lock

   # NEW architecture
   ab -n 100 -c 10 -p lock_payload.json -T application/json \
     http://localhost:8088/api/v1/infobases/11111111-1111-1111-1111-111111111111/lock
   ```

5. **Metrics comparison table**:

| Metric | OLD (cluster-service) | NEW (ras-adapter) | Improvement |
|--------|----------------------|-------------------|-------------|
| Lock Latency P50 | TBD | TBD | TBD |
| Lock Latency P95 | TBD | TBD | TBD |
| Lock Latency P99 | TBD | TBD | TBD |
| Success Rate (100 requests) | TBD | TBD | TBD |
| Network Hops | 2 | 1 | -50% |
| Services Count | 7 | 6 | -14% |
| Throughput (ops/min) | TBD | TBD | TBD |

**Expected results:**
- ✅ Latency P95: **30-50% reduction** (one less network hop)
- ✅ Success Rate: **> 99%** (same or better)
- ✅ Throughput: **same or higher**

---

## 3. Smoke Testing Strategy

### 3.1 Critical Tests

**Minimum validation before cutover:**

| # | Test | Type | Expected Result | Critical |
|---|------|------|-----------------|----------|
| 1 | Health check | REST API | 200 OK | ✅ YES |
| 2 | GET /clusters | REST API | List of clusters | ✅ YES |
| 3 | GET /infobases | REST API | List of infobases | ✅ YES |
| 4 | POST /lock | REST API | 200 OK, ScheduledJobsDeny=true | ✅ YES |
| 5 | POST /unlock | REST API | 200 OK, ScheduledJobsDeny=false | ✅ YES |
| 6 | POST /terminate | REST API | 200 OK, sessions closed | 🟡 NO (Week 5) |
| 7 | Redis Pub/Sub Lock | Event Handler | Event published | ✅ YES |
| 8 | Redis Pub/Sub Unlock | Event Handler | Event published | ✅ YES |
| 9 | End-to-End workflow | Integration | Lock → Verify → Unlock | ✅ YES |
| 10 | Concurrent requests | Load Test | 10 parallel locks succeed | ✅ YES |

**Total critical tests: 8** (excluding Terminate sessions - Week 5 task)

### 3.2 Test Scenarios

#### Test 1: Health Check

**Purpose:** Verify service is running and responsive

```bash
curl http://localhost:8088/health

# Expected response:
# {
#   "status": "ok",
#   "service": "ras-adapter",
#   "version": "v1.0.0",
#   "uptime": "5m30s",
#   "ras_connected": true
# }
```

**Success criteria:**
- ✅ HTTP 200 OK
- ✅ `status: "ok"`
- ✅ `ras_connected: true`

#### Test 2: GET /clusters

**Purpose:** Verify RAS connection and cluster enumeration

```bash
curl "http://localhost:8088/api/v1/clusters?server=localhost:1545"

# Expected response:
# {
#   "clusters": [
#     {
#       "id": "00000000-0000-0000-0000-000000000000",
#       "name": "Local cluster",
#       "host": "localhost",
#       "port": 1541
#     }
#   ]
# }
```

**Success criteria:**
- ✅ HTTP 200 OK
- ✅ At least 1 cluster returned
- ✅ Cluster has valid UUID

#### Test 3: GET /infobases

**Purpose:** Verify infobase enumeration

```bash
# Get cluster ID from Test 2
CLUSTER_ID="00000000-0000-0000-0000-000000000000"

curl "http://localhost:8088/api/v1/infobases?cluster_id=${CLUSTER_ID}"

# Expected response:
# {
#   "infobases": [
#     {
#       "id": "11111111-1111-1111-1111-111111111111",
#       "name": "accounting",
#       "descr": "Бухгалтерия 3.0",
#       "scheduled_jobs_deny": false
#     }
#   ]
# }
```

**Success criteria:**
- ✅ HTTP 200 OK
- ✅ At least 1 infobase returned
- ✅ Infobase has valid UUID
- ✅ `scheduled_jobs_deny` field present

#### Test 4: POST /lock (REST API)

**Purpose:** Verify Lock functionality via REST API

```bash
CLUSTER_ID="00000000-0000-0000-0000-000000000000"
INFOBASE_ID="11111111-1111-1111-1111-111111111111"

# Lock infobase
curl -X POST "http://localhost:8088/api/v1/infobases/${INFOBASE_ID}/lock" \
  -H "Content-Type: application/json" \
  -d "{\"cluster_id\": \"${CLUSTER_ID}\"}"

# Expected response:
# {
#   "status": "success",
#   "message": "Infobase locked successfully",
#   "infobase_id": "11111111-1111-1111-1111-111111111111",
#   "scheduled_jobs_deny": true
# }

# Verify lock applied
curl "http://localhost:8088/api/v1/infobases?cluster_id=${CLUSTER_ID}" | \
  jq ".infobases[] | select(.id == \"${INFOBASE_ID}\") | .scheduled_jobs_deny"

# Expected: true
```

**Success criteria:**
- ✅ HTTP 200 OK
- ✅ `status: "success"`
- ✅ Verification query returns `scheduled_jobs_deny: true`

#### Test 5: POST /unlock (REST API)

**Purpose:** Verify Unlock functionality via REST API

```bash
CLUSTER_ID="00000000-0000-0000-0000-000000000000"
INFOBASE_ID="11111111-1111-1111-1111-111111111111"

# Unlock infobase
curl -X POST "http://localhost:8088/api/v1/infobases/${INFOBASE_ID}/unlock" \
  -H "Content-Type: application/json" \
  -d "{\"cluster_id\": \"${CLUSTER_ID}\"}"

# Expected response:
# {
#   "status": "success",
#   "message": "Infobase unlocked successfully",
#   "infobase_id": "11111111-1111-1111-1111-111111111111",
#   "scheduled_jobs_deny": false
# }

# Verify unlock applied
curl "http://localhost:8088/api/v1/infobases?cluster_id=${CLUSTER_ID}" | \
  jq ".infobases[] | select(.id == \"${INFOBASE_ID}\") | .scheduled_jobs_deny"

# Expected: false
```

**Success criteria:**
- ✅ HTTP 200 OK
- ✅ `status: "success"`
- ✅ Verification query returns `scheduled_jobs_deny: false`

#### Test 6: Redis Pub/Sub Lock (Event Handler)

**Purpose:** Verify Lock via Redis Pub/Sub (Worker integration)

**Terminal 1 (subscriber - listen for event):**
```bash
redis-cli SUBSCRIBE "events:cluster-service:infobase:locked"

# Expected output after Test 6 Terminal 2:
# 1) "message"
# 2) "events:cluster-service:infobase:locked"
# 3) "{\"cluster_id\":\"...\",\"infobase_id\":\"...\",\"status\":\"success\",\"scheduled_jobs_deny\":true}"
```

**Terminal 2 (publisher - send command):**
```bash
CLUSTER_ID="00000000-0000-0000-0000-000000000000"
INFOBASE_ID="11111111-1111-1111-1111-111111111111"

redis-cli PUBLISH "commands:cluster-service:infobase:lock" \
  "{\"cluster_id\":\"${CLUSTER_ID}\",\"infobase_id\":\"${INFOBASE_ID}\"}"

# Expected: (integer) 1
# (1 subscriber received the message)
```

**Success criteria:**
- ✅ Terminal 1 receives event `events:cluster-service:infobase:locked`
- ✅ Event payload contains `status: "success"`
- ✅ Event payload contains `scheduled_jobs_deny: true`

#### Test 7: Redis Pub/Sub Unlock (Event Handler)

**Purpose:** Verify Unlock via Redis Pub/Sub

**Terminal 1 (subscriber):**
```bash
redis-cli SUBSCRIBE "events:cluster-service:infobase:unlocked"
```

**Terminal 2 (publisher):**
```bash
CLUSTER_ID="00000000-0000-0000-0000-000000000000"
INFOBASE_ID="11111111-1111-1111-1111-111111111111"

redis-cli PUBLISH "commands:cluster-service:infobase:unlock" \
  "{\"cluster_id\":\"${CLUSTER_ID}\",\"infobase_id\":\"${INFOBASE_ID}\"}"

# Expected: (integer) 1
```

**Success criteria:**
- ✅ Terminal 1 receives event `events:cluster-service:infobase:unlocked`
- ✅ Event payload contains `status: "success"`
- ✅ Event payload contains `scheduled_jobs_deny: false`

#### Test 8: End-to-End Workflow

**Purpose:** Verify complete Lock → Verify → Unlock workflow

```bash
#!/bin/bash
# test-lock-unlock-workflow.sh

set -e

CLUSTER_ID="00000000-0000-0000-0000-000000000000"
INFOBASE_ID="11111111-1111-1111-1111-111111111111"
BASE_URL="http://localhost:8088"

echo "=== End-to-End Lock/Unlock Workflow Test ==="

# Step 1: Get initial state
echo "Step 1: Get initial state..."
INITIAL_STATE=$(curl -s "${BASE_URL}/api/v1/infobases?cluster_id=${CLUSTER_ID}" | \
  jq -r ".infobases[] | select(.id == \"${INFOBASE_ID}\") | .scheduled_jobs_deny")
echo "Initial ScheduledJobsDeny: ${INITIAL_STATE}"

# Step 2: Lock infobase
echo "Step 2: Lock infobase..."
LOCK_RESULT=$(curl -s -X POST "${BASE_URL}/api/v1/infobases/${INFOBASE_ID}/lock" \
  -H "Content-Type: application/json" \
  -d "{\"cluster_id\": \"${CLUSTER_ID}\"}")
echo "Lock result: ${LOCK_RESULT}"

# Step 3: Verify lock applied
echo "Step 3: Verify lock applied..."
LOCKED_STATE=$(curl -s "${BASE_URL}/api/v1/infobases?cluster_id=${CLUSTER_ID}" | \
  jq -r ".infobases[] | select(.id == \"${INFOBASE_ID}\") | .scheduled_jobs_deny")
echo "Locked ScheduledJobsDeny: ${LOCKED_STATE}"

if [ "$LOCKED_STATE" != "true" ]; then
  echo "❌ FAIL: Lock not applied (expected true, got ${LOCKED_STATE})"
  exit 1
fi

# Step 4: Unlock infobase
echo "Step 4: Unlock infobase..."
UNLOCK_RESULT=$(curl -s -X POST "${BASE_URL}/api/v1/infobases/${INFOBASE_ID}/unlock" \
  -H "Content-Type: application/json" \
  -d "{\"cluster_id\": \"${CLUSTER_ID}\"}")
echo "Unlock result: ${UNLOCK_RESULT}"

# Step 5: Verify unlock applied
echo "Step 5: Verify unlock applied..."
UNLOCKED_STATE=$(curl -s "${BASE_URL}/api/v1/infobases?cluster_id=${CLUSTER_ID}" | \
  jq -r ".infobases[] | select(.id == \"${INFOBASE_ID}\") | .scheduled_jobs_deny")
echo "Unlocked ScheduledJobsDeny: ${UNLOCKED_STATE}"

if [ "$UNLOCKED_STATE" != "false" ]; then
  echo "❌ FAIL: Unlock not applied (expected false, got ${UNLOCKED_STATE})"
  exit 1
fi

echo "✅ SUCCESS: End-to-End workflow passed"
```

**Success criteria:**
- ✅ Lock applied: `scheduled_jobs_deny: true`
- ✅ Unlock applied: `scheduled_jobs_deny: false`
- ✅ No errors during workflow

#### Test 9: Concurrent Requests

**Purpose:** Verify system handles parallel lock requests

```bash
#!/bin/bash
# test-concurrent-locks.sh

set -e

CLUSTER_ID="00000000-0000-0000-0000-000000000000"
BASE_URL="http://localhost:8088"

echo "=== Concurrent Lock Requests Test ==="

# Get list of infobases
INFOBASES=$(curl -s "${BASE_URL}/api/v1/infobases?cluster_id=${CLUSTER_ID}" | \
  jq -r '.infobases[].id' | head -10)

# Lock 10 infobases in parallel
echo "Locking 10 infobases in parallel..."

for INFOBASE_ID in $INFOBASES; do
  curl -s -X POST "${BASE_URL}/api/v1/infobases/${INFOBASE_ID}/lock" \
    -H "Content-Type: application/json" \
    -d "{\"cluster_id\": \"${CLUSTER_ID}\"}" &
done

# Wait for all background jobs
wait

echo "✅ All 10 lock requests completed"

# Verify all locked
echo "Verifying locks applied..."
LOCKED_COUNT=$(curl -s "${BASE_URL}/api/v1/infobases?cluster_id=${CLUSTER_ID}" | \
  jq '[.infobases[] | select(.scheduled_jobs_deny == true)] | length')

echo "Locked infobases: ${LOCKED_COUNT} / 10"

if [ "$LOCKED_COUNT" -ge 8 ]; then
  echo "✅ SUCCESS: At least 8/10 infobases locked"
else
  echo "❌ FAIL: Only ${LOCKED_COUNT}/10 infobases locked"
  exit 1
fi
```

**Success criteria:**
- ✅ At least 8/10 parallel requests succeed
- ✅ No crashes or panics
- ✅ Latency P95 < 2s

### 3.3 Success Criteria

**Minimum passing threshold:**

| Category | Test | Passing Criteria |
|----------|------|------------------|
| **REST API** | Health, Clusters, Infobases | 100% pass rate |
| **REST API** | Lock, Unlock | 100% pass rate |
| **Event Handlers** | Lock, Unlock via Redis | 100% pass rate |
| **Integration** | End-to-End workflow | 100% pass rate |
| **Load** | Concurrent requests | > 80% success rate |
| **Performance** | Lock/Unlock Latency P95 | < 2s |

**GATE CONDITION:** ALL critical tests must PASS before cutover to production.

---

## 4. Performance Comparison

### 4.1 Metrics to Measure

**Primary Metrics:**

| Metric | Description | Measurement Method | Target |
|--------|-------------|-------------------|--------|
| **Lock Latency P50** | Median lock operation time | Benchmark, Apache Bench | < 500ms |
| **Lock Latency P95** | 95th percentile lock time | Benchmark, Apache Bench | < 2s |
| **Lock Latency P99** | 99th percentile lock time | Benchmark, Apache Bench | < 5s |
| **Unlock Latency P50** | Median unlock operation time | Benchmark, Apache Bench | < 500ms |
| **Success Rate** | % of successful operations | Manual testing, Load test | > 99% |
| **Throughput** | Operations per minute | Apache Bench, Vegeta | > 100 ops/min |

**Secondary Metrics:**

| Metric | Description | Measurement Method |
|--------|-------------|-------------------|
| **Network Hops** | Worker → RAS hops count | Architecture review |
| **Services Count** | Total services running | Process count |
| **Memory Usage** | RAS Adapter RSS | `ps aux`, Prometheus |
| **CPU Usage** | RAS Adapter CPU % | `top`, Prometheus |

### 4.2 Testing Tools

**Option 1: Go Benchmark (preferred)**

```bash
cd /c/1CProject/command-center-1c/go-services/ras-adapter

# Run all benchmarks
go test -bench=. -benchtime=10s ./...

# Run specific benchmark
go test -bench=BenchmarkLockUnlock -benchtime=10s ./tests/integration

# Save results
go test -bench=. -benchtime=10s ./... > benchmark_results.txt
```

**Option 2: Apache Bench (HTTP load testing)**

```bash
# Prepare test payload
cat > lock_payload.json << EOF
{
  "cluster_id": "00000000-0000-0000-0000-000000000000"
}
EOF

# Run 100 requests, 10 concurrent
ab -n 100 -c 10 -p lock_payload.json -T application/json \
  http://localhost:8088/api/v1/infobases/11111111-1111-1111-1111-111111111111/lock

# Output includes:
# - Time per request (mean, median)
# - Requests per second
# - Percentage served within X ms
```

**Option 3: Manual timing (curl + time)**

```bash
# Measure single request latency
time curl -X POST http://localhost:8088/api/v1/infobases/{id}/lock \
  -H "Content-Type: application/json" \
  -d '{"cluster_id": "..."}'

# Run 10 times, calculate P50/P95
for i in {1..10}; do
  time curl -s -X POST http://localhost:8088/api/v1/infobases/{id}/lock \
    -H "Content-Type: application/json" \
    -d '{"cluster_id": "..."}' > /dev/null
done 2>&1 | grep real
```

### 4.3 Benchmarking Methodology

**Step 1: Baseline (OLD architecture)**

1. Ensure cluster-service + ras-grpc-gw running
2. Run benchmark suite
3. Save results to `baseline_cluster_service.txt`

**Step 2: New implementation (RAS Adapter)**

1. Stop cluster-service, start ras-adapter
2. Run **same** benchmark suite
3. Save results to `benchmark_ras_adapter.txt`

**Step 3: Comparison**

```bash
# Compare results
benchstat baseline_cluster_service.txt benchmark_ras_adapter.txt

# Expected output:
# name              old time/op  new time/op  delta
# LockUnlock-8      1.50s ± 2%   0.90s ± 3%  -40.00%  (p=0.000 n=10+10)
```

**Step 4: Document findings**

Create report: `WEEK4_PERFORMANCE_COMPARISON.md`

---

## 5. Cutover Strategy

### 5.1 Validation Checklist (Pre-Cutover)

**MUST PASS ALL before cutover:**

```bash
# ========================================
# RAS Adapter Production Readiness Checklist
# ========================================

## Infrastructure
- [ ] PostgreSQL running (docker ps | grep postgres)
- [ ] Redis running (docker exec -it redis redis-cli ping)
- [ ] 1C RAS server available (telnet localhost 1545)
- [ ] RAS Adapter binary built (ls -lh bin/cc1c-ras-adapter.exe)
- [ ] Environment variables configured (.env.local)

## Service Health
- [ ] RAS Adapter starts successfully
- [ ] Health check returns 200 OK (curl http://localhost:8088/health)
- [ ] RAS connection pool initialized (check logs)
- [ ] Redis Pub/Sub connected (check logs)
- [ ] No errors in logs (tail -f logs/ras-adapter.log)

## Functional Tests
- [ ] GET /clusters works (returns cluster list)
- [ ] GET /infobases works (returns infobase list)
- [ ] POST /lock works (ScheduledJobsDeny=true)
- [ ] POST /unlock works (ScheduledJobsDeny=false)
- [ ] Redis Pub/Sub Lock works (event published)
- [ ] Redis Pub/Sub Unlock works (event published)
- [ ] End-to-End workflow passes (Lock → Verify → Unlock)

## Performance Tests
- [ ] Lock/Unlock Latency P95 < 2s
- [ ] Success rate > 99% (100 requests)
- [ ] Concurrent requests work (10 parallel locks)
- [ ] No memory leaks (run 1000 requests, check RSS)

## 24-Hour Stability
- [ ] RAS Adapter running for 24 hours without crashes
- [ ] No error rate spikes in logs
- [ ] No memory growth (RSS stable)
- [ ] No file descriptor leaks (lsof | grep ras-adapter)

## Worker Integration
- [ ] Worker can publish commands (commands:cluster-service:infobase:lock)
- [ ] Worker receives events (events:cluster-service:infobase:locked)
- [ ] No event loss (all commands produce events)

## Rollback Readiness
- [ ] cluster-service binary available (bin/cc1c-cluster-service.exe)
- [ ] ras-grpc-gw available (../ras-grpc-gw/bin/)
- [ ] Rollback procedure documented
- [ ] Rollback tested (switch back to cluster-service works)

## Documentation
- [ ] CLAUDE.md updated (ras-adapter in service list)
- [ ] README.md updated (architecture diagram)
- [ ] scripts/dev/README.md updated (ras-adapter commands)
- [ ] RAS_ADAPTER_ROADMAP.md updated (Week 4 status)

## Sign-off
Validated by: _________________________
Date: _________________________
Status: [ ] ✅ READY FOR CUTOVER   [ ] ❌ NOT READY

Blockers (if not ready):
_________________________________________
_________________________________________
```

**If ANY checklist item FAILS → DO NOT proceed to cutover!**

### 5.2 Deprecation Steps

**Cutover Timeline:** 30 minutes

#### Step 1: Stop Worker (5 min)

**Purpose:** Prevent Worker from sending commands during cutover

```bash
# Stop Worker
./scripts/dev/stop-all.sh

# Verify Worker stopped
ps aux | grep cc1c-worker
# Expected: no processes
```

#### Step 2: Stop cluster-service and ras-grpc-gw (5 min)

```bash
# Stop cluster-service
kill $(cat pids/cluster-service.pid)
rm pids/cluster-service.pid

# Verify stopped
curl http://localhost:8088/health
# Expected: connection refused

# Stop ras-grpc-gw
cd ../ras-grpc-gw
./stop.sh
# или
kill $(cat ras-grpc-gw.pid)

# Verify stopped
curl http://localhost:8081/health
# Expected: connection refused
```

#### Step 3: Start RAS Adapter (5 min)

```bash
cd /c/1CProject/command-center-1c

# Ensure ras-adapter configured in start-all.sh (see Section 1.3)

# Start RAS Adapter
./scripts/dev/start-all.sh

# Verify RAS Adapter started
curl http://localhost:8088/health
# Expected: 200 OK, {"status":"ok"}

# Check logs
tail -f logs/ras-adapter.log
# Expected: "HTTP server listening on 0.0.0.0:8088"
```

#### Step 4: Start Worker (5 min)

```bash
# Worker already started by start-all.sh, but verify
ps aux | grep cc1c-worker

# Check Worker logs
tail -f logs/worker.log
# Expected: "Worker started", "Redis connected"
```

#### Step 5: Smoke Test (5 min)

```bash
# Quick smoke test
./test-lock-unlock-workflow.sh
# Expected: ✅ SUCCESS

# Check Worker can send commands
redis-cli PUBLISH "commands:cluster-service:infobase:lock" \
  '{"cluster_id":"...","infobase_id":"..."}'

# Listen for event
redis-cli SUBSCRIBE "events:cluster-service:infobase:locked"
# Expected: event received
```

#### Step 6: Archive old services (5 min)

```bash
# Create archive directory
mkdir -p go-services/archive

# Move cluster-service
git mv go-services/cluster-service go-services/archive/cluster-service

# Add deprecation notice
cat > go-services/archive/cluster-service/README.md << EOF
# cluster-service (DEPRECATED)

**Status:** ⛔ DEPRECATED as of 2025-11-20
**Replaced by:** ras-adapter

This service has been replaced by RAS Adapter.
Do not use in production.

## Reason for deprecation
- Removed middleman (ras-grpc-gw) → reduced network hops
- Direct RAS protocol integration (khorevaa/ras-client)
- Simplified architecture (6 services instead of 7)

## Migration guide
See: docs/roadmaps/WEEK4_DEPLOY_VALIDATE_PLAN.md
EOF

# Commit changes
git add go-services/archive/cluster-service
git commit -m "chore: Deprecate cluster-service, replaced by ras-adapter"
```

**Note:** Do NOT delete ras-grpc-gw repository (external fork). Just stop using it.

### 5.3 Rollback Plan

**If cutover FAILS → rollback to cluster-service**

**Rollback Timeline:** 15 minutes

#### Step 1: Stop RAS Adapter

```bash
kill $(cat pids/ras-adapter.pid)
rm pids/ras-adapter.pid
```

#### Step 2: Restore cluster-service

```bash
# If archived
git mv go-services/archive/cluster-service go-services/cluster-service

# Or use binary directly
export SERVER_PORT=8088
nohup bin/cc1c-cluster-service.exe > logs/cluster-service.log 2>&1 &
echo $! > pids/cluster-service.pid
```

#### Step 3: Start ras-grpc-gw

```bash
cd ../ras-grpc-gw
./start.sh
# or
nohup ./bin/ras-grpc-gw.exe localhost:1545 > ras-grpc-gw.log 2>&1 &
```

#### Step 4: Restart Worker

```bash
./scripts/dev/restart.sh worker
```

#### Step 5: Verify rollback

```bash
# Check cluster-service
curl http://localhost:8088/health

# Check ras-grpc-gw
curl http://localhost:8081/health

# Test Lock/Unlock
curl -X POST http://localhost:8088/api/v1/infobases/{id}/lock \
  -H "Content-Type: application/json" \
  -d '{"cluster_id": "..."}'
```

**Rollback triggers:**
- ❌ RAS Adapter crashes repeatedly
- ❌ Lock/Unlock operations fail > 10%
- ❌ Worker cannot connect to RAS Adapter
- ❌ Performance degradation > 50%

**Rollback decision:** Tech Lead or Senior Developer

---

## 6. Documentation Updates

### 6.1 Critical Files

**Must update BEFORE cutover:**

| File | Changes | Priority |
|------|---------|----------|
| **CLAUDE.md** | Replace cluster-service with ras-adapter | ✅ HIGH |
| **scripts/dev/start-all.sh** | Add ras-adapter startup | ✅ HIGH |
| **scripts/dev/stop-all.sh** | Add ras-adapter shutdown | ✅ HIGH |
| **scripts/dev/restart-all.sh** | Add ras-adapter restart | ✅ HIGH |
| **scripts/dev/health-check.sh** | Add ras-adapter health check | ✅ HIGH |
| **RAS_ADAPTER_ROADMAP.md** | Mark Week 4 as DONE | ✅ HIGH |
| **README.md** | Update architecture diagram | 🟡 MEDIUM |
| **docs/architecture/README.md** | Update service list | 🟡 MEDIUM |
| **.env.local.example** | Add RAS_* variables | 🟡 MEDIUM |

**Can update AFTER cutover:**

| File | Changes | Priority |
|------|---------|----------|
| **docker-compose.local.yml** | Add comment: cluster-service deprecated | 🟢 LOW |
| **go-services/README.md** | Update service list | 🟢 LOW |
| **docs/START_HERE.md** | Update quick start | 🟢 LOW |

### 6.2 Deployment Guide Format

**Create:** `docs/deployment/RAS_ADAPTER_DEPLOYMENT_GUIDE.md`

**Contents:**

```markdown
# RAS Adapter Deployment Guide

## Overview
This guide covers deployment of RAS Adapter to development environment.

## Prerequisites
- PostgreSQL running (port 5432)
- Redis running (port 6379)
- 1C RAS server available (port 1545)
- Go 1.21+ installed
- .env.local configured

## Deployment Steps

### 1. Build Binary
[Copy from Section 1.3, Phase 1]

### 2. Configure Environment
[List required variables]

### 3. Start Service
[Copy from Section 1.3, Phase 2]

### 4. Verify Deployment
[Copy smoke tests from Section 3]

## Troubleshooting

### Service won't start
[Common issues and solutions]

### Lock/Unlock fails
[Debugging steps]

## Rollback Procedure
[Copy from Section 5.3]

## Monitoring
[Metrics to watch]

## Support
[Contact info]
```

### 6.3 CLAUDE.md Updates

**File:** `CLAUDE.md`

**Section:** "🔌 Критичные сервисы"

**BEFORE:**
```markdown
| Service | Назначение | Протокол | Use Case |
|---------|------------|----------|----------|
| **cluster-service** | Мониторинг кластеров | gRPC → RAS | Чтение метаданных, real-time мониторинг |
| **batch-service** | Управление конфигурациями | subprocess → 1cv8.exe | Установка расширений, batch операции |
| **ras-grpc-gw** | Gateway для RAS | gRPC ↔ RAS binary | Прокси для cluster-service |
```

**AFTER:**
```markdown
| Service | Назначение | Протокол | Use Case |
|---------|------------|----------|----------|
| **ras-adapter** | Мониторинг и управление кластерами | Direct RAS protocol | Lock/Unlock, sessions, real-time monitoring |
| **batch-service** | Управление конфигурациями | subprocess → 1cv8.exe | Установка расширений, batch операции |
| ~~**cluster-service**~~ | ⛔ DEPRECATED (replaced by ras-adapter) | - | - |
| ~~**ras-grpc-gw**~~ | ⛔ DEPRECATED (no longer needed) | - | - |
```

**Section:** "Доступные сервисы"

**BEFORE:**
```markdown
- `orchestrator`, `celery-worker`, `celery-beat` (Python/Django)
- `api-gateway`, `worker`, `cluster-service` (Go)
- `frontend` (React)
- ras-grpc-gw (внешний, в ../ras-grpc-gw)
```

**AFTER:**
```markdown
- `orchestrator`, `celery-worker`, `celery-beat` (Python/Django)
- `api-gateway`, `worker`, `ras-adapter` (Go)
- `frontend` (React)
```

**Section:** "Endpoints для проверки"

**BEFORE:**
```markdown
- Cluster Service: http://localhost:8088/health
- ras-grpc-gw: http://localhost:8081/health (gRPC: 9999)
```

**AFTER:**
```markdown
- RAS Adapter: http://localhost:8088/health
```

---

## 7. Task Breakdown

### 7.1 Day 1: Deployment (4 hours)

**Morning (2 hours):**

| Task | Effort | Owner | Deliverable |
|------|--------|-------|-------------|
| Build ras-adapter binary | 10 min | Dev | `bin/cc1c-ras-adapter.exe` |
| Verify environment variables | 10 min | Dev | `.env.local` configured |
| Update start-all.sh | 20 min | Dev | Script with ras-adapter |
| Deploy ras-adapter to host | 10 min | Dev | Service running on 8088 |
| Health check | 5 min | Dev | 200 OK response |
| **Break** | 15 min | - | - |
| Update stop-all.sh, restart-all.sh | 20 min | Dev | Scripts updated |
| Update health-check.sh | 10 min | Dev | Health check includes ras-adapter |
| Test restart cycle | 10 min | Dev | Stop → Start works |
| **Lunch** | 30 min | - | - |

**Afternoon (2 hours):**

| Task | Effort | Owner | Deliverable |
|------|--------|-------|-------------|
| Run smoke tests (Tests 1-3) | 30 min | Dev | REST API validated |
| Run smoke tests (Tests 4-5) | 30 min | Dev | Lock/Unlock validated |
| Run smoke tests (Tests 6-7) | 30 min | Dev | Redis Pub/Sub validated |
| Run smoke tests (Tests 8-9) | 20 min | Dev | E2E + Concurrent validated |
| Document test results | 10 min | Dev | Test report |

**Day 1 Deliverables:**
- ✅ RAS Adapter deployed and running
- ✅ All smoke tests PASSED
- ✅ Scripts updated (start, stop, restart, health-check)

### 7.2 Day 2: Validation (4 hours)

**Morning (2 hours):**

| Task | Effort | Owner | Deliverable |
|------|--------|-------|-------------|
| Run baseline benchmarks (cluster-service) | 30 min | Dev | `baseline_cluster_service.txt` |
| Stop cluster-service, start ras-adapter | 10 min | Dev | Services switched |
| Run new benchmarks (ras-adapter) | 30 min | Dev | `benchmark_ras_adapter.txt` |
| Compare results (benchstat) | 15 min | Dev | Comparison report |
| **Break** | 15 min | - | - |
| Load testing (Apache Bench) | 20 min | Dev | Performance metrics |

**Afternoon (2 hours):**

| Task | Effort | Owner | Deliverable |
|------|--------|-------|-------------|
| Document performance comparison | 30 min | Dev | `WEEK4_PERFORMANCE_COMPARISON.md` |
| 24-hour stability monitoring setup | 20 min | Dev | Logs rotating, alerts configured |
| **DECISION GATE: Cutover or Rollback?** | 10 min | Tech Lead | GO/NO-GO decision |
| **If GO:** Execute cutover | 30 min | Dev | Old services stopped |
| **If NO-GO:** Document blockers | 30 min | Dev | Issue list |

**Day 2 Deliverables:**
- ✅ Performance comparison complete
- ✅ Cutover decision made
- ✅ If GO: Old services deprecated
- ✅ If NO-GO: Blockers documented

### 7.3 Day 3: Documentation & Validation (3 hours)

**Morning (2 hours):**

| Task | Effort | Owner | Deliverable |
|------|--------|-------|-------------|
| Update CLAUDE.md | 20 min | Dev | Service list updated |
| Update README.md | 20 min | Dev | Architecture diagram updated |
| Update RAS_ADAPTER_ROADMAP.md | 10 min | Dev | Week 4 marked DONE |
| Create deployment guide | 40 min | Dev | `RAS_ADAPTER_DEPLOYMENT_GUIDE.md` |
| **Break** | 15 min | - | - |
| Update .env.local.example | 10 min | Dev | RAS_* variables added |
| Git commit: deprecate cluster-service | 15 min | Dev | Archive commit |

**Afternoon (1 hour):**

| Task | Effort | Owner | Deliverable |
|------|--------|-------|-------------|
| Final smoke test (after 24h stability) | 20 min | Dev | All tests PASSED |
| Sign-off validation checklist | 10 min | Tech Lead | ✅ PRODUCTION READY |
| Create handover document | 20 min | Dev | Week 4 summary |
| Update sprint board | 10 min | PM | Week 4 → DONE |

**Day 3 Deliverables:**
- ✅ All documentation updated
- ✅ cluster-service archived
- ✅ Production readiness validated
- ✅ Week 4 COMPLETE

### 7.4 Total Timeline

**Total Effort:** 11 hours (1.5 days)
**Total Calendar Time:** 3 days (with stability monitoring)

**Critical Path:**
1. Deploy ras-adapter (Day 1 morning)
2. Smoke tests (Day 1 afternoon)
3. Performance validation (Day 2 morning)
4. Cutover decision (Day 2 afternoon)
5. Documentation (Day 3)

**Milestones:**

| Milestone | Date | Deliverable |
|-----------|------|-------------|
| M1: RAS Adapter deployed | Day 1 EOD | Service running, smoke tests PASSED |
| M2: Performance validated | Day 2 12:00 | Benchmarks complete, comparison done |
| M3: Cutover complete | Day 2 EOD | Old services stopped, ras-adapter primary |
| M4: Documentation complete | Day 3 EOD | All docs updated, Week 4 DONE |

---

## 8. Risks & Mitigation

### 8.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **RAS Adapter crashes in production** | LOW | HIGH | - Comprehensive testing (37+ scenarios)<br>- 24-hour stability monitoring<br>- Rollback plan ready |
| **Performance regression** | LOW | MEDIUM | - Benchmark comparison before cutover<br>- Load testing (100+ requests)<br>- P95 latency < 2s validation |
| **Worker integration issues** | LOW | HIGH | - Same Redis channels as cluster-service<br>- No Worker code changes needed<br>- Integration tests cover Worker flow |
| **1C RAS server unavailable** | MEDIUM | HIGH | - Connection pool with retry logic<br>- Circuit breaker pattern<br>- Graceful degradation |
| **Redis connection loss** | LOW | HIGH | - Redis reconnection logic (Watermill)<br>- Event replay on reconnect<br>- Circuit breaker for Pub/Sub |

### 8.2 Operational Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Deployment script errors** | LOW | MEDIUM | - Test scripts before production<br>- Dry-run mode for start-all.sh<br>- Manual verification steps |
| **Documentation outdated** | MEDIUM | LOW | - Update docs BEFORE cutover<br>- Peer review of CLAUDE.md changes<br>- Version control all docs |
| **Rollback complexity** | LOW | MEDIUM | - Document rollback steps<br>- Test rollback procedure<br>- Keep cluster-service binary |
| **Missing environment variables** | MEDIUM | LOW | - Validate .env.local before start<br>- Default values in config.go<br>- Error messages guide user |

### 8.3 Schedule Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Smoke tests take longer** | MEDIUM | LOW | - Automate tests (bash scripts)<br>- Parallelize where possible<br>- Buffer time in schedule |
| **Performance issues found** | LOW | HIGH | - Week 3 benchmarks as baseline<br>- Early performance validation<br>- Optimize before cutover if needed |
| **24-hour stability fails** | LOW | HIGH | - Monitor logs actively<br>- Set up alerts (Grafana)<br>- Fix issues before cutover |

### 8.4 Mitigation Summary

**Critical Success Factors:**

1. ✅ **Comprehensive testing** - 37+ integration tests, smoke tests, load tests
2. ✅ **Rollback readiness** - cluster-service binary available, rollback procedure documented
3. ✅ **Performance validation** - Benchmark comparison, P95 < 2s requirement
4. ✅ **Zero Worker changes** - Same Redis channels, transparent cutover
5. ✅ **Documentation complete** - CLAUDE.md, deployment guide, troubleshooting

**Contingency Plans:**

| Scenario | Action |
|----------|--------|
| RAS Adapter crashes | Rollback to cluster-service (15 min) |
| Performance regression | Optimize code, delay cutover |
| Worker integration fails | Debug Redis Pub/Sub, verify channels |
| RAS server unavailable | Check RAS service, verify firewall |
| Redis connection issues | Restart Redis, check network |

---

## 9. Success Criteria

**Week 4 is considered SUCCESSFUL if:**

✅ **Functional Requirements:**
- [ ] RAS Adapter deployed to development environment
- [ ] All smoke tests PASSED (8/8 critical tests)
- [ ] REST API works (GET /clusters, /infobases, POST /lock, /unlock)
- [ ] Redis Pub/Sub works (Lock, Unlock event handlers)
- [ ] End-to-End workflow works (Lock → Verify → Unlock)

✅ **Performance Requirements:**
- [ ] Lock/Unlock Latency P95 < 2s
- [ ] Success rate > 99% (100 requests)
- [ ] Throughput > 100 ops/min
- [ ] Performance improvement vs cluster-service (expected 30-50%)

✅ **Stability Requirements:**
- [ ] RAS Adapter runs for 24 hours without crashes
- [ ] No memory leaks (RSS stable)
- [ ] No error rate spikes
- [ ] Graceful shutdown/restart works

✅ **Integration Requirements:**
- [ ] Worker publishes commands successfully
- [ ] Worker receives events successfully
- [ ] No event loss (all commands produce events)
- [ ] Zero Worker code changes needed

✅ **Deprecation Requirements:**
- [ ] cluster-service stopped and archived
- [ ] ras-grpc-gw stopped (no longer needed)
- [ ] Deprecation notices added to archived services
- [ ] Services count reduced (7 → 6)

✅ **Documentation Requirements:**
- [ ] CLAUDE.md updated (service list, endpoints)
- [ ] RAS_ADAPTER_ROADMAP.md updated (Week 4 DONE)
- [ ] Deployment guide created
- [ ] Scripts updated (start-all.sh, stop-all.sh, etc.)
- [ ] Rollback procedure documented

✅ **Validation Requirements:**
- [ ] Production readiness checklist 100% PASSED
- [ ] Performance comparison report created
- [ ] Sign-off obtained from Tech Lead
- [ ] Ready for Week 4.5 (Manual Testing Gate)

**GATE CONDITION for Week 5:** ALL success criteria must be met.

---

## 10. Next Steps (Week 4.5+)

**After Week 4 completion:**

1. **Week 4.5: Manual Testing Gate** (RAS_ADAPTER_ROADMAP.md)
   - Comprehensive manual validation
   - ALL REST endpoints tested
   - ALL event handlers tested
   - Performance validation
   - Sign-off required

2. **Week 5: Terminate Sessions** (if needed)
   - Implement Terminate Sessions NEW (ISessionBase.Close)
   - Replace AdminSession.Terminate calls
   - Integration with Worker State Machine

3. **Production Deployment** (future)
   - Kubernetes manifests (Deployment, Service)
   - Helm charts
   - CI/CD pipeline (GitHub Actions)
   - Production monitoring (Prometheus, Grafana)

---

## Appendix A: Environment Variables Reference

**Required for RAS Adapter:**

```bash
# Server configuration
SERVER_HOST=0.0.0.0                    # HTTP server bind address
SERVER_PORT=8088                       # HTTP server port
SERVER_READ_TIMEOUT=10s                # HTTP read timeout
SERVER_WRITE_TIMEOUT=10s               # HTTP write timeout
SERVER_SHUTDOWN_TIMEOUT=30s            # Graceful shutdown timeout

# RAS configuration
RAS_SERVER_ADDR=localhost:1545         # 1C RAS server address
RAS_CONN_TIMEOUT=5s                    # RAS connection timeout
RAS_REQUEST_TIMEOUT=10s                # RAS request timeout
RAS_MAX_CONNECTIONS=10                 # Connection pool size

# Redis configuration
REDIS_HOST=localhost                   # Redis host
REDIS_PORT=6379                        # Redis port
REDIS_PASSWORD=                        # Redis password (empty for dev)
REDIS_DB=0                             # Redis database number
REDIS_PUBSUB_ENABLED=true              # Enable event handlers

# Monitoring configuration
SESSION_MONITOR_INTERVAL=1s            # Session monitoring interval (future)

# Logging configuration
LOG_LEVEL=info                         # Log level (debug, info, warn, error)
```

---

## Appendix B: Quick Reference Commands

```bash
# ========================================
# RAS Adapter - Quick Reference
# ========================================

# Build binary
cd go-services/ras-adapter
go build -o ../../bin/cc1c-ras-adapter.exe cmd/main.go

# Start all services (includes ras-adapter)
./scripts/dev/start-all.sh

# Stop all services
./scripts/dev/stop-all.sh

# Restart ras-adapter only
./scripts/dev/restart.sh ras-adapter

# Health check
curl http://localhost:8088/health

# Get clusters
curl "http://localhost:8088/api/v1/clusters?server=localhost:1545"

# Get infobases
curl "http://localhost:8088/api/v1/infobases?cluster_id=CLUSTER_UUID"

# Lock infobase
curl -X POST "http://localhost:8088/api/v1/infobases/INFOBASE_UUID/lock" \
  -H "Content-Type: application/json" \
  -d '{"cluster_id": "CLUSTER_UUID"}'

# Unlock infobase
curl -X POST "http://localhost:8088/api/v1/infobases/INFOBASE_UUID/unlock" \
  -H "Content-Type: application/json" \
  -d '{"cluster_id": "CLUSTER_UUID"}'

# View logs
tail -f logs/ras-adapter.log

# Redis Pub/Sub test (Lock)
# Terminal 1:
redis-cli SUBSCRIBE "events:cluster-service:infobase:locked"

# Terminal 2:
redis-cli PUBLISH "commands:cluster-service:infobase:lock" \
  '{"cluster_id":"UUID","infobase_id":"UUID"}'

# Run integration tests
cd go-services/ras-adapter
go test -v ./tests/integration

# Run benchmarks
go test -bench=. -benchtime=10s ./tests/integration

# Load test (Apache Bench)
ab -n 100 -c 10 -p payload.json -T application/json \
  http://localhost:8088/api/v1/infobases/UUID/lock
```

---

**End of Document**

**Version:** 1.0
**Date:** 2025-11-20
**Author:** Senior Software Architect
**Status:** ✅ READY FOR REVIEW

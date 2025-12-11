# Administrative Services Roadmap (backup-service + config-service)

**Version:** 1.0
**Date:** 2025-11-28
**Status:** Draft - Pending Approval
**Total Duration:** 8-10 weeks
**Related:** [batch-service](../../go-services/batch-service/), [ibcmd.md](../ibcmd.md)

---

## Table of Contents

- [Overview](#overview)
- [Architecture Decision](#architecture-decision)
- [Phase 1: backup-service](#phase-1-backup-service)
- [Phase 2: config-service](#phase-2-config-service)
- [Shared Infrastructure](#shared-infrastructure)
- [Success Metrics](#success-metrics)
- [Risk Mitigation](#risk-mitigation)
- [References](#references)

---

## Overview

### Background

Исследование инструментов администрирования 1С выявило две утилиты:

| Инструмент | Назначение | Особенности |
|------------|------------|-------------|
| **ibcmd** | Автономное администрирование БД | Работает без платформы и RAS, многопоточность |
| **AgentMode** | CI/CD конфигураций | Persistent SSH, работа с конфигуратором |

### Design Decision: Разделение по ролям, не по инструментам

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         СЕРВИСЫ ПО РОЛЯМ                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  batch-service            backup-service          config-service        │
│  "Изменение баз"          "Сохранность данных"    "CI/CD конфигураций"  │
│  ✅ EXISTS                🔴 NEW                  🟡 FUTURE             │
│                                                                         │
│  ├── extensions (.cfe)    ├── dump → .dt          ├── export в файлы    │
│  ├── UpdateDBConfig       ├── restore ← .dt       ├── import из файлов  │
│  └── quick operations     └── replicate (DR)      ├── UpdateDBConfig    │
│                                                   └── внешние обработки │
│                                                                         │
│  SLA: <15 сек             SLA: минуты-часы        SLA: секунды-минуты   │
│  Модель: subprocess       Модель: async jobs      Модель: persistent SSH│
│                                                                         │
│  Инструменты:             Инструменты:            Инструменты:          │
│  • 1cv8.exe               • ibcmd.exe             • 1cv8.exe /AgentMode │
│  • ibcmd (быстрые)                                • SSH protocol        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Почему не по инструментам:**
- Разные SLA и модели выполнения
- Разные потребители (Ops vs Dev)
- Независимое масштабирование
- Изоляция отказов

### Goals

1. **backup-service** — Disaster Recovery для 700+ баз 1С
2. **config-service** — CI/CD pipeline для конфигураций (отложен)
3. **Интеграция** с существующей инфраструктурой (Redis, Orchestrator)

### Timeline Summary

```
Phase 1: backup-service (6 weeks)
├── Week 1-2: Core Infrastructure + ibcmd integration
├── Week 3-4: Async Jobs + Storage (S3/MinIO)
└── Week 5-6: API + Integration + Testing

Phase 2: config-service (4 weeks) - DEFERRED
├── Week 7-8: AgentMode SSH Pool
└── Week 9-10: API + VCS Integration

Total: 10 weeks (2.5 months)
Priority: Phase 1 (backup-service) - HIGH
          Phase 2 (config-service) - LOW (on-demand)
```

---

## Architecture Decision

### ADR-001: Separation by Business Role

**Context:**
- ibcmd и AgentMode — разные инструменты с разными характеристиками
- batch-service уже существует для операций с расширениями
- Нужно добавить backup/restore и CI/CD capabilities

**Decision:**
Создать отдельные сервисы по бизнес-ролям:
- `backup-service` — Disaster Recovery (ibcmd dump/restore/replicate)
- `config-service` — CI/CD (AgentMode)

**Consequences:**
- (+) Чистое разделение ответственности
- (+) Независимое масштабирование
- (+) Разные SLA per service
- (-) Больше сервисов в инфраструктуре
- (-) Небольшое дублирование (config, health)

### ADR-002: ibcmd vs 1cv8.exe для backup

**Context:**
- `1cv8.exe DESIGNER /DumpIB` — традиционный способ
- `ibcmd infobase dump` — новый способ (8.3.x+)

**Decision:**
Использовать **ibcmd** как primary tool:

| Критерий | 1cv8.exe | ibcmd |
|----------|----------|-------|
| Требует платформу | ✅ Да | ❌ Нет |
| Требует лицензию | ✅ Да | ❌ Нет |
| Многопоточность | ❌ Нет | ✅ `--jobs-count` |
| Размер дистрибутива | ~2GB | ~50MB |
| Headless servers | ❌ Сложно | ✅ Легко |

**Consequences:**
- (+) Можно деплоить на "чистые" серверы без платформы
- (+) Ускорение через многопоточность
- (+) Меньше footprint
- (-) Только 8.3.x+ (не критично для проекта)

---

## Phase 1: backup-service

**Duration:** 6 weeks
**Priority:** HIGH
**Status:** 🔴 NOT STARTED

### Goals

- Async backup/restore jobs для 700+ баз
- S3/MinIO storage для .dt файлов
- Progress tracking через WebSocket
- Scheduled backups (cron-like)
- Disaster Recovery: replicate между серверами

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        backup-service                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │   REST API  │───▶│ Job Manager │───▶│   ibcmd     │         │
│  │  (Gin)      │    │  (async)    │    │  Executor   │         │
│  └─────────────┘    └──────┬──────┘    └──────┬──────┘         │
│         │                  │                  │                 │
│         ▼                  ▼                  ▼                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │  WebSocket  │    │   Redis     │    │  S3/MinIO   │         │
│  │  (progress) │    │  (jobs)     │    │  (.dt files)│         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Orchestrator                            │
│  • Scheduling (Celery Beat)                                     │
│  • Database registry                                            │
│  • Backup history & retention                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Directory Structure

```
go-services/backup-service/
├── cmd/
│   └── main.go
├── internal/
│   ├── api/
│   │   ├── router.go
│   │   └── handlers/
│   │       ├── dump.go           # POST /api/v1/jobs/dump
│   │       ├── restore.go        # POST /api/v1/jobs/restore
│   │       ├── replicate.go      # POST /api/v1/jobs/replicate
│   │       ├── jobs.go           # GET /api/v1/jobs/:id
│   │       └── websocket.go      # WS /api/v1/jobs/:id/progress
│   ├── infrastructure/
│   │   ├── ibcmd/
│   │   │   ├── executor.go       # Subprocess wrapper
│   │   │   ├── config.go         # YAML config builder
│   │   │   └── parser.go         # Output parser
│   │   ├── storage/
│   │   │   ├── s3.go             # S3/MinIO client
│   │   │   └── local.go          # Local filesystem fallback
│   │   └── redis/
│   │       └── client.go         # Job queue + Pub/Sub
│   ├── domain/
│   │   ├── job/
│   │   │   ├── manager.go        # Job lifecycle (FSM)
│   │   │   ├── types.go          # JobStatus, JobType enums
│   │   │   └── repository.go     # Redis-based persistence
│   │   └── backup/
│   │       ├── dump.go           # Dump business logic
│   │       ├── restore.go        # Restore business logic
│   │       └── replicate.go      # Cross-server replication
│   ├── eventhandlers/
│   │   └── backup_commands.go    # Redis Pub/Sub handlers
│   └── config/
│       └── config.go
├── configs/
│   └── ibcmd-template.yaml       # Template for ibcmd config
├── Dockerfile
├── Makefile
└── README.md
```

### Week 1-2: Core Infrastructure

**Effort:** 10 days
**Goal:** ibcmd integration + basic job management

#### Week 1: ibcmd Executor

**Day 1-2: Project Setup**
- [ ] Create `go-services/backup-service/` structure
- [ ] Copy shared packages from `go-services/shared/`
- [ ] Setup Makefile, Dockerfile
- [ ] Add to docker-compose.yml (port 8089)
- [ ] Health check endpoint

**Day 3-4: ibcmd Executor**
- [ ] `internal/infrastructure/ibcmd/executor.go`
  - Subprocess execution with timeout
  - Async stdout/stderr reading (prevent deadlock)
  - Exit code handling
- [ ] `internal/infrastructure/ibcmd/config.go`
  - YAML config file generation
  - Support for all connection types (PostgreSQL, MSSQL, file)
- [ ] `internal/infrastructure/ibcmd/parser.go`
  - Parse ibcmd output for progress (if available)
  - Error message extraction

**Day 5: Unit Tests**
- [ ] Test executor with mock subprocess
- [ ] Test config generation
- [ ] Test error handling

#### Week 2: Job Manager

**Day 1-2: Job Domain**
- [ ] `internal/domain/job/types.go`
  ```go
  type JobType string
  const (
      JobTypeDump      JobType = "dump"
      JobTypeRestore   JobType = "restore"
      JobTypeReplicate JobType = "replicate"
  )

  type JobStatus string
  const (
      JobStatusPending    JobStatus = "pending"
      JobStatusRunning    JobStatus = "running"
      JobStatusCompleted  JobStatus = "completed"
      JobStatusFailed     JobStatus = "failed"
      JobStatusCancelled  JobStatus = "cancelled"
  )

  type Job struct {
      ID           string
      Type         JobType
      Status       JobStatus
      DatabaseID   string
      Progress     int       // 0-100
      StartedAt    time.Time
      CompletedAt  *time.Time
      Error        string
      OutputPath   string    // S3 path for dump
      InputPath    string    // S3 path for restore
  }
  ```

**Day 3-4: Job Manager (FSM)**
- [ ] `internal/domain/job/manager.go`
  - Create job → Pending
  - Start job → Running (spawn goroutine)
  - Complete job → Completed/Failed
  - Cancel job → Cancelled (kill subprocess)
- [ ] `internal/domain/job/repository.go`
  - Redis-based persistence (HSET, HGET)
  - TTL for completed jobs (7 days)

**Day 5: Integration Test**
- [ ] Test full flow: create → run → complete
- [ ] Test cancellation
- [ ] Test failure handling

### Week 3-4: Storage + Async Jobs

**Effort:** 10 days
**Goal:** S3 integration + async execution

#### Week 3: S3/MinIO Storage

**Day 1-2: Storage Interface**
- [ ] `internal/infrastructure/storage/interface.go`
  ```go
  type Storage interface {
      Upload(ctx context.Context, key string, reader io.Reader) error
      Download(ctx context.Context, key string) (io.ReadCloser, error)
      Delete(ctx context.Context, key string) error
      GetPresignedURL(ctx context.Context, key string, expiry time.Duration) (string, error)
  }
  ```

**Day 3-4: S3 Implementation**
- [ ] `internal/infrastructure/storage/s3.go`
  - MinIO client (AWS SDK compatible)
  - Multipart upload for large .dt files
  - Presigned URLs for download

**Day 5: Local Fallback**
- [ ] `internal/infrastructure/storage/local.go`
  - Filesystem-based storage
  - For development/testing without S3

#### Week 4: Async Execution

**Day 1-2: Worker Pool**
- [ ] Goroutine-based worker pool
- [ ] Configurable concurrency (default: 3 parallel jobs)
- [ ] Job queue in Redis (LPUSH/BRPOP)

**Day 3-4: Progress Tracking**
- [ ] Parse ibcmd output for progress indicators
- [ ] Fallback: time-based estimation
- [ ] Redis Pub/Sub for progress updates

**Day 5: WebSocket Handler**
- [ ] `internal/api/handlers/websocket.go`
  - Real-time progress streaming
  - Heartbeat for connection health

### Week 5-6: API + Integration

**Effort:** 10 days
**Goal:** Complete REST API + Orchestrator integration

#### Week 5: REST API

**Day 1-2: Dump Endpoint**
- [ ] `POST /api/v1/jobs/dump`
  ```json
  {
    "database_id": "uuid",
    "output_format": "dt",
    "jobs_count": 4,
    "compress": true
  }
  ```
- [ ] Response: `{ "job_id": "uuid", "status": "pending" }`

**Day 3-4: Restore Endpoint**
- [ ] `POST /api/v1/jobs/restore`
  ```json
  {
    "database_id": "uuid",
    "source_path": "s3://backups/db-2025-01-01.dt",
    "create_database": true,
    "force": false
  }
  ```

**Day 5: Replicate Endpoint**
- [ ] `POST /api/v1/jobs/replicate`
  ```json
  {
    "source_database_id": "uuid",
    "target": {
      "dbms": "PostgreSQL",
      "server": "new-server:5432",
      "name": "db_copy",
      "user": "postgres",
      "password": "***"
    },
    "jobs_count": 4
  }
  ```

#### Week 6: Integration + Testing

**Day 1-2: Orchestrator Integration**
- [ ] Django models for BackupJob, BackupSchedule
- [ ] Celery Beat for scheduled backups
- [ ] API Gateway routing

**Day 3-4: Event Handlers**
- [ ] Redis Pub/Sub: `backup-service/commands`
- [ ] Events: BackupStarted, BackupCompleted, BackupFailed

**Day 5: Testing + Documentation**
- [ ] Integration tests
- [ ] Load tests (concurrent jobs)
- [ ] OpenAPI spec
- [ ] README.md

### API Reference

#### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/jobs/dump` | Create dump job |
| `POST` | `/api/v1/jobs/restore` | Create restore job |
| `POST` | `/api/v1/jobs/replicate` | Create replicate job |
| `GET` | `/api/v1/jobs/:id` | Get job status |
| `DELETE` | `/api/v1/jobs/:id` | Cancel job |
| `GET` | `/api/v1/jobs` | List jobs (with filters) |
| `WS` | `/api/v1/jobs/:id/progress` | Real-time progress |
| `GET` | `/health` | Health check |

#### Job Lifecycle

```
┌─────────┐    start    ┌─────────┐    success   ┌───────────┐
│ PENDING │────────────▶│ RUNNING │─────────────▶│ COMPLETED │
└─────────┘             └────┬────┘              └───────────┘
                             │
                             │ failure
                             ▼
                        ┌────────┐
     cancel             │ FAILED │
┌──────────────────────▶└────────┘
│
│    ┌───────────┐
└────│ CANCELLED │
     └───────────┘
```

---

## Phase 2: config-service

**Duration:** 4 weeks
**Priority:** LOW (on-demand)
**Status:** 🟡 DEFERRED

### Goals

- AgentMode SSH connection pool
- CI/CD integration (GitLab, Jenkins)
- Configuration export/import
- External reports/processors management

### Prerequisites

- Clear use case from development team
- EDT or CI/CD pipeline requirements
- AgentMode testing on target 1C versions

### Architecture (Draft)

```
┌─────────────────────────────────────────────────────────────────┐
│                        config-service                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │   REST API  │───▶│ Agent Pool  │───▶│   SSH       │         │
│  │  (Gin)      │    │  Manager    │    │  Clients    │         │
│  └─────────────┘    └──────┬──────┘    └──────┬──────┘         │
│                            │                  │                 │
│                            ▼                  ▼                 │
│                     ┌─────────────┐    ┌─────────────┐         │
│                     │   Redis     │    │ 1cv8.exe    │         │
│                     │  (sessions) │    │ /AgentMode  │         │
│                     └─────────────┘    └─────────────┘         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Key Challenges

1. **Persistent SSH connections** — нужен connection pool с health checks
2. **One agent = one database** — ограничение AgentMode
3. **Синхронное выполнение** — очередь команд per connection
4. **Platform dependency** — требует 1cv8.exe на сервере

### Endpoints (Draft)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/config/export` | Export config to files |
| `POST` | `/api/v1/config/import` | Import config from files |
| `POST` | `/api/v1/config/update-db` | Update database config |
| `POST` | `/api/v1/external/export` | Export external processor |
| `POST` | `/api/v1/external/import` | Import external processor |
| `GET` | `/api/v1/agents` | List active agents |
| `GET` | `/health` | Health check |

---

## Shared Infrastructure

### Reusable from batch-service

| Component | Path | Reuse |
|-----------|------|-------|
| Logger | `shared/logger/` | ✅ Direct |
| Config | `shared/config/` | ✅ Direct |
| Metrics | `shared/metrics/` | ✅ Direct |
| Auth middleware | `shared/auth/` | ✅ Direct |
| Redis client | `shared/redis/` | ⚠️ Extend |

### New Shared Components

```
go-services/shared/
├── ibcmd/              # NEW: ibcmd executor (shared with batch-service)
│   ├── executor.go
│   ├── config.go
│   └── parser.go
└── storage/            # NEW: S3/MinIO abstraction
    ├── interface.go
    ├── s3.go
    └── local.go
```

---

## Success Metrics

### Phase 1 (backup-service)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Dump throughput | 10 GB/hour | Time per GB |
| Restore success rate | >99% | Failed/Total jobs |
| Concurrent jobs | 10 parallel | Load test |
| API latency (create job) | <100ms | P95 |
| Progress accuracy | ±10% | Actual vs reported |

### Phase 2 (config-service)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Export time | <30 sec | Large config |
| Connection pool efficiency | >80% reuse | New/Reused connections |
| Agent uptime | >99.9% | Health checks |

---

## Risk Mitigation

### Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| ibcmd version incompatibility | HIGH | Test on 8.3.20+, 8.3.25+, 8.3.27 |
| Large .dt files (>100GB) | MEDIUM | Streaming upload, multipart |
| S3 unavailability | MEDIUM | Local storage fallback |
| SSH connection drops | MEDIUM | Reconnect logic, heartbeat |

### Operational Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Backup window conflicts | HIGH | Scheduling with lock detection |
| Storage costs | MEDIUM | Retention policies, compression |
| Network bandwidth | MEDIUM | Throttling, off-peak scheduling |

---

## References

### ibcmd Documentation

- [Infostart: Примеры работы с ibcmd](https://infostart.ru/1c/articles/2500569/)
- [1C:Зазеркалье: Режим агента конфигуратора](https://wonderland.v8.1c.ru/blog/rezhim-agenta-konfiguratora/)
- `docs/ibcmd.md` — Local examples

### ibcmd Command Reference

```bash
# Dump database
ibcmd infobase dump \
  --dbms=PostgreSQL \
  --db-server="server port=5433" \
  --db-name=mydb \
  --db-user=user --db-pwd=pass \
  --user=1c_user --password=1c_pass \
  /path/to/output.dt

# Restore database
ibcmd infobase restore \
  --dbms=PostgreSQL \
  --db-server="server port=5433" \
  --db-name=mydb \
  --db-user=user --db-pwd=pass \
  --create-database --force \
  /path/to/input.dt

# Replicate (cross-server copy)
ibcmd infobase replicate \
  --dbms=PostgreSQL \
  --db-server="source:5432" --db-name=source_db \
  --db-user=user --db-pwd=pass \
  --target-dbms=PostgreSQL \
  --target-database-server="target:5432" \
  --target-database-name=target_db \
  --target-database-user=user \
  --target-database-password=pass \
  --jobs-count=4 --target-jobs-count=4
```

### AgentMode Command Reference

```bash
# Start agent
1cv8.exe DESIGNER /S server/base /AgentMode /Port 1543

# SSH commands (via PuTTY, Paramiko, etc.)
common connect-ib
config dump-cfg --file /path/to/config.cf
config load-cfg --file /path/to/config.cf
common disconnect-ib
common shutdown
```

---

**Version History:**

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-11-28 | Initial draft |

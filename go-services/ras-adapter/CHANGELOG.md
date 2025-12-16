# Changelog

## [Unreleased]

### Changed
- Removed legacy REST API v1 (only `/api/v2/*` is supported).

### Week 4+ (Planned)
- Integration tests with real RAS server
- Connection pooling optimization
- Advanced error handling improvements
- Performance testing

## [0.3.0] - 2025-11-20 - Week 3: Real RAS Protocol Integration

### Changed

- **BREAKING:** Replaced stub RAS client with real khorevaa/ras-client implementation
- All RAS methods now use real RAS binary protocol (GetClusters, GetInfobases, GetSessions, GetInfobaseInfo, RegInfoBase, TerminateSession)
- Added authentication for cluster operations
- Improved error handling and logging for all RAS operations

### Added

- Circuit breaker for RAS operations (sony/gobreaker)
- Connection health checks in pool (GetClusters ping)
- Client.Close() method for graceful shutdown
- Real UUID type conversions (satori/go.uuid)
- Full RAS type conversions to domain models

### Fixed

- GetClusters(), GetInfobases(), GetSessions() now return real data from RAS server
- RegInfoBase() now works correctly for Lock/Unlock operations
- TerminateSession() now terminates real 1C sessions
- Lock/Unlock operations now use real RAS UpdateInfobase method

### Technical Details

- Dependencies:
  - github.com/khorevaa/ras-client v0.0.0-20201104084928-a9228766f6ed
  - github.com/sony/gobreaker v0.5.0 (new)
  - github.com/satori/go.uuid v1.2.0 (new)

## [0.2.0] - 2025-11-20 - Week 2: Lock/Unlock Implementation

### Added
- Lock/Unlock functionality for infobases (scheduled jobs blocking)
- RAS Client methods: `LockInfobase()`, `UnlockInfobase()`, `GetInfobaseInfo()`, `RegInfoBase()`
- Service layer: `InfobaseService.LockInfobase()`, `InfobaseService.UnlockInfobase()`
- REST API endpoints: `POST /api/v2/lock-infobase`, `POST /api/v2/unlock-infobase`
- Event handlers: `LockHandler`, `UnlockHandler` (Redis Pub/Sub)
- Models: `Infobase.ScheduledJobsDeny`, `Infobase.SessionsDeny` fields

### Changed
- `internal/models/infobase.go`: Added lock/unlock fields
- `cmd/main.go`: Wired Lock/Unlock event handlers
- `internal/eventhandlers/interfaces.go`: Added `InfobaseManager` interface

### Notes
- Week 2 implementation uses STUB for RegInfoBase (mock data)
- Real v8platform SDK integration will be in Week 3+
- Lock/Unlock workflow ready for testing

## [0.1.0] - 2025-11-20 - Week 1: Foundation

### Added
- Project structure (cmd/, internal/api/, internal/service/, etc.)
- Configuration management (`internal/config/`)
- Domain models (`internal/models/`)
- Stub RAS client (`internal/ras/client.go`) - returns mock data
- RAS connection pool (`internal/ras/pool.go`)
- REST API handlers:
  - `GET /health` - health check
  - `GET /api/v2/list-clusters` - list clusters
  - `GET /api/v2/list-infobases` - list infobases
  - `GET /api/v2/list-sessions` - list sessions
  - `POST /api/v2/terminate-sessions` - terminate sessions
- Service layer (`internal/service/`)
  - ClusterService
  - InfobaseService
  - SessionService
- Event handlers (`internal/eventhandlers/`)
  - TerminateHandler (Redis Pub/Sub)
  - Idempotency check via Redis SetNX
  - Session monitoring (30 sec timeout)
- Middleware:
  - Logger (request logging with sanitization)
  - Recovery (panic recovery)
- HTTP server with graceful shutdown
- Version info support
- Build configuration for `cc1c-ras-adapter.exe`

### Notes
- **Week 1 is STUB implementation** - all RAS methods return mock data
- No real RAS connection yet (will be implemented in Week 2)
- Lock/Unlock NOT implemented (Week 2 via RegInfoBase)
- Event Bus integration ready (Redis Pub/Sub)

### Technical Details
- Module: `github.com/commandcenter1c/commandcenter/ras-adapter`
- Go version: 1.21
- Dependencies:
  - gin-gonic/gin v1.11.0
  - redis/go-redis/v9 v9.17.0
  - uber/zap v1.27.1
  - ThreeDotsLabs/watermill v1.5.1
  - commandcenter/shared (local)

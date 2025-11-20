# cluster-service - DEPRECATED

**Status:** ❌ DEPRECATED (Week 4 - 2025-11-20)
**Replaced by:** ras-adapter

## Why Deprecated?

cluster-service has been replaced by ras-adapter, which provides:
- Direct RAS protocol integration (no ras-grpc-gw middleman)
- 1 network hop instead of 2 (50% reduction)
- Better performance (30-50% latency improvement)
- Simpler architecture (single service vs cluster-service + ras-grpc-gw)

## Architecture Change

**Old:**
```
Worker → Redis → cluster-service (8088) → ras-grpc-gw (9999) → RAS (1545)
                      2 network hops
```

**New:**
```
Worker → Redis → ras-adapter (8088) → RAS (1545)
                      1 network hop
```

## Migration Guide

1. Stop using cluster-service:
   ```bash
   ./scripts/dev/stop-all.sh
   ```

2. Start ras-adapter (automatically via start-all.sh):
   ```bash
   ./scripts/dev/start-all.sh
   ```

3. Verify ras-adapter:
   ```bash
   curl http://localhost:8088/health
   ```

## Backward Compatibility

To temporarily switch back to cluster-service (NOT recommended):
```bash
USE_RAS_ADAPTER=false ./scripts/dev/start-all.sh
```

## Code Location

Archived at: `go-services/archive/cluster-service/`

## Contact

For questions, see: docs/roadmaps/WEEK4_DEPLOY_VALIDATE_PLAN.md

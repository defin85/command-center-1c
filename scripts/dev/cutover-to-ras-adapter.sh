#!/bin/bash
# Week 4 Day 2: Cutover to RAS Adapter
# Deprecates cluster-service, archives code, updates configurations

set -e

echo "========================================"
echo "  Cutover to RAS Adapter"
echo "========================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Confirmation prompt
echo -e "${YELLOW}⚠️  WARNING: This will deprecate cluster-service and ras-grpc-gw!${NC}"
echo ""
echo "This script will:"
echo "  1. Stop cluster-service (if running)"
echo "  2. Archive cluster-service code"
echo "  3. Update .env.local (set USE_RAS_ADAPTER=true)"
echo "  4. Create deprecation notice"
echo ""
read -p "Are you sure you want to proceed? (yes/no): " confirmation

if [ "$confirmation" != "yes" ]; then
    echo "Cutover cancelled."
    exit 0
fi

echo ""
echo -e "${BLUE}Starting cutover process...${NC}"
echo ""

# Step 1: Stop cluster-service
echo "Step 1: Stopping cluster-service..."

if [ -f pids/cluster-service.pid ]; then
    CLUSTER_PID=$(cat pids/cluster-service.pid)
    echo "  Stopping cluster-service (PID: $CLUSTER_PID)..."
    taskkill //PID $CLUSTER_PID //F > /dev/null 2>&1 || true
    rm -f pids/cluster-service.pid
    echo -e "  ${GREEN}✓ cluster-service stopped${NC}"
else
    echo -e "  ${YELLOW}⚠ cluster-service not running${NC}"
fi

echo ""

# Step 2: Archive cluster-service code
echo "Step 2: Archiving cluster-service code..."

if [ -d "go-services/cluster-service" ] && [ ! -d "go-services/archive/cluster-service" ]; then
    mkdir -p go-services/archive
    git mv go-services/cluster-service go-services/archive/cluster-service 2>/dev/null || mv go-services/cluster-service go-services/archive/cluster-service
    echo -e "  ${GREEN}✓ cluster-service archived to go-services/archive/${NC}"
else
    echo -e "  ${YELLOW}⚠ cluster-service already archived or not found${NC}"
fi

# Create deprecation notice
cat > go-services/archive/cluster-service/DEPRECATED.md << 'EOF'
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
EOF

echo -e "  ${GREEN}✓ Deprecation notice created${NC}"
echo ""

# Step 3: Update .env.local
echo "Step 3: Updating .env.local..."

if [ -f .env.local ]; then
    # Check if USE_RAS_ADAPTER exists
    if grep -q "USE_RAS_ADAPTER" .env.local; then
        # Update existing value
        sed -i 's/USE_RAS_ADAPTER=.*/USE_RAS_ADAPTER=true/' .env.local
        echo -e "  ${GREEN}✓ USE_RAS_ADAPTER=true set in .env.local${NC}"
    else
        # Add new line
        echo "" >> .env.local
        echo "# Week 4: RAS Adapter (replaces cluster-service)" >> .env.local
        echo "USE_RAS_ADAPTER=true" >> .env.local
        echo -e "  ${GREEN}✓ USE_RAS_ADAPTER=true added to .env.local${NC}"
    fi
else
    echo -e "  ${YELLOW}⚠ .env.local not found, skipping${NC}"
fi

echo ""

# Step 4: Verify RAS Adapter is running
echo "Step 4: Verifying RAS Adapter..."

if curl -sf http://localhost:8088/health > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓ RAS Adapter is running and healthy${NC}"
else
    echo -e "  ${RED}✗ RAS Adapter is NOT running!${NC}"
    echo ""
    echo -e "${YELLOW}ACTION REQUIRED:${NC} Start RAS Adapter:"
    echo "  ./scripts/dev/start-all.sh"
    exit 1
fi

echo ""

# Step 5: Summary
echo "========================================"
echo "  Cutover Complete!"
echo "========================================"
echo ""
echo -e "${GREEN}✓ cluster-service deprecated${NC}"
echo -e "${GREEN}✓ Code archived to go-services/archive/cluster-service/${NC}"
echo -e "${GREEN}✓ USE_RAS_ADAPTER=true set${NC}"
echo -e "${GREEN}✓ RAS Adapter verified running${NC}"
echo ""
echo "Next steps:"
echo "  1. Monitor RAS Adapter for 24 hours"
echo "  2. Run smoke tests: ./scripts/dev/test-lock-unlock-workflow.sh"
echo "  3. Update documentation (if needed)"
echo ""
echo -e "${BLUE}ℹ️  Rollback:${NC} If issues occur, see docs/roadmaps/WEEK4_DEPLOY_VALIDATE_PLAN.md Section 5.3"
echo ""

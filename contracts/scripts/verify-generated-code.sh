#!/bin/bash
# Verify that generated code compiles correctly
# This script runs AFTER generate-all.sh to ensure generated code is valid
#
# Usage: ./contracts/scripts/verify-generated-code.sh [--quick]
#   --quick: Skip TypeScript check (faster, for frequent rebuilds)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
QUICK_MODE=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            QUICK_MODE=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

echo -e "${BLUE}=== Verifying Generated Code ===${NC}"
echo ""

FAILED=0

##############################################################################
# 1. Go: Verify ras-adapter generated server.go compiles
##############################################################################
echo -e "${BLUE}[1/3] Checking Go generated code (ras-adapter)...${NC}"

RAS_ADAPTER_GENERATED="$PROJECT_ROOT/go-services/ras-adapter/internal/api/generated"

if [[ -d "$RAS_ADAPTER_GENERATED" ]]; then
    cd "$PROJECT_ROOT/go-services/ras-adapter"

    # Try to build just the generated package (fast check)
    if go build -o /dev/null ./internal/api/generated/ 2>&1; then
        echo -e "  ${GREEN}✓ ras-adapter generated code compiles${NC}"
    else
        echo -e "  ${RED}✗ ras-adapter generated code has compilation errors:${NC}"
        go build -o /dev/null ./internal/api/generated/ 2>&1 | head -n 20
        FAILED=$((FAILED + 1))
    fi
else
    echo -e "  ${YELLOW}⊘ ras-adapter generated directory not found (skipping)${NC}"
fi

echo ""

##############################################################################
# 2. Go: Verify api-gateway generated routes compile
##############################################################################
echo -e "${BLUE}[2/3] Checking Go generated code (api-gateway)...${NC}"

API_GW_GENERATED="$PROJECT_ROOT/go-services/api-gateway/internal/routes/generated"

if [[ -d "$API_GW_GENERATED" ]]; then
    cd "$PROJECT_ROOT/go-services/api-gateway"

    # Try to build the routes package
    if go build -o /dev/null ./internal/routes/... 2>&1; then
        echo -e "  ${GREEN}✓ api-gateway generated routes compile${NC}"
    else
        echo -e "  ${RED}✗ api-gateway generated routes have compilation errors:${NC}"
        go build -o /dev/null ./internal/routes/... 2>&1 | head -n 20
        FAILED=$((FAILED + 1))
    fi
else
    echo -e "  ${YELLOW}⊘ api-gateway generated directory not found (skipping)${NC}"
fi

echo ""

##############################################################################
# 3. TypeScript: Verify frontend generated types (optional in quick mode)
##############################################################################
if [[ "$QUICK_MODE" == "true" ]]; then
    echo -e "${BLUE}[3/3] Skipping TypeScript check (--quick mode)${NC}"
else
    echo -e "${BLUE}[3/3] Checking TypeScript generated code (frontend)...${NC}"

    FRONTEND_GENERATED="$PROJECT_ROOT/frontend/src/api/generated"

    if [[ -d "$FRONTEND_GENERATED" ]]; then
        cd "$PROJECT_ROOT/frontend"

        # Check if node_modules exists
        if [[ ! -d "node_modules" ]]; then
            echo -e "  ${YELLOW}⊘ node_modules not found, skipping TypeScript check${NC}"
        else
            # Type-check using project's tsconfig (handles Vite's import.meta.env)
            # We check only the generated directory to keep it fast
            if npx tsc --noEmit --project tsconfig.json 2>&1 | grep -q "src/api/generated"; then
                # Errors specifically in generated code
                echo -e "  ${RED}✗ frontend generated types have errors:${NC}"
                npx tsc --noEmit --project tsconfig.json 2>&1 | grep "src/api/generated" | head -n 20
                FAILED=$((FAILED + 1))
            else
                echo -e "  ${GREEN}✓ frontend generated types are valid${NC}"
            fi
        fi
    else
        echo -e "  ${YELLOW}⊘ frontend generated directory not found (skipping)${NC}"
    fi
fi

echo ""

##############################################################################
# Summary
##############################################################################
echo -e "${BLUE}=== Verification Complete ===${NC}"

if [[ $FAILED -eq 0 ]]; then
    echo -e "${GREEN}✓ All generated code verified successfully${NC}"
    exit 0
else
    echo -e "${RED}✗ $FAILED component(s) failed verification${NC}"
    echo -e "${YELLOW}Hint: Re-run contracts/scripts/generate-all.sh --force${NC}"
    exit 1
fi

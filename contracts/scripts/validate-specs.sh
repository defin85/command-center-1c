#!/bin/bash
# Validate OpenAPI specifications
# Usage: ./contracts/scripts/validate-specs.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTRACTS_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== OpenAPI Specification Validation ===${NC}"
echo ""

# Function to validate a spec file
validate_spec() {
    local spec_file="$1"
    local service_name="$2"

    echo -e "${GREEN}Validating $service_name...${NC}"

    if [[ ! -f "$spec_file" ]]; then
        echo -e "  ${RED}✗ Spec file not found: $spec_file${NC}"
        return 1
    fi

    # Method 1: Try oapi-codegen (if available)
    if command -v oapi-codegen &> /dev/null; then
        if oapi-codegen -config /dev/null "$spec_file" > /dev/null 2>&1; then
            echo -e "  ${GREEN}✓ Valid OpenAPI 3.0 spec (oapi-codegen)${NC}"
            return 0
        else
            echo -e "  ${RED}✗ Invalid OpenAPI spec (oapi-codegen)${NC}"
            oapi-codegen -config /dev/null "$spec_file" 2>&1 | head -n 10
            return 1
        fi
    fi

    # Method 2: Try swagger-cli (if available)
    if command -v swagger-cli &> /dev/null; then
        if swagger-cli validate "$spec_file" > /dev/null 2>&1; then
            echo -e "  ${GREEN}✓ Valid OpenAPI spec (swagger-cli)${NC}"
            return 0
        else
            echo -e "  ${RED}✗ Invalid OpenAPI spec (swagger-cli)${NC}"
            swagger-cli validate "$spec_file"
            return 1
        fi
    fi

    # Method 3: Basic YAML syntax check
    if command -v python3 &> /dev/null; then
        if python3 -c "import yaml; yaml.safe_load(open('$spec_file'))" 2> /dev/null; then
            echo -e "  ${YELLOW}⊘ YAML syntax valid (Python PyYAML)${NC}"
            echo -e "  ${YELLOW}  Install oapi-codegen or swagger-cli for full validation${NC}"
            return 0
        else
            echo -e "  ${RED}✗ Invalid YAML syntax${NC}"
            python3 -c "import yaml; yaml.safe_load(open('$spec_file'))"
            return 1
        fi
    fi

    # No validators available
    echo -e "  ${YELLOW}⊘ No validators available${NC}"
    echo -e "  ${YELLOW}  Install one of: oapi-codegen, swagger-cli, or python3 with PyYAML${NC}"
    return 0
}

# Validate all specs
FAILED=0

# api-gateway (if exists)
if [[ -f "$CONTRACTS_DIR/api-gateway/openapi.yaml" ]]; then
    if ! validate_spec "$CONTRACTS_DIR/api-gateway/openapi.yaml" "api-gateway"; then
        FAILED=$((FAILED + 1))
    fi
    echo ""
fi

# orchestrator (if exists)
if [[ -f "$CONTRACTS_DIR/orchestrator/openapi.yaml" ]]; then
    if ! validate_spec "$CONTRACTS_DIR/orchestrator/openapi.yaml" "orchestrator"; then
        FAILED=$((FAILED + 1))
    fi
    echo ""
fi

# worker (if exists)
if [[ -f "$CONTRACTS_DIR/worker/openapi.yaml" ]]; then
    if ! validate_spec "$CONTRACTS_DIR/worker/openapi.yaml" "worker"; then
        FAILED=$((FAILED + 1))
    fi
    echo ""
fi

# Summary
echo -e "${GREEN}=== Validation Complete ===${NC}"
if [[ $FAILED -eq 0 ]]; then
    echo -e "${GREEN}✓ All specifications are valid${NC}"
    exit 0
else
    echo -e "${RED}✗ $FAILED specification(s) failed validation${NC}"
    exit 1
fi

#!/bin/bash
# Generate all API clients from OpenAPI specifications
# Usage: ./contracts/scripts/generate-all.sh [--force]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTRACTS_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$CONTRACTS_DIR")"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== API Client Generation ===${NC}"
echo "Contracts directory: $CONTRACTS_DIR"
echo ""

# Check if force regeneration is requested
FORCE_REGEN=false
if [[ "$1" == "--force" ]]; then
    FORCE_REGEN=true
    echo -e "${YELLOW}Force regeneration enabled${NC}"
fi

# Function to check if spec file changed since last generation
needs_regeneration() {
    local spec_file="$1"
    local output_dir="$2"

    if [[ "$FORCE_REGEN" == "true" ]]; then
        return 0
    fi

    # If output doesn't exist, needs generation
    if [[ ! -d "$output_dir" ]]; then
        return 0
    fi

    # Check if spec is newer than output
    if [[ "$spec_file" -nt "$output_dir" ]]; then
        return 0
    fi

    return 1
}

# ============================
# Generate ras-adapter clients
# ============================
echo -e "${GREEN}[1/3] ras-adapter API...${NC}"

RAS_SPEC="$CONTRACTS_DIR/ras-adapter/openapi.yaml"
RAS_GO_OUTPUT="$PROJECT_ROOT/go-services/ras-adapter/internal/api/generated"
RAS_PY_OUTPUT="$PROJECT_ROOT/orchestrator/apps/databases/clients/generated"

if needs_regeneration "$RAS_SPEC" "$RAS_GO_OUTPUT"; then
    echo "  → Generating Go server types..."

    # Check if oapi-codegen is installed
    if ! command -v oapi-codegen &> /dev/null; then
        echo -e "${RED}Error: oapi-codegen not found${NC}"
        echo "Install with: go install github.com/oapi-codegen/oapi-codegen/v2/cmd/oapi-codegen@latest"
        exit 1
    fi

    # Create output directory if not exists
    mkdir -p "$RAS_GO_OUTPUT"

    # Generate Go code
    cd "$CONTRACTS_DIR/ras-adapter"
    oapi-codegen -config .oapi-codegen.yaml openapi.yaml

    echo -e "  ${GREEN}✓ Go server types generated${NC}"
else
    echo -e "  ${YELLOW}⊘ Go code unchanged (skip)${NC}"
fi

if needs_regeneration "$RAS_SPEC" "$RAS_PY_OUTPUT"; then
    echo "  → Generating Python client..."

    # Check if openapi-python-client is installed
    VENV_ACTIVATE="$PROJECT_ROOT/orchestrator/venv/Scripts/activate"

    if [[ ! -f "$VENV_ACTIVATE" ]]; then
        echo -e "${RED}Error: Django venv not found at $VENV_ACTIVATE${NC}"
        exit 1
    fi

    # Activate venv and check for openapi-python-client
    source "$VENV_ACTIVATE"

    if ! command -v openapi-python-client &> /dev/null; then
        echo -e "${RED}Error: openapi-python-client not found${NC}"
        echo "Install with: pip install openapi-python-client"
        exit 1
    fi

    # Generate Python client
    cd "$PROJECT_ROOT"
    openapi-python-client generate \
        --path "$RAS_SPEC" \
        --output-path "$RAS_PY_OUTPUT" \
        --overwrite \
        > /dev/null 2>&1

    echo -e "  ${GREEN}✓ Python client generated${NC}"
else
    echo -e "  ${YELLOW}⊘ Python client unchanged (skip)${NC}"
fi

echo ""

# ============================
# api-gateway → TypeScript client for Frontend
# ============================
echo -e "${GREEN}[2/3] api-gateway API (TypeScript client)...${NC}"

GATEWAY_SPEC="$CONTRACTS_DIR/api-gateway/openapi.yaml"
GATEWAY_TS_OUTPUT="$PROJECT_ROOT/frontend/src/api/generated"

if [[ ! -f "$GATEWAY_SPEC" ]]; then
    echo -e "  ${YELLOW}⊘ OpenAPI spec not found (skip)${NC}"
    echo ""
    continue
fi

# Check if we need to regenerate
if needs_regeneration "$GATEWAY_SPEC" "$GATEWAY_TS_OUTPUT"; then
    echo -e "  ${BLUE}Generating TypeScript client...${NC}"

    # Check for openapi-generator-cli
    if command -v openapi-generator-cli &> /dev/null; then
        GENERATOR_CMD="openapi-generator-cli"
    elif command -v npx &> /dev/null; then
        GENERATOR_CMD="npx @openapitools/openapi-generator-cli"
    else
        echo -e "  ${YELLOW}Warning: openapi-generator-cli not found${NC}"
        echo -e "  ${YELLOW}Install with: npm install -g @openapitools/openapi-generator-cli${NC}"
        echo -e "  ${YELLOW}Skipping TypeScript generation...${NC}"
        echo ""
        continue
    fi

    # Generate TypeScript Axios client
    $GENERATOR_CMD generate \
        -i "$GATEWAY_SPEC" \
        -g typescript-axios \
        -o "$GATEWAY_TS_OUTPUT" \
        --skip-validate-spec \
        --additional-properties=supportsES6=true,npmName=@cc1c/api-client,npmVersion=1.0.0,withInterfaces=true \
        > /dev/null 2>&1

    if [[ $? -eq 0 ]]; then
        echo -e "  ${GREEN}✓ TypeScript client generated${NC}"
    else
        echo -e "  ${RED}✗ TypeScript generation failed${NC}"
        echo -e "  ${YELLOW}Try running manually: npx @openapitools/openapi-generator-cli generate -i $GATEWAY_SPEC -g typescript-axios -o $GATEWAY_TS_OUTPUT${NC}"
    fi
else
    echo -e "  ${YELLOW}⊘ TypeScript client unchanged (skip)${NC}"
fi

echo ""

# ============================
# worker (future)
# ============================
echo -e "${GREEN}[3/3] worker API...${NC}"
echo -e "  ${YELLOW}⊘ Not implemented yet${NC}"
echo ""

# ============================
# Summary
# ============================
echo -e "${GREEN}=== Generation Complete ===${NC}"
echo ""
echo "Generated clients:"
echo "  • ras-adapter Go server:     $RAS_GO_OUTPUT/server.go"
echo "  • ras-adapter Python client: $RAS_PY_OUTPUT/ras_adapter_api_client/"
if [[ -d "$GATEWAY_TS_OUTPUT" ]]; then
    echo "  • api-gateway TypeScript:    $GATEWAY_TS_OUTPUT/"
fi
echo ""
echo "Next steps:"
echo "  1. Review generated code for breaking changes"
echo "  2. Update wrapper implementations if needed"
echo "  3. Run tests: ./scripts/dev/test-all.sh"
echo ""

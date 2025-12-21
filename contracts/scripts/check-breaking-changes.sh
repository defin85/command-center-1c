#!/bin/bash
# Check for breaking changes in OpenAPI specifications
# Usage: ./contracts/scripts/check-breaking-changes.sh [base_commit]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTRACTS_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$CONTRACTS_DIR")"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

BASE_COMMIT="${1:-HEAD~1}"

echo -e "${GREEN}=== Breaking Changes Detection ===${NC}"
echo "Comparing against: $BASE_COMMIT"
echo ""

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}Error: Not a git repository${NC}"
    exit 1
fi

# Check if oasdiff is installed
if ! command -v oasdiff &> /dev/null; then
    echo -e "${YELLOW}Warning: oasdiff not installed${NC}"
    echo "Install with: go install github.com/tufin/oasdiff@latest"
    echo ""
    echo "Falling back to simple git diff..."
    echo ""

    # Fallback: show git diff for OpenAPI specs
    # Note: Use find instead of **/*.yaml glob pattern for compatibility
    SPEC_FILES=$(find "$CONTRACTS_DIR" -type f -name "*.yaml" 2>/dev/null | tr '\n' ' ')
    if [[ -n "$SPEC_FILES" ]] && git diff "$BASE_COMMIT" -- $SPEC_FILES | grep -q "^"; then
        echo -e "${YELLOW}Changes detected in OpenAPI specs:${NC}"
        git diff "$BASE_COMMIT" --stat -- $SPEC_FILES
        echo ""
        echo -e "${YELLOW}Manual review required!${NC}"
        exit 0
    else
        echo -e "${GREEN}No changes in OpenAPI specs${NC}"
        exit 0
    fi
fi

# Function to check breaking changes for a spec
check_spec_breaking_changes() {
    local spec_path="$1"
    local service_name="$2"

    echo -e "${BLUE}Checking $service_name...${NC}"

    # Check if spec exists in current version
    if [[ ! -f "$spec_path" ]]; then
        echo -e "  ${YELLOW}⊘ Spec not found in current version (skipped)${NC}"
        return 0
    fi

    # Get the spec from base commit
    local base_spec_content
    base_spec_content=$(git show "$BASE_COMMIT:$spec_path" 2>/dev/null)

    if [[ -z "$base_spec_content" ]]; then
        echo -e "  ${GREEN}✓ New API spec (no breaking changes possible)${NC}"
        return 0
    fi

    # Create temp files
    local base_temp="/tmp/base-$service_name.yaml"
    local current_temp="/tmp/current-$service_name.yaml"

    echo "$base_spec_content" > "$base_temp"
    cp "$spec_path" "$current_temp"

    # Run oasdiff
    if oasdiff breaking "$base_temp" "$current_temp" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓ No breaking changes detected${NC}"
        # Show summary of changes
        if oasdiff changelog "$base_temp" "$current_temp" 2>/dev/null | grep -q "^"; then
            echo -e "  ${BLUE}  Non-breaking changes:${NC}"
            oasdiff changelog "$base_temp" "$current_temp" 2>/dev/null | head -n 5
        fi
        rm -f "$base_temp" "$current_temp"
        return 0
    else
        echo -e "  ${RED}✗ BREAKING CHANGES DETECTED${NC}"
        echo ""
        oasdiff breaking "$base_temp" "$current_temp" 2>&1 || true
        echo ""
        rm -f "$base_temp" "$current_temp"
        return 1
    fi
}

# Check all specs
FAILED=0

# api-gateway (if exists)
if [[ -f "$CONTRACTS_DIR/api-gateway/openapi.yaml" ]]; then
    if ! check_spec_breaking_changes "$CONTRACTS_DIR/api-gateway/openapi.yaml" "api-gateway"; then
        FAILED=$((FAILED + 1))
    fi
    echo ""
fi

# worker (if exists)
if [[ -f "$CONTRACTS_DIR/worker/openapi.yaml" ]]; then
    if ! check_spec_breaking_changes "$CONTRACTS_DIR/worker/openapi.yaml" "worker"; then
        FAILED=$((FAILED + 1))
    fi
    echo ""
fi

# Summary
echo -e "${GREEN}=== Breaking Changes Check Complete ===${NC}"
if [[ $FAILED -eq 0 ]]; then
    echo -e "${GREEN}✓ No breaking changes detected${NC}"
    exit 0
else
    echo -e "${RED}✗ $FAILED API(s) have breaking changes${NC}"
    echo ""
    echo "Breaking changes require:"
    echo "  1. API version bump (e.g., v1 → v2)"
    echo "  2. Deprecation notices for old endpoints"
    echo "  3. Migration guide for clients"
    echo "  4. Team approval before merge"
    exit 1
fi

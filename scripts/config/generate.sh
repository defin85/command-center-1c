#!/bin/bash

##############################################################################
# CommandCenter1C - Service Configuration Generator Wrapper
##############################################################################
# Generates configuration files from config/services.json
#
# Usage:
#   ./scripts/config/generate.sh [--mode local|docker] [--verbose] [--validate-only]
#
# Examples:
#   ./scripts/config/generate.sh                    # Local mode (default)
#   ./scripts/config/generate.sh --mode docker      # Docker mode
#   ./scripts/config/generate.sh --verbose          # Detailed output
#   ./scripts/config/generate.sh --validate-only    # Only validate, don't generate
##############################################################################

set -e

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default arguments
MODE="local"
VERBOSE=""
VALIDATE_ONLY=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --mode)
            MODE="$2"
            shift 2
            ;;
        --mode=*)
            MODE="${1#*=}"
            shift
            ;;
        --verbose|-v)
            VERBOSE="--verbose"
            shift
            ;;
        --validate-only)
            VALIDATE_ONLY="--validate-only"
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--mode local|docker] [--verbose] [--validate-only]"
            echo ""
            echo "Options:"
            echo "  --mode MODE        Target environment: local (default) or docker"
            echo "  --verbose, -v      Show detailed output"
            echo "  --validate-only    Only validate config, don't generate files"
            echo "  --help, -h         Show this help"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown argument: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Validate mode
if [[ "$MODE" != "local" && "$MODE" != "docker" ]]; then
    echo -e "${RED}Invalid mode: $MODE${NC}"
    echo "Valid modes: local, docker"
    exit 1
fi

# Check Python version
# Note: On Windows, python3 may be a broken Windows Store alias
# So we check if python actually works, not just if it exists
PYTHON_CMD=""
if command -v python &> /dev/null && python --version &> /dev/null; then
    PYTHON_CMD="python"
elif command -v python3 &> /dev/null && python3 --version &> /dev/null; then
    PYTHON_CMD="python3"
else
    echo -e "${RED}Error: Python not found${NC}"
    echo "Please install Python 3.11+ and ensure it's in your PATH"
    exit 1
fi

# Verify Python version is 3.11+
PYTHON_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_MAJOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.major)")
PYTHON_MINOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.minor)")

if [[ "$PYTHON_MAJOR" -lt 3 ]] || [[ "$PYTHON_MAJOR" -eq 3 && "$PYTHON_MINOR" -lt 11 ]]; then
    echo -e "${YELLOW}Warning: Python $PYTHON_VERSION detected, 3.11+ recommended${NC}"
    # Continue anyway, the script might work with older versions
fi

# Check that config file exists
CONFIG_FILE="$PROJECT_ROOT/config/services.json"
if [[ ! -f "$CONFIG_FILE" ]]; then
    echo -e "${RED}Error: Config file not found: $CONFIG_FILE${NC}"
    exit 1
fi

# Run the generator
echo -e "${BLUE}Running configuration generator...${NC}"
echo ""

$PYTHON_CMD "$SCRIPT_DIR/generate.py" --mode "$MODE" $VERBOSE $VALIDATE_ONLY

EXIT_CODE=$?

if [[ $EXIT_CODE -eq 0 ]]; then
    echo -e "${GREEN}Configuration generation completed successfully!${NC}"
else
    echo -e "${RED}Configuration generation failed with exit code $EXIT_CODE${NC}"
    exit $EXIT_CODE
fi

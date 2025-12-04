#!/bin/bash
# Export Django OpenAPI specification using drf-spectacular
# Usage: ./contracts/scripts/export-django-openapi.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

cd "$PROJECT_ROOT/orchestrator"

# Activate virtual environment
if [[ -f "venv/bin/activate" ]]; then
    source venv/bin/activate
elif [[ -f "venv/Scripts/activate" ]]; then
    source venv/Scripts/activate
else
    echo "Error: Virtual environment not found"
    exit 1
fi

# Create output directory
mkdir -p "$PROJECT_ROOT/contracts/orchestrator"

# Export OpenAPI spec
python manage.py spectacular \
    --file "$PROJECT_ROOT/contracts/orchestrator/openapi.yaml" \
    --format openapi

echo "OpenAPI exported to contracts/orchestrator/openapi.yaml"

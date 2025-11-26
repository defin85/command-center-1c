#!/bin/bash
# Generate Swagger documentation for ras-adapter

set -e

echo "Generating Swagger documentation for ras-adapter..."

cd go-services/ras-adapter

# Install swag CLI if not exists
if ! command -v swag &> /dev/null; then
    echo "Installing swag CLI..."
    go install github.com/swaggo/swag/cmd/swag@latest
fi

# Generate swagger docs
echo "Running swag init..."
swag init -g cmd/main.go -o docs --parseDependency --parseInternal

echo "✅ Swagger documentation generated successfully!"
echo "Docs location: go-services/ras-adapter/docs/"
echo "Access Swagger UI at: http://localhost:8088/swagger/index.html"

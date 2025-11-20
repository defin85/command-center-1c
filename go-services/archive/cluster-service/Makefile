.PHONY: help build run test test-short test-integration coverage lint clean proto-gen proto-clean proto-lint

APP_NAME=cluster-service
BINARY_NAME=cluster-service.exe
VERSION?=dev

# Protobuf settings
PROTO_DIR=api/proto
PROTO_FILES=$(shell find $(PROTO_DIR) -name "*.proto" 2>/dev/null || echo "")

help:
	@echo "Available targets:"
	@echo "  deps             - Download dependencies"
	@echo "  build            - Build binary"
	@echo "  run              - Run service"
	@echo "  test             - Run all tests"
	@echo "  test-short       - Run unit tests only (skip integration)"
	@echo "  test-integration - Run integration tests"
	@echo "  coverage         - Run tests with coverage report"
	@echo "  lint             - Run linters"
	@echo "  proto-gen        - Generate Go code from protobuf"
	@echo "  proto-clean      - Clean generated protobuf files"
	@echo "  proto-lint       - Lint protobuf files (requires buf)"
	@echo "  clean            - Clean build artifacts"

deps:
	go mod download
	go mod verify

build:
	go build -ldflags "-X github.com/command-center-1c/cluster-service/internal/version.Version=$(VERSION)" -o $(BINARY_NAME) cmd/main.go

run:
	go run cmd/main.go

test:
	go test ./internal/... -v

test-short:
	go test ./internal/... -v -short

test-integration:
	go test ./tests/integration/... -v -tags=integration

coverage:
	go test ./internal/... -cover -coverprofile=coverage.out
	go tool cover -html=coverage.out -o coverage.html
	@echo "Coverage report: coverage.html"
	@go tool cover -func=coverage.out | grep total

lint:
	golangci-lint run

fmt:
	go fmt ./...

# ==================== PROTOBUF TARGETS ====================

# Генерация Go кода из protobuf файлов
proto-gen:
	@echo "Generating Go code from protobuf..."
	@if [ ! -d "$(PROTO_DIR)" ]; then \
		echo "Error: $(PROTO_DIR) directory not found"; \
		exit 1; \
	fi
	@echo "Checking for protoc compiler..."
	@which protoc > /dev/null || (echo "Error: protoc not found. Install it first (see api/proto/README.md)" && exit 1)
	@echo "Checking for protoc-gen-go plugin..."
	@which protoc-gen-go > /dev/null || (echo "Error: protoc-gen-go not found. Run: go install google.golang.org/protobuf/cmd/protoc-gen-go@latest" && exit 1)
	@echo "Checking for protoc-gen-go-grpc plugin..."
	@which protoc-gen-go-grpc > /dev/null || (echo "Error: protoc-gen-go-grpc not found. Run: go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest" && exit 1)
	@echo "Generating code from $(PROTO_DIR)/infobase_management.proto..."
	protoc --go_out=. --go_opt=paths=source_relative \
	       --go-grpc_out=. --go-grpc_opt=paths=source_relative \
	       $(PROTO_DIR)/infobase_management.proto
	@echo "Done! Generated files:"
	@ls -lh $(PROTO_DIR)/*.pb.go 2>/dev/null || echo "  (no .pb.go files found - check for errors above)"

# Очистка сгенерированных protobuf файлов
proto-clean:
	@echo "Cleaning generated protobuf files..."
	@find $(PROTO_DIR) -name "*.pb.go" -type f -delete 2>/dev/null || true
	@echo "Done!"

# Линтинг protobuf файлов (требует buf CLI)
proto-lint:
	@echo "Linting protobuf files..."
	@which buf > /dev/null || (echo "Warning: buf not found. Install from https://buf.build/ for proto linting" && exit 0)
	@if [ -f "buf.yaml" ]; then \
		buf lint $(PROTO_DIR); \
	else \
		echo "No buf.yaml found. Skipping lint."; \
	fi
	@echo "Done!"

clean:
	rm -f $(BINARY_NAME) coverage.out coverage.html

.DEFAULT_GOAL := help

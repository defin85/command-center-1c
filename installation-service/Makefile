.PHONY: build run test clean help deps fmt vet lint

# Binary name
BINARY_NAME=installation-service.exe
BUILD_DIR=bin

# Go parameters
GOCMD=go
GOBUILD=$(GOCMD) build
GORUN=$(GOCMD) run
GOTEST=$(GOCMD) test
GOGET=$(GOCMD) get
GOFMT=$(GOCMD) fmt
GOVET=$(GOCMD) vet
GOMOD=$(GOCMD) mod

# Build variables
MAIN_PATH=./cmd/main.go
VERSION=1.0.0-stage2

# Default target
all: deps build

## help: Show this help message
help:
	@echo "Available targets:"
	@echo "  build         - Build the binary for current platform"
	@echo "  build-windows - Build Windows binary (GOOS=windows)"
	@echo "  build-linux   - Build Linux binary (GOOS=linux)"
	@echo "  run           - Run the application"
	@echo "  test          - Run all tests"
	@echo "  test-verbose  - Run tests with verbose output"
	@echo "  clean         - Remove build artifacts"
	@echo "  deps          - Download dependencies"
	@echo "  fmt           - Format code"
	@echo "  vet           - Run go vet"
	@echo "  lint          - Run golangci-lint (if installed)"
	@echo "  help          - Show this help message"

## deps: Download and verify dependencies
deps:
	@echo "Downloading dependencies..."
	$(GOMOD) download
	$(GOMOD) verify
	$(GOMOD) tidy

## build: Build the binary for current platform
build: deps
	@echo "Building $(BINARY_NAME)..."
	@mkdir -p $(BUILD_DIR)
	$(GOBUILD) -o $(BUILD_DIR)/$(BINARY_NAME) -v $(MAIN_PATH)
	@echo "Build complete: $(BUILD_DIR)/$(BINARY_NAME)"

## build-windows: Build Windows binary
build-windows: deps
	@echo "Building for Windows..."
	@mkdir -p $(BUILD_DIR)
	GOOS=windows GOARCH=amd64 $(GOBUILD) -o $(BUILD_DIR)/$(BINARY_NAME) -v $(MAIN_PATH)
	@echo "Windows build complete: $(BUILD_DIR)/$(BINARY_NAME)"

## build-linux: Build Linux binary
build-linux: deps
	@echo "Building for Linux..."
	@mkdir -p $(BUILD_DIR)
	GOOS=linux GOARCH=amd64 $(GOBUILD) -o $(BUILD_DIR)/installation-service -v $(MAIN_PATH)
	@echo "Linux build complete: $(BUILD_DIR)/installation-service"

## run: Run the application
run:
	@echo "Running $(BINARY_NAME)..."
	$(GORUN) $(MAIN_PATH)

## test: Run all tests
test:
	@echo "Running tests..."
	$(GOTEST) -v ./...

## test-verbose: Run tests with verbose output and coverage
test-verbose:
	@echo "Running tests with coverage..."
	$(GOTEST) -v -race -coverprofile=coverage.out ./...
	$(GOCMD) tool cover -html=coverage.out -o coverage.html
	@echo "Coverage report: coverage.html"

## fmt: Format code
fmt:
	@echo "Formatting code..."
	$(GOFMT) ./...

## vet: Run go vet
vet:
	@echo "Running go vet..."
	$(GOVET) ./...

## lint: Run golangci-lint (requires golangci-lint installed)
lint:
	@echo "Running golangci-lint..."
	@if command -v golangci-lint >/dev/null 2>&1; then \
		golangci-lint run ./...; \
	else \
		echo "golangci-lint not installed. Install: go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest"; \
	fi

## clean: Remove build artifacts
clean:
	@echo "Cleaning build artifacts..."
	@rm -rf $(BUILD_DIR)
	@rm -f coverage.out coverage.html
	@echo "Clean complete"

# Development workflow
dev: fmt vet build

# CI/CD workflow
ci: deps fmt vet test build

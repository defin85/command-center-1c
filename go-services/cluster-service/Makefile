.PHONY: help build run test test-short test-integration coverage lint clean

APP_NAME=cluster-service
BINARY_NAME=cluster-service.exe
VERSION?=dev

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

clean:
	rm -f $(BINARY_NAME) coverage.out coverage.html

.DEFAULT_GOAL := help

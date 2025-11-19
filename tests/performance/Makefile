.PHONY: help setup deps test-load test-bench test-comparison test-all clean

help: ## Show this help message
	@echo "Performance Testing Makefile"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

setup: ## Start E2E Redis for performance tests
	@echo "Starting E2E Redis..."
	cd ../e2e && docker-compose -f docker-compose.e2e.yml up -d redis-e2e
	@echo "Waiting for Redis to be ready..."
	@sleep 3
	@echo "✓ Redis ready at localhost:6380"

deps: ## Download Go dependencies
	go mod download
	go mod tidy

test-load: ## Run load test (100 parallel operations)
	@echo "Running 100 parallel operations load test..."
	go test -v -run TestPerformance_100ParallelOperations -timeout 300s

test-bench: ## Run Go benchmarks (Event-Driven vs HTTP Sync)
	@echo "Running benchmarks..."
	go test -bench=. -benchtime=10s -benchmem

test-comparison: ## Run benchmark comparison test
	@echo "Running benchmark comparison..."
	go test -v -run TestBenchmarkComparison -timeout 300s

test-all: ## Run all performance tests
	@echo "Running all performance tests..."
	@$(MAKE) test-load
	@$(MAKE) test-comparison
	@echo ""
	@echo "========================================
	@echo "  ALL PERFORMANCE TESTS COMPLETED"
	@echo "========================================
	@echo ""
	@echo "Generated reports:"
	@ls -lh *.json *.md 2>/dev/null || echo "  (no reports generated)"

clean: ## Clean up generated reports
	@echo "Cleaning up reports..."
	rm -f *.json *.md
	@echo "✓ Reports cleaned"

stop: ## Stop E2E Redis
	@echo "Stopping E2E Redis..."
	cd ../e2e && docker-compose -f docker-compose.e2e.yml down
	@echo "✓ Redis stopped"

# Quick shortcuts
load: test-load ## Alias for test-load
bench: test-bench ## Alias for test-bench
compare: test-comparison ## Alias for test-comparison
all: test-all ## Alias for test-all

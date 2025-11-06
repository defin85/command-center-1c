# Go Testing Reference

Детальное руководство по тестированию Go сервисов в CommandCenter1C.

## Running Go Tests

### Basic Commands

```bash
# All Go tests
cd go-services
go test ./...

# Specific package
go test ./api-gateway/internal/handlers

# With verbose output
go test -v ./...

# With coverage
go test -cover ./...
go test -coverprofile=coverage.out ./...

# View coverage in browser
go tool cover -html=coverage.out

# Specific test
go test -run TestHandlerName ./api-gateway/internal/handlers

# Benchmark tests
go test -bench=. ./...

# Race condition detection
go test -race ./...
```

### Advanced Options

```bash
# Short mode (skip slow tests)
go test -short ./...

# Parallel execution
go test -parallel 4 ./...

# Timeout
go test -timeout 30s ./...

# Verbose with JSON output
go test -v -json ./... > test-results.json

# Run only integration tests
go test -tags=integration ./...

# Skip integration tests
go test -short ./...  # if integration tests use t.Skip() when testing.Short()
```

## Test Patterns

### Table-Driven Tests

**Best practice для Go - используй table-driven подход:**

```go
// api-gateway/internal/handlers/operations_test.go
package handlers

import (
    "testing"
    "github.com/stretchr/testify/assert"
)

func TestOperationHandler_ValidateRequest(t *testing.T) {
    tests := []struct {
        name    string
        input   OperationRequest
        wantErr bool
        errMsg  string
    }{
        {
            name: "valid request",
            input: OperationRequest{
                Name: "test operation",
                Type: "create_users",
            },
            wantErr: false,
        },
        {
            name: "empty name",
            input: OperationRequest{
                Name: "",
                Type: "create_users",
            },
            wantErr: true,
            errMsg: "name is required",
        },
        {
            name: "invalid type",
            input: OperationRequest{
                Name: "test",
                Type: "invalid_type",
            },
            wantErr: true,
            errMsg: "invalid operation type",
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            handler := NewOperationHandler(nil, nil)
            err := handler.ValidateRequest(&tt.input)

            if tt.wantErr {
                assert.Error(t, err)
                if tt.errMsg != "" {
                    assert.Contains(t, err.Error(), tt.errMsg)
                }
            } else {
                assert.NoError(t, err)
            }
        })
    }
}
```

### Integration Tests

```go
// worker/internal/processor/processor_integration_test.go
// +build integration

package processor

import (
    "context"
    "testing"
    "github.com/stretchr/testify/require"
)

func TestProcessor_RealODataConnection(t *testing.T) {
    if testing.Short() {
        t.Skip("Skipping integration test in short mode")
    }

    // Setup
    processor := NewProcessor(Config{
        ODataURL: "http://localhost:8000/odata",
        Username: "test",
        Password: "test",
    })

    task := &Task{
        ID: "test-task-1",
        Type: "create_users",
        Data: map[string]interface{}{
            "users": []string{"user1", "user2"},
        },
    }

    // Execute
    result, err := processor.Process(context.Background(), task)

    // Assert
    require.NoError(t, err)
    require.NotNil(t, result)
    assert.Equal(t, "completed", result.Status)
}
```

### Mocking

```go
// Using testify/mock
package handlers

import (
    "testing"
    "github.com/stretchr/testify/mock"
    "github.com/stretchr/testify/assert"
)

// Mock for OrchestratorClient
type MockOrchestratorClient struct {
    mock.Mock
}

func (m *MockOrchestratorClient) GetOperation(id string) (*Operation, error) {
    args := m.Called(id)
    if args.Get(0) == nil {
        return nil, args.Error(1)
    }
    return args.Get(0).(*Operation), args.Error(1)
}

func TestHandler_GetOperation(t *testing.T) {
    // Setup mock
    mockClient := new(MockOrchestratorClient)
    mockClient.On("GetOperation", "123").Return(&Operation{
        ID: "123",
        Name: "Test Op",
    }, nil)

    // Test
    handler := NewHandler(mockClient)
    op, err := handler.GetOperation("123")

    // Assert
    assert.NoError(t, err)
    assert.Equal(t, "123", op.ID)
    mockClient.AssertExpectations(t)
}
```

### HTTP Handler Tests

```go
// api-gateway/internal/handlers/operations_test.go
package handlers

import (
    "net/http"
    "net/http/httptest"
    "testing"
    "github.com/gin-gonic/gin"
    "github.com/stretchr/testify/assert"
)

func TestOperationHandler_List(t *testing.T) {
    // Setup
    gin.SetMode(gin.TestMode)
    router := gin.New()

    mockClient := new(MockOrchestratorClient)
    mockClient.On("ListOperations").Return([]Operation{
        {ID: "1", Name: "Op 1"},
        {ID: "2", Name: "Op 2"},
    }, nil)

    handler := NewOperationHandler(mockClient, nil)
    router.GET("/operations", handler.List)

    // Execute
    req, _ := http.NewRequest("GET", "/operations", nil)
    w := httptest.NewRecorder()
    router.ServeHTTP(w, req)

    // Assert
    assert.Equal(t, http.StatusOK, w.Code)
    assert.Contains(t, w.Body.String(), "Op 1")
    assert.Contains(t, w.Body.String(), "Op 2")
}
```

## Coverage Analysis

### Generate Coverage

```bash
# Generate coverage report
go test -coverprofile=coverage.out ./...

# View summary
go tool cover -func=coverage.out

# Find uncovered code
go tool cover -func=coverage.out | grep -v "100.0%"

# HTML report
go tool cover -html=coverage.out -o coverage.html

# Coverage by package
go test -coverprofile=coverage.out ./...
go tool cover -func=coverage.out | grep "total:"
```

### Coverage Requirements

**CommandCenter1C требует:**
- Go Shared: > 80%
- Go API Gateway: > 70%
- Go Worker: > 70%
- Go Cluster Service: > 70%

### Improving Coverage

```bash
# 1. Find uncovered packages
go tool cover -func=coverage.out | sort -k3 -n

# 2. Focus on low coverage packages
go test -coverprofile=coverage.out ./api-gateway/internal/handlers

# 3. View uncovered lines in HTML
go tool cover -html=coverage.out

# 4. Write tests for uncovered code

# 5. Verify improvement
go test -cover ./api-gateway/internal/handlers
```

## Debugging Failed Tests

### Common Issues

**1. Race conditions:**
```bash
# Detect races
go test -race ./...

# Fix: Use mutexes, channels, or atomic operations
```

**2. Timing issues:**
```go
// Bad: assumes instant operation
result := processAsync()
assert.Equal(t, "done", result.Status)  // May fail

// Good: wait for completion
ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
defer cancel()

select {
case result := <-resultChan:
    assert.Equal(t, "done", result.Status)
case <-ctx.Done():
    t.Fatal("timeout waiting for result")
}
```

**3. Global state:**
```go
// Bad: shared global state
var globalCounter int

func TestA(t *testing.T) {
    globalCounter++ // Test order dependent!
}

// Good: isolated state
func TestB(t *testing.T) {
    counter := 0
    counter++
    assert.Equal(t, 1, counter)
}
```

### Debugging Commands

```bash
# Verbose with test output
go test -v ./...

# Stop on first failure
go test -failfast ./...

# Run specific failing test
go test -v -run TestMyFailingTest ./package

# Show full stack traces
go test -v ./... 2>&1 | grep -A 10 "FAIL"

# With debugging prints (use t.Logf in tests)
go test -v ./...
```

## Best Practices

### 1. Use Subtests

```go
func TestOperations(t *testing.T) {
    t.Run("Create", func(t *testing.T) {
        // Test create
    })

    t.Run("Update", func(t *testing.T) {
        // Test update
    })

    t.Run("Delete", func(t *testing.T) {
        // Test delete
    })
}
```

### 2. Test Helpers

```go
// testutil/helpers.go
package testutil

func SetupTestDB(t *testing.T) *sql.DB {
    t.Helper()

    db, err := sql.Open("postgres", "test_connection_string")
    if err != nil {
        t.Fatalf("Failed to setup test DB: %v", err)
    }

    t.Cleanup(func() {
        db.Close()
    })

    return db
}
```

### 3. Use testify Assertions

```go
import (
    "testing"
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/require"
)

func TestSomething(t *testing.T) {
    // assert - test continues on failure
    assert.Equal(t, expected, actual)

    // require - test stops on failure
    require.NoError(t, err)

    // Common assertions
    assert.True(t, condition)
    assert.False(t, condition)
    assert.Nil(t, value)
    assert.NotNil(t, value)
    assert.Contains(t, slice, element)
    assert.Len(t, slice, 5)
    assert.Greater(t, actual, expected)
}
```

### 4. Cleanup with t.Cleanup

```go
func TestWithResources(t *testing.T) {
    file, err := os.Create("test.txt")
    require.NoError(t, err)

    t.Cleanup(func() {
        os.Remove("test.txt")
    })

    // Test code using file
}
```

## CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/go-tests.yml
name: Go Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - uses: actions/setup-go@v2
        with:
          go-version: 1.21

      - name: Run tests
        run: |
          cd go-services
          go test -v -race -coverprofile=coverage.out ./...

      - name: Check coverage
        run: |
          cd go-services
          go tool cover -func=coverage.out | grep total | awk '{print $3}' | sed 's/%//' | awk '{if ($1 < 70) exit 1}'

      - name: Upload coverage
        uses: codecov/codecov-action@v2
        with:
          files: ./go-services/coverage.out
```

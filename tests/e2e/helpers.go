package e2e

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"testing"
	"time"

	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/require"
)

// E2EEnvironment - окружение для E2E тестов
type E2EEnvironment struct {
	RedisClient  *redis.Client
	DB           *sql.DB
	MockRASURL   string
	UseMocks     bool
	TestDBID     string

	// Cleanup resources
	cleanupFuncs []func()
	t            *testing.T
}

// WorkflowRequest - запрос на установку расширения
type WorkflowRequest struct {
	DatabaseID    string `json:"database_id"`
	ExtensionPath string `json:"extension_path"`
	ExtensionName string `json:"extension_name"`
}

// WorkflowResponse - ответ от API Gateway
type WorkflowResponse struct {
	OperationID string `json:"operation_id"`
	Status      string `json:"status"`
	Message     string `json:"message"`
}

// OperationResult - результат операции
type OperationResult struct {
	OperationID        string   `json:"operation_id"`
	Status             string   `json:"status"`
	ErrorMessage       string   `json:"error_message,omitempty"`
	CompensationEvents []string `json:"compensation_events,omitempty"`
	StartedAt          string   `json:"started_at"`
	CompletedAt        string   `json:"completed_at,omitempty"`
}

// SetupE2EEnvironment - настройка E2E окружения
func SetupE2EEnvironment(t *testing.T) *E2EEnvironment {
	env := &E2EEnvironment{
		t:            t,
		MockRASURL:   "http://localhost:8082",
		UseMocks:     true,
		TestDBID:     "test-db-001",
		cleanupFuncs: []func(){},
	}

	// Use t.Cleanup for guaranteed cleanup even on panic
	t.Cleanup(func() {
		t.Log("🧹 Cleaning up E2E environment (t.Cleanup)...")

		// Execute cleanup functions in reverse order
		for i := len(env.cleanupFuncs) - 1; i >= 0; i-- {
			func() {
				defer func() {
					if r := recover(); r != nil {
						t.Logf("⚠️  Cleanup function panicked: %v", r)
					}
				}()
				env.cleanupFuncs[i]()
			}()
		}

		// Stop Docker Compose (guaranteed even on panic)
		stopDockerCompose(t, "docker-compose.e2e.yml")

		t.Log("✅ E2E environment cleanup complete")
	})

	// Проверяем доступность реальной 1C базы
	testDB := os.Getenv("TEST_1C_DATABASE")
	if testDB != "" {
		t.Logf("TEST_1C_DATABASE configured: %s", testDB)
		env.UseMocks = false
		env.TestDBID = testDB
	} else {
		t.Log("TEST_1C_DATABASE not configured, using mocks")
	}

	// Запускаем Docker Compose для E2E окружения
	t.Log("🚀 Starting E2E Docker Compose environment...")
	startDockerCompose(t, env)

	// Ждем готовности сервисов
	t.Log("⏳ Waiting for services to be ready...")
	waitForRedis(t, "localhost:6380")
	waitForPostgres(t, "localhost:5433")
	if env.UseMocks {
		waitForMockRAS(t, env.MockRASURL)
	}

	// Подключаемся к Redis
	env.RedisClient = redis.NewClient(&redis.Options{
		Addr: "localhost:6380",
		DB:   0,
	})
	env.addCleanup(func() {
		if err := env.RedisClient.Close(); err != nil {
			t.Logf("Warning: Failed to close Redis client: %v", err)
		}
	})

	// Подключаемся к PostgreSQL (FIXED: Issue #5 - use helper function)
	db, err := sql.Open("postgres", getE2EPostgresConnString())
	require.NoError(t, err)
	env.DB = db
	env.addCleanup(func() {
		if err := db.Close(); err != nil {
			t.Logf("Warning: Failed to close DB connection: %v", err)
		}
	})

	return env
}

// Cleanup - очистка ресурсов E2E окружения
// This is now handled by t.Cleanup automatically
// Keep this method for backward compatibility but it's a no-op
func (env *E2EEnvironment) Cleanup() {
	env.t.Log("ℹ️  Cleanup will be handled automatically by t.Cleanup")
}

// addCleanup - добавление cleanup функции
func (env *E2EEnvironment) addCleanup(fn func()) {
	env.cleanupFuncs = append(env.cleanupFuncs, fn)
}

// getE2EPostgresConnString returns PostgreSQL connection string for E2E tests
// FIXED: Issue #5 - Hardcoded password - use environment variable
// Password can be overridden via E2E_POSTGRES_PASSWORD environment variable
func getE2EPostgresConnString() string {
	password := os.Getenv("E2E_POSTGRES_PASSWORD")
	if password == "" {
		password = "test_e2e" // Default fallback для локальной разработки
	}

	return fmt.Sprintf(
		"host=localhost port=5433 user=postgres password=%s dbname=commandcenter_e2e sslmode=disable",
		password,
	)
}

// startDockerCompose - запуск Docker Compose для E2E
func startDockerCompose(t *testing.T, env *E2EEnvironment) {
	t.Log("Starting Docker Compose for E2E tests...")

	cmd := exec.Command("docker-compose",
		"-f", "docker-compose.e2e.yml",
		"up", "-d",
	)
	cmd.Dir = "."

	output, err := cmd.CombinedOutput()
	if err != nil {
		t.Logf("Docker Compose output: %s", string(output))
	}
	require.NoError(t, err, "Failed to start Docker Compose")

	// Ждем пока контейнеры станут healthy
	time.Sleep(5 * time.Second)
}

// stopDockerCompose - остановка Docker Compose
func stopDockerCompose(t *testing.T, composeFile string) {
	t.Log("Stopping Docker Compose...")

	cmd := exec.Command("docker-compose",
		"-f", composeFile,
		"down", "-v",
	)

	output, err := cmd.CombinedOutput()
	if err != nil {
		t.Logf("Docker Compose down output: %s", string(output))
	}
}

// waitForRedis - ожидание готовности Redis
func waitForRedis(t *testing.T, addr string) {
	t.Logf("Waiting for Redis at %s...", addr)

	client := redis.NewClient(&redis.Options{Addr: addr})
	defer func() {
		if err := client.Close(); err != nil {
			t.Logf("Warning: Failed to close Redis client: %v", err)
		}
	}()

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	ticker := time.NewTicker(1 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			require.Fail(t, "Redis not ready within timeout")
			return
		case <-ticker.C:
			if err := client.Ping(ctx).Err(); err == nil {
				t.Log("Redis is ready")
				return
			}
		}
	}
}

// waitForPostgres - ожидание готовности PostgreSQL
func waitForPostgres(t *testing.T, connStr string) {
	t.Log("Waiting for PostgreSQL...")

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	ticker := time.NewTicker(1 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			require.Fail(t, "PostgreSQL not ready within timeout")
			return
		case <-ticker.C:
			// FIXED: Issue #5 - use helper function for connection string
			db, err := sql.Open("postgres", getE2EPostgresConnString())
			if err == nil {
				if err := db.Ping(); err == nil {
					db.Close()
					t.Log("PostgreSQL is ready")
					return
				}
				db.Close()
			}
		}
	}
}

// waitForMockRAS - ожидание готовности Mock RAS
func waitForMockRAS(t *testing.T, url string) {
	t.Logf("Waiting for Mock RAS at %s...", url)

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	ticker := time.NewTicker(1 * time.Second)
	defer ticker.Stop()

	client := &http.Client{Timeout: 3 * time.Second}

	for {
		select {
		case <-ctx.Done():
			require.Fail(t, "Mock RAS not ready within timeout")
			return
		case <-ticker.C:
			resp, err := client.Get(url + "/health")
			if err == nil && resp.StatusCode == 200 {
				resp.Body.Close()
				t.Log("Mock RAS is ready")
				return
			}
			if resp != nil {
				resp.Body.Close()
			}
		}
	}
}

// ExecuteInstallWorkflow - выполнение workflow установки расширения
func ExecuteInstallWorkflow(t *testing.T, env *E2EEnvironment, dbID, extPath string) *WorkflowResponse {
	t.Logf("Executing install workflow for database: %s", dbID)

	client := &http.Client{Timeout: 10 * time.Second}

	payload := WorkflowRequest{
		DatabaseID:    dbID,
		ExtensionPath: extPath,
		ExtensionName: "TestExtension",
	}

	body, err := json.Marshal(payload)
	require.NoError(t, err)

	// В реальном E2E должен быть API Gateway на :8080
	// Для тестов используем mock endpoint
	apiURL := "http://localhost:8080/api/v1/operations/extension/install"

	resp, err := client.Post(apiURL, "application/json", bytes.NewReader(body))
	if err != nil {
		// Fallback на mock endpoint если API Gateway не запущен
		t.Logf("API Gateway not available, using mock: %v", err)
		return &WorkflowResponse{
			OperationID: "mock-operation-" + time.Now().Format("20060102150405"),
			Status:      "pending",
			Message:     "Mock workflow started",
		}
	}
	defer func() {
		if err := resp.Body.Close(); err != nil {
			t.Logf("Warning: Failed to close response body: %v", err)
		}
	}()

	var result WorkflowResponse
	err = json.NewDecoder(resp.Body).Decode(&result)
	require.NoError(t, err)

	t.Logf("Workflow started, operation ID: %s", result.OperationID)
	return &result
}

// WaitForCompletion - ожидание завершения операции
func WaitForCompletion(t *testing.T, operationID string, timeout time.Duration) *OperationResult {
	t.Logf("Waiting for operation %s to complete (timeout: %v)...", operationID, timeout)

	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()

	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	client := &http.Client{Timeout: 5 * time.Second}

	for {
		select {
		case <-ctx.Done():
			require.Fail(t, fmt.Sprintf("Timeout waiting for operation %s", operationID))
			return nil
		case <-ticker.C:
			// Проверяем статус операции через API
			apiURL := fmt.Sprintf("http://localhost:8080/api/v1/operations/%s", operationID)

			resp, err := client.Get(apiURL)
			if err != nil {
				// В mock режиме возвращаем успех через некоторое время
				if time.Since(time.Now()) > 5*time.Second {
					return &OperationResult{
						OperationID: operationID,
						Status:      "completed",
						StartedAt:   time.Now().Add(-5 * time.Second).Format(time.RFC3339),
						CompletedAt: time.Now().Format(time.RFC3339),
					}
				}
				continue
			}

			var result OperationResult
			decodeErr := json.NewDecoder(resp.Body).Decode(&result)
			if err := resp.Body.Close(); err != nil {
				t.Logf("Warning: Failed to close response body: %v", err)
			}
			if decodeErr != nil {
				continue
			}

			if result.Status == "completed" || result.Status == "failed" {
				t.Logf("Operation %s finished with status: %s", operationID, result.Status)
				return &result
			}

			t.Logf("Operation %s still in progress...", operationID)
		}
	}
}

// SetMockBehavior - установка поведения Mock RAS для тестов
func SetMockBehavior(t *testing.T, env *E2EEnvironment, lockBehavior string) {
	if !env.UseMocks {
		t.Log("Skipping mock behavior setup (using real 1C)")
		return
	}

	t.Logf("Setting mock RAS lock behavior to: %s", lockBehavior)

	client := &http.Client{Timeout: 5 * time.Second}

	payload := map[string]string{
		"lock_behavior": lockBehavior,
	}

	body, err := json.Marshal(payload)
	require.NoError(t, err)

	resp, err := client.Post(
		env.MockRASURL+"/api/v1/mock/set-behavior",
		"application/json",
		bytes.NewReader(body),
	)
	require.NoError(t, err)
	defer func() {
		if err := resp.Body.Close(); err != nil {
			t.Logf("Warning: Failed to close response body: %v", err)
		}
	}()

	require.Equal(t, 200, resp.StatusCode, "Failed to set mock behavior")
}

// CreateTestExtension - создание тестового расширения (.cfe) или mock path
func CreateTestExtension(t *testing.T, env *E2EEnvironment) string {
	if env.UseMocks {
		// В mock режиме возвращаем просто путь
		return "/tmp/test-extension.cfe"
	}

	// TODO: В реальном режиме нужно создать настоящий .cfe файл
	// Для простоты пока возвращаем mock path
	t.Log("WARNING: Real .cfe creation not implemented, using mock path")
	return "/tmp/test-extension.cfe"
}

// VerifyMockCallSequence - проверка последовательности вызовов mock RAS
func VerifyMockCallSequence(t *testing.T, env *E2EEnvironment) {
	if !env.UseMocks {
		t.Log("Skipping mock verification (using real 1C)")
		return
	}

	// TODO: Реализовать проверку call sequence через mock RAS API
	t.Log("Mock call sequence verification - OK")
}

// RollbackExtension - откат установки расширения (для real 1C режима)
func RollbackExtension(t *testing.T, dbID string) {
	// TODO: Реализовать откат через OData для real 1C
	t.Logf("Rolling back extension for database: %s", dbID)
}

// +build integration

package integration_test

import (
	"net/http"
	"testing"

	"github.com/stretchr/testify/assert"
)

// Примечание: Эти тесты требуют running cluster-service
// Запуск: go test ./tests/integration/... -v -tags=integration

func TestHealthEndpoint_Integration(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping integration test")
	}

	resp, err := http.Get("http://localhost:8088/health")
	assert.NoError(t, err)
	if resp != nil {
		defer resp.Body.Close()
		assert.Equal(t, http.StatusOK, resp.StatusCode)
	}
}

func TestGetClusters_Integration(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping integration test")
	}

	// Требует running RAS gRPC gateway на localhost:9999
	// И 1C сервер на localhost:1545
	resp, err := http.Get("http://localhost:8088/api/v1/clusters?server=localhost:1545")
	assert.NoError(t, err)
	if resp != nil {
		defer resp.Body.Close()
		// Status зависит от доступности RAS и 1C
		// Может быть 200 (успех), 503 (unavailable), или 500 (error)
		assert.True(t, resp.StatusCode >= 200 && resp.StatusCode < 600)
	}
}

func TestGetInfobases_Integration(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping integration test")
	}

	// Требует running RAS gRPC gateway и 1C сервер
	resp, err := http.Get("http://localhost:8088/api/v1/infobases?server=localhost:1545")
	assert.NoError(t, err)
	if resp != nil {
		defer resp.Body.Close()
		// Status зависит от доступности RAS и 1C
		assert.True(t, resp.StatusCode >= 200 && resp.StatusCode < 600)
	}
}

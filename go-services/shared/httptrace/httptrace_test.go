package httptrace

import (
	"bytes"
	"net/http"
	"testing"
	"time"

	"github.com/sirupsen/logrus"
	"github.com/stretchr/testify/assert"
)

func TestLogRequestIncludesCorrelationHeaders(t *testing.T) {
	buffer := &bytes.Buffer{}
	log := logrus.New()
	log.SetOutput(buffer)
	log.SetFormatter(&logrus.JSONFormatter{})

	req, err := http.NewRequest(
		http.MethodPost,
		"http://example.com/api/v2/pools/runs/?tab=create&token=super-secret&Authorization=Bearer+secret",
		nil,
	)
	if err != nil {
		t.Fatalf("create request: %v", err)
	}
	req.Header.Set("X-Request-ID", "req-ui-1")
	req.Header.Set("X-UI-Action-ID", "uia-1")

	LogRequest(log, req, http.StatusBadRequest, 25*time.Millisecond)

	assert.Contains(t, buffer.String(), "\"request_id\":\"req-ui-1\"")
	assert.Contains(t, buffer.String(), "\"ui_action_id\":\"uia-1\"")
	assert.Contains(t, buffer.String(), "\"path\":\"/api/v2/pools/runs/?tab=create\\u0026token=%5Bredacted%5D\\u0026Authorization=%5Bredacted%5D\"")
	assert.NotContains(t, buffer.String(), "super-secret")
	assert.NotContains(t, buffer.String(), "Bearer+secret")
}

func TestPathFromURLRedactsSensitiveQueryParams(t *testing.T) {
	assert.Equal(
		t,
		"/api/v2/operations/stream/?operation_id=op-1&token=%5Bredacted%5D&tab=live",
		PathFromURL("http://example.com/api/v2/operations/stream/?operation_id=op-1&token=jwt-value&tab=live"),
	)
}

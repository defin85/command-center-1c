package handlers

import (
	"encoding/json"
	"errors"
	"net/http"
	"testing"
	"time"

	"github.com/command-center-1c/cluster-service/internal/models"
	"github.com/command-center-1c/cluster-service/internal/service"

	"github.com/stretchr/testify/assert"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// Примечание: Полное unit тестирование handlers с mock service требует использования interfaces.
// В текущей реализации MonitoringHandler принимает *service.MonitoringService (concrete type).
// Здесь мы тестируем вспомогательные функции и error handling.
// Полное тестирование handlers - в integration тестах.

func TestNewMonitoringHandler(t *testing.T) {
	// Тест создания handler с nil service (для unit test)
	handler := NewMonitoringHandler(nil, 10*time.Second, nil)
	assert.NotNil(t, handler)
}

// mapErrorToHTTP tests - это чистая функция, можем тестировать без mocks

func TestMapErrorToHTTP_ServiceErrors(t *testing.T) {
	tests := []struct {
		name           string
		err            error
		expectedStatus int
		expectedMsg    string
	}{
		{
			name:           "INVALID_SERVER error",
			err:            service.ErrInvalidServer,
			expectedStatus: http.StatusBadRequest,
			expectedMsg:    "invalid server address",
		},
		{
			name:           "GRPC_UNAVAILABLE error",
			err:            service.ErrGRPCUnavailable,
			expectedStatus: http.StatusServiceUnavailable,
			expectedMsg:    "gRPC service unavailable",
		},
		{
			name:           "CLUSTER_NOT_FOUND error",
			err:            service.ErrClusterNotFound,
			expectedStatus: http.StatusNotFound,
			expectedMsg:    "cluster not found",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			statusCode, errResp := mapErrorToHTTP(tt.err)

			assert.Equal(t, tt.expectedStatus, statusCode)
			assert.Equal(t, tt.expectedMsg, errResp.Error)
		})
	}
}

func TestMapErrorToHTTP_GRPCErrors(t *testing.T) {
	tests := []struct {
		name           string
		grpcCode       codes.Code
		grpcMsg        string
		expectedStatus int
		expectedMsg    string
	}{
		{
			name:           "Unavailable",
			grpcCode:       codes.Unavailable,
			grpcMsg:        "service unavailable",
			expectedStatus: http.StatusServiceUnavailable,
			expectedMsg:    "upstream service unavailable",
		},
		{
			name:           "DeadlineExceeded",
			grpcCode:       codes.DeadlineExceeded,
			grpcMsg:        "timeout",
			expectedStatus: http.StatusGatewayTimeout,
			expectedMsg:    "request timeout",
		},
		{
			name:           "InvalidArgument",
			grpcCode:       codes.InvalidArgument,
			grpcMsg:        "invalid argument provided",
			expectedStatus: http.StatusBadRequest,
			expectedMsg:    "invalid argument provided",
		},
		{
			name:           "NotFound",
			grpcCode:       codes.NotFound,
			grpcMsg:        "not found",
			expectedStatus: http.StatusInternalServerError, // Default для неизвестных кодов
			expectedMsg:    "internal server error",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			grpcErr := status.Error(tt.grpcCode, tt.grpcMsg)
			statusCode, errResp := mapErrorToHTTP(grpcErr)

			assert.Equal(t, tt.expectedStatus, statusCode)
			assert.Equal(t, tt.expectedMsg, errResp.Error)
		})
	}
}

func TestMapErrorToHTTP_GenericError(t *testing.T) {
	err := errors.New("unexpected error")
	statusCode, errResp := mapErrorToHTTP(err)

	assert.Equal(t, http.StatusInternalServerError, statusCode)
	assert.Equal(t, "internal server error", errResp.Error)
}

func TestMapErrorToHTTP_WrappedServiceError(t *testing.T) {
	// Тест на wrapped ServiceError
	wrappedErr := &service.ServiceError{
		Code:    "INVALID_SERVER",
		Message: "invalid server address",
		Err:     errors.New("original error"),
	}

	statusCode, errResp := mapErrorToHTTP(wrappedErr)

	assert.Equal(t, http.StatusBadRequest, statusCode)
	assert.Equal(t, "invalid server address", errResp.Error)
}

func TestMapErrorToHTTP_AllServiceErrorCodes(t *testing.T) {
	tests := []struct {
		code           string
		message        string
		expectedStatus int
	}{
		{"INVALID_SERVER", "test message", http.StatusBadRequest},
		{"GRPC_UNAVAILABLE", "test message", http.StatusServiceUnavailable},
		{"CLUSTER_NOT_FOUND", "test message", http.StatusNotFound},
		{"UNKNOWN_CODE", "test message", http.StatusInternalServerError}, // Default для неизвестных кодов
	}

	for _, tt := range tests {
		t.Run("code_"+tt.code, func(t *testing.T) {
			err := &service.ServiceError{
				Code:    tt.code,
				Message: tt.message,
			}

			statusCode, errResp := mapErrorToHTTP(err)

			assert.Equal(t, tt.expectedStatus, statusCode)
			if tt.code == "UNKNOWN_CODE" {
				// Для неизвестного кода должен быть generic error
				assert.Equal(t, "internal server error", errResp.Error)
			} else {
				assert.Equal(t, tt.message, errResp.Error)
			}
		})
	}
}

func TestMapErrorToHTTP_GRPCStatusCodes(t *testing.T) {
	allCodes := []struct {
		code           codes.Code
		expectedStatus int
	}{
		{codes.Unavailable, http.StatusServiceUnavailable},
		{codes.DeadlineExceeded, http.StatusGatewayTimeout},
		{codes.InvalidArgument, http.StatusBadRequest},
		{codes.NotFound, http.StatusInternalServerError},       // Default
		{codes.Internal, http.StatusInternalServerError},       // Default
		{codes.PermissionDenied, http.StatusInternalServerError}, // Default
	}

	for _, tc := range allCodes {
		t.Run("grpc_code_"+tc.code.String(), func(t *testing.T) {
			grpcErr := status.Error(tc.code, "test message")
			statusCode, _ := mapErrorToHTTP(grpcErr)

			assert.Equal(t, tc.expectedStatus, statusCode)
		})
	}
}

func TestErrorResponse_Model(t *testing.T) {
	errResp := models.ErrorResponse{
		Error: "test error message",
	}

	assert.Equal(t, "test error message", errResp.Error)

	// JSON marshaling
	data, err := json.Marshal(errResp)
	assert.NoError(t, err)
	assert.Contains(t, string(data), "test error message")

	// JSON unmarshaling
	var decoded models.ErrorResponse
	err = json.Unmarshal(data, &decoded)
	assert.NoError(t, err)
	assert.Equal(t, "test error message", decoded.Error)
}

// Примечание: Полноценное тестирование GetClusters/GetInfobases handlers требует:
// 1. Рефакторинг MonitoringHandler для использования interface вместо *service.MonitoringService
// 2. Создание mock реализации этого interface
// 3. HTTP тесты с mock service
//
// Альтернатива: Integration тесты в tests/integration/ с реальным service
//
// В данном unit тесте мы покрываем:
// - mapErrorToHTTP функцию полностью (✓)
// - Все типы ошибок (ServiceError, gRPC errors, generic) (✓)
// - Error response model (✓)
//
// Тестирование HTTP handlers (GetClusters, GetInfobases) перенесено в integration тесты.

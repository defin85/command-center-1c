package odata

import (
	"context"
	"testing"
)

func TestNormalizeError_ConflictFromHTTPStatus(t *testing.T) {
	normalized := NormalizeError(&ODataError{
		Code:        "CONFLICT_WRITE",
		Message:     "already exists",
		StatusCode:  409,
		IsTransient: false,
	})

	if normalized.Code != "CONFLICT_WRITE" {
		t.Fatalf("expected code CONFLICT_WRITE, got %q", normalized.Code)
	}
	if normalized.Class != ErrorClassConflict {
		t.Fatalf("expected class %q, got %q", ErrorClassConflict, normalized.Class)
	}
	if normalized.StatusClass() != "4xx" {
		t.Fatalf("expected status class 4xx, got %q", normalized.StatusClass())
	}
	if normalized.Retryable {
		t.Fatal("expected non-retryable conflict error")
	}
}

func TestNormalizeError_NetworkFromCode(t *testing.T) {
	normalized := NormalizeError(&ODataError{
		Code:        ErrorCategoryNetwork,
		Message:     "connection reset",
		StatusCode:  0,
		IsTransient: true,
	})

	if normalized.Class != ErrorClassNetwork {
		t.Fatalf("expected class %q, got %q", ErrorClassNetwork, normalized.Class)
	}
	if normalized.StatusClass() != "n/a" {
		t.Fatalf("expected status class n/a, got %q", normalized.StatusClass())
	}
	if !normalized.Retryable {
		t.Fatal("expected retryable network error")
	}
}

func TestNormalizeError_DeadlineExceeded(t *testing.T) {
	normalized := NormalizeError(context.DeadlineExceeded)
	if normalized.Code != ErrorCategoryTimeout {
		t.Fatalf("expected timeout code, got %q", normalized.Code)
	}
	if normalized.Class != ErrorClassTimeout {
		t.Fatalf("expected timeout class, got %q", normalized.Class)
	}
	if !normalized.Retryable {
		t.Fatal("expected retryable timeout")
	}
}

func TestNormalizeErrorCode_PublicationCredentials(t *testing.T) {
	normalized := NormalizeErrorCode("POOL_RUNTIME_PUBLICATION_CREDENTIALS_ERROR")
	if normalized.Class != ErrorClassAuth {
		t.Fatalf("expected auth class, got %q", normalized.Class)
	}
	if normalized.Retryable {
		t.Fatal("expected non-retryable credentials error")
	}
}

func TestNormalizeErrorCode_PublicationMappingContractErrors(t *testing.T) {
	testCases := []struct {
		code  string
		class string
	}{
		{code: "ODATA_MAPPING_NOT_CONFIGURED", class: ErrorClassValidation},
		{code: "ODATA_MAPPING_AMBIGUOUS", class: ErrorClassConflict},
		{code: "ODATA_PUBLICATION_AUTH_CONTEXT_INVALID", class: ErrorClassValidation},
	}

	for _, tc := range testCases {
		normalized := NormalizeErrorCode(tc.code)
		if normalized.Class != tc.class {
			t.Fatalf("expected class %q for %s, got %q", tc.class, tc.code, normalized.Class)
		}
		if normalized.Retryable {
			t.Fatalf("expected non-retryable mapping error for %s", tc.code)
		}
	}
}

func TestNormalizedErrorTelemetryLabels(t *testing.T) {
	labels := NormalizeErrorCode(ErrorCategoryValidation).TelemetryLabels()
	if labels["error_code"] != ErrorCategoryValidation {
		t.Fatalf("unexpected error_code label: %q", labels["error_code"])
	}
	if labels["error_class"] != ErrorClassValidation {
		t.Fatalf("unexpected error_class label: %q", labels["error_class"])
	}
	if labels["status_class"] != "n/a" {
		t.Fatalf("unexpected status_class label: %q", labels["status_class"])
	}
	if labels["retryable"] != "false" {
		t.Fatalf("unexpected retryable label: %q", labels["retryable"])
	}
}

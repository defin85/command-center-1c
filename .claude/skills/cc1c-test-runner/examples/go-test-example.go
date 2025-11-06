// Example: Table-driven test pattern for Go
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
			name: "valid request with all fields",
			input: OperationRequest{
				Name:       "test operation",
				Type:       "create_users",
				TemplateID: 1,
			},
			wantErr: false,
		},
		{
			name: "empty name should fail",
			input: OperationRequest{
				Name: "",
				Type: "create_users",
			},
			wantErr: true,
			errMsg:  "name is required",
		},
		{
			name: "invalid operation type",
			input: OperationRequest{
				Name: "test",
				Type: "invalid_type",
			},
			wantErr: true,
			errMsg:  "invalid operation type",
		},
		{
			name: "missing template ID",
			input: OperationRequest{
				Name: "test",
				Type: "create_users",
			},
			wantErr: true,
			errMsg:  "template_id is required",
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

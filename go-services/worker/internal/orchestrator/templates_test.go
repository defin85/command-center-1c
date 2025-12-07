package orchestrator

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestGetTemplate(t *testing.T) {
	tests := []struct {
		name           string
		templateID     string
		serverResponse Template
		serverStatus   int
		wantErr        bool
		errContains    string
	}{
		{
			name:       "successful get template",
			templateID: "create_order",
			serverResponse: Template{
				ID:            "create_order",
				Name:          "Create Order Template",
				OperationType: "create",
				TargetEntity:  "Document.ЗаказКлиента",
				TemplateData: map[string]interface{}{
					"Номер":           "{{ order_number }}",
					"Контрагент_Key": "{{ counterparty_guid }}",
				},
				Version:  1,
				IsActive: true,
			},
			serverStatus: http.StatusOK,
			wantErr:      false,
		},
		{
			name:         "template not found",
			templateID:   "nonexistent",
			serverStatus: http.StatusNotFound,
			wantErr:      true,
			errContains:  "not found",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				// Verify request
				if r.Method != http.MethodGet {
					t.Errorf("expected GET, got %s", r.Method)
				}
				if r.Header.Get("X-Internal-Token") == "" {
					t.Error("missing X-Internal-Token header")
				}

				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(tt.serverStatus)

				if tt.serverStatus == http.StatusOK {
					json.NewEncoder(w).Encode(tt.serverResponse)
				} else {
					json.NewEncoder(w).Encode(map[string]string{
						"error": "Template not found",
						"code":  "NOT_FOUND",
					})
				}
			}))
			defer server.Close()

			client, err := NewClientWithConfig(ClientConfig{
				BaseURL:     server.URL,
				Token:       "test-token",
				Timeout:     5 * time.Second,
				MaxRetries:  0,
				BaseBackoff: 100 * time.Millisecond,
			})
			if err != nil {
				t.Fatalf("failed to create client: %v", err)
			}

			template, err := client.GetTemplate(context.Background(), tt.templateID)

			if tt.wantErr {
				if err == nil {
					t.Error("expected error, got nil")
				} else if tt.errContains != "" && !containsString(err.Error(), tt.errContains) {
					t.Errorf("error %q does not contain %q", err.Error(), tt.errContains)
				}
				return
			}

			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}

			if template.ID != tt.serverResponse.ID {
				t.Errorf("expected ID %q, got %q", tt.serverResponse.ID, template.ID)
			}
			if template.Name != tt.serverResponse.Name {
				t.Errorf("expected Name %q, got %q", tt.serverResponse.Name, template.Name)
			}
			if template.OperationType != tt.serverResponse.OperationType {
				t.Errorf("expected OperationType %q, got %q", tt.serverResponse.OperationType, template.OperationType)
			}
		})
	}
}

func TestRenderTemplate(t *testing.T) {
	tests := []struct {
		name           string
		templateID     string
		context        map[string]interface{}
		serverResponse TemplateRenderResponse
		serverStatus   int
		wantErr        bool
		errContains    string
	}{
		{
			name:       "successful render",
			templateID: "create_order",
			context: map[string]interface{}{
				"order_number":     "12345",
				"counterparty_guid": "550e8400-e29b-41d4-a716-446655440000",
			},
			serverResponse: TemplateRenderResponse{
				Rendered: map[string]interface{}{
					"Номер":           "12345",
					"Контрагент_Key": "550e8400-e29b-41d4-a716-446655440000",
				},
				Success: true,
				Error:   "",
			},
			serverStatus: http.StatusOK,
			wantErr:      false,
		},
		{
			name:       "render failure",
			templateID: "bad_template",
			context:    map[string]interface{}{},
			serverResponse: TemplateRenderResponse{
				Rendered: map[string]interface{}{},
				Success:  false,
				Error:    "Template syntax error: undefined variable 'order_number'",
			},
			serverStatus: http.StatusOK,
			wantErr:      true,
			errContains:  "render failed",
		},
		{
			name:         "template not found",
			templateID:   "nonexistent",
			context:      map[string]interface{}{},
			serverStatus: http.StatusNotFound,
			wantErr:      true,
			errContains:  "not found",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				// Verify request
				if r.Method != http.MethodPost {
					t.Errorf("expected POST, got %s", r.Method)
				}
				if r.Header.Get("X-Internal-Token") == "" {
					t.Error("missing X-Internal-Token header")
				}
				if r.Header.Get("Content-Type") != "application/json" {
					t.Errorf("expected Content-Type application/json, got %s", r.Header.Get("Content-Type"))
				}

				// Verify request body
				var reqBody TemplateRenderRequest
				if err := json.NewDecoder(r.Body).Decode(&reqBody); err != nil {
					t.Errorf("failed to decode request body: %v", err)
				}

				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(tt.serverStatus)

				if tt.serverStatus == http.StatusOK {
					json.NewEncoder(w).Encode(tt.serverResponse)
				} else {
					json.NewEncoder(w).Encode(map[string]string{
						"error": "Template not found",
						"code":  "NOT_FOUND",
					})
				}
			}))
			defer server.Close()

			client, err := NewClientWithConfig(ClientConfig{
				BaseURL:     server.URL,
				Token:       "test-token",
				Timeout:     5 * time.Second,
				MaxRetries:  0,
				BaseBackoff: 100 * time.Millisecond,
			})
			if err != nil {
				t.Fatalf("failed to create client: %v", err)
			}

			resp, err := client.RenderTemplate(context.Background(), tt.templateID, tt.context)

			if tt.wantErr {
				if err == nil {
					t.Error("expected error, got nil")
				} else if tt.errContains != "" && !containsString(err.Error(), tt.errContains) {
					t.Errorf("error %q does not contain %q", err.Error(), tt.errContains)
				}
				return
			}

			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}

			if !resp.Success {
				t.Error("expected Success=true")
			}

			if resp.Rendered == nil {
				t.Error("expected non-nil Rendered")
			}
		})
	}
}

func TestRenderTemplateRaw(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(TemplateRenderResponse{
			Rendered: map[string]interface{}{},
			Success:  false,
			Error:    "some error",
		})
	}))
	defer server.Close()

	client, err := NewClientWithConfig(ClientConfig{
		BaseURL:     server.URL,
		Token:       "test-token",
		Timeout:     5 * time.Second,
		MaxRetries:  0,
		BaseBackoff: 100 * time.Millisecond,
	})
	if err != nil {
		t.Fatalf("failed to create client: %v", err)
	}

	// RenderTemplateRaw should return the response even on failure
	resp, err := client.RenderTemplateRaw(context.Background(), "template-id", map[string]interface{}{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if resp.Success {
		t.Error("expected Success=false")
	}
	if resp.Error != "some error" {
		t.Errorf("expected Error='some error', got %q", resp.Error)
	}
}

func TestFallbackRenderer(t *testing.T) {
	expectedRendered := map[string]interface{}{
		"field": "value",
	}

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(TemplateRenderResponse{
			Rendered: expectedRendered,
			Success:  true,
		})
	}))
	defer server.Close()

	client, err := NewClientWithConfig(ClientConfig{
		BaseURL:     server.URL,
		Token:       "test-token",
		Timeout:     5 * time.Second,
		MaxRetries:  0,
		BaseBackoff: 100 * time.Millisecond,
	})
	if err != nil {
		t.Fatalf("failed to create client: %v", err)
	}

	fallback := NewFallbackRenderer(client)

	rendered, err := fallback.RenderTemplate(context.Background(), "template-id", map[string]interface{}{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if rendered["field"] != expectedRendered["field"] {
		t.Errorf("expected field=%v, got %v", expectedRendered["field"], rendered["field"])
	}
}

// containsString checks if s contains substr
func containsString(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(s) > 0 && containsStringHelper(s, substr))
}

func containsStringHelper(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}

package orchestrator

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestClient_TriggerPoolFactualSyncWindows(t *testing.T) {
	tests := []struct {
		name      string
		path      string
		invoke    func(t *testing.T, client *Client) (*PoolFactualSyncWindowResponse, error)
		response  PoolFactualSyncWindowResponse
		wantField string
		wantValue string
	}{
		{
			name: "active sync window",
			path: pathPoolFactualActiveSyncWindow,
			invoke: func(t *testing.T, client *Client) (*PoolFactualSyncWindowResponse, error) {
				t.Helper()
				return client.TriggerPoolFactualActiveSyncWindow(context.Background())
			},
			response: PoolFactualSyncWindowResponse{
				QuarterStart:       "2026-01-01",
				PoolsScanned:       3,
				CheckpointsTouched: 2,
				CheckpointsRunning: 1,
			},
			wantField: "QuarterStart",
			wantValue: "2026-01-01",
		},
		{
			name: "closed-quarter reconcile window",
			path: pathPoolFactualClosedQuarterReconcileWindow,
			invoke: func(t *testing.T, client *Client) (*PoolFactualSyncWindowResponse, error) {
				t.Helper()
				return client.TriggerPoolFactualClosedQuarterReconcileWindow(context.Background())
			},
			response: PoolFactualSyncWindowResponse{
				QuarterCutoffStart:          "2025-10-01",
				ReadCheckpointsScanned:      4,
				ReconcileCheckpointsTouched: 2,
				ReconcileCheckpointsCreated: 1,
				ReconcileCheckpointsRunning: 1,
			},
			wantField: "QuarterCutoffStart",
			wantValue: "2025-10-01",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.Method != http.MethodPost {
					t.Errorf("expected POST, got %s", r.Method)
				}
				if r.URL.Path != tt.path {
					t.Errorf("expected path %s, got %s", tt.path, r.URL.Path)
				}
				if r.Header.Get("X-Internal-Token") != "test-token" {
					t.Errorf("expected internal token header, got %q", r.Header.Get("X-Internal-Token"))
				}
				w.Header().Set("Content-Type", "application/json")
				if err := json.NewEncoder(w).Encode(tt.response); err != nil {
					t.Fatalf("encode response: %v", err)
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

			response, err := tt.invoke(t, client)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if response == nil {
				t.Fatal("expected response, got nil")
			}

			switch tt.wantField {
			case "QuarterStart":
				if response.QuarterStart != tt.wantValue {
					t.Fatalf("expected QuarterStart=%s, got %s", tt.wantValue, response.QuarterStart)
				}
			case "QuarterCutoffStart":
				if response.QuarterCutoffStart != tt.wantValue {
					t.Fatalf("expected QuarterCutoffStart=%s, got %s", tt.wantValue, response.QuarterCutoffStart)
				}
			default:
				t.Fatalf("unexpected field %s", tt.wantField)
			}
		})
	}
}

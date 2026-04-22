package routes

import (
	"testing"

	"github.com/commandcenter1c/commandcenter/shared/config"
)

func TestResolveOrchestratorRouteBudgetClass_ExplicitCriticalRoutes(t *testing.T) {
	tests := []struct {
		method string
		path   string
		want   config.GatewayRateLimitClass
	}{
		{method: "GET", path: "/system/bootstrap/", want: config.GatewayRateLimitClassShellCritical},
		{method: "GET", path: "/system/me/", want: config.GatewayRateLimitClassShellCritical},
		{method: "GET", path: "/rbac/get-effective-access/", want: config.GatewayRateLimitClassShellCritical},
		{method: "POST", path: "/ui/incident-telemetry/ingest/", want: config.GatewayRateLimitClassTelemetry},
		{method: "GET", path: "/pools/master-data/sync-status/", want: config.GatewayRateLimitClassBackground},
		{method: "GET", path: "/pools/master-data/sync-launches/:id/", want: config.GatewayRateLimitClassBackground},
		{method: "GET", path: "/operations/stream/", want: config.GatewayRateLimitClassStreaming},
	}

	for _, tt := range tests {
		t.Run(tt.method+" "+tt.path, func(t *testing.T) {
			got := resolveOrchestratorRouteBudgetClass(tt.method, tt.path, config.GatewayRateLimitClassInteractive)
			if got != tt.want {
				t.Fatalf("expected class %q for %s %s, got %q", tt.want, tt.method, tt.path, got)
			}
		})
	}
}

func TestResolveOrchestratorRouteBudgetClass_UsesBoundedDefaultForUnknownRoutes(t *testing.T) {
	got := resolveOrchestratorRouteBudgetClass("GET", "/new-route/", config.GatewayRateLimitClassBackground)
	if got != config.GatewayRateLimitClassBackground {
		t.Fatalf("expected bounded default class background_heavy, got %q", got)
	}
}

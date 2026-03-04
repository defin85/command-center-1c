package config

import (
	"testing"
	"time"
)

func TestLoadFromEnv_EnablePoolOpsRoute_DefaultFalse(t *testing.T) {
	t.Setenv("ENABLE_POOLOPS_ROUTE", "")

	cfg := LoadFromEnv()
	if cfg.EnablePoolOpsRoute {
		t.Fatalf("expected EnablePoolOpsRoute=false by default")
	}
}

func TestLoadFromEnv_WorkerFairnessDefaults(t *testing.T) {
	t.Setenv("WORKER_FAIRNESS_OLDEST_AGE_THRESHOLD", "")
	t.Setenv("WORKER_FAIRNESS_MANUAL_RESERVE_SLOTS", "")
	t.Setenv("WORKER_FAIRNESS_TENANT_BUDGET_SHARE", "")
	t.Setenv("WORKER_FAIRNESS_TENANT_BUDGET_BACKOFF", "")

	cfg := LoadFromEnv()
	if cfg.WorkerFairnessOldestAgeThreshold != 120*time.Second {
		t.Fatalf(
			"expected WorkerFairnessOldestAgeThreshold=120s by default, got %v",
			cfg.WorkerFairnessOldestAgeThreshold,
		)
	}
	if cfg.WorkerFairnessManualReserveSlots != 1 {
		t.Fatalf(
			"expected WorkerFairnessManualReserveSlots=1 by default, got %d",
			cfg.WorkerFairnessManualReserveSlots,
		)
	}
	if cfg.WorkerFairnessTenantBudgetShare != 0.5 {
		t.Fatalf(
			"expected WorkerFairnessTenantBudgetShare=0.5 by default, got %v",
			cfg.WorkerFairnessTenantBudgetShare,
		)
	}
	if cfg.WorkerFairnessTenantBudgetBackoff != 25*time.Millisecond {
		t.Fatalf(
			"expected WorkerFairnessTenantBudgetBackoff=25ms by default, got %v",
			cfg.WorkerFairnessTenantBudgetBackoff,
		)
	}
}

func TestLoadFromEnv_WorkerFairnessOverrides(t *testing.T) {
	t.Setenv("WORKER_FAIRNESS_OLDEST_AGE_THRESHOLD", "45s")
	t.Setenv("WORKER_FAIRNESS_MANUAL_RESERVE_SLOTS", "3")
	t.Setenv("WORKER_FAIRNESS_TENANT_BUDGET_SHARE", "0.3")
	t.Setenv("WORKER_FAIRNESS_TENANT_BUDGET_BACKOFF", "90ms")

	cfg := LoadFromEnv()
	if cfg.WorkerFairnessOldestAgeThreshold != 45*time.Second {
		t.Fatalf(
			"expected WorkerFairnessOldestAgeThreshold=45s, got %v",
			cfg.WorkerFairnessOldestAgeThreshold,
		)
	}
	if cfg.WorkerFairnessManualReserveSlots != 3 {
		t.Fatalf(
			"expected WorkerFairnessManualReserveSlots=3, got %d",
			cfg.WorkerFairnessManualReserveSlots,
		)
	}
	if cfg.WorkerFairnessTenantBudgetShare != 0.3 {
		t.Fatalf(
			"expected WorkerFairnessTenantBudgetShare=0.3, got %v",
			cfg.WorkerFairnessTenantBudgetShare,
		)
	}
	if cfg.WorkerFairnessTenantBudgetBackoff != 90*time.Millisecond {
		t.Fatalf(
			"expected WorkerFairnessTenantBudgetBackoff=90ms, got %v",
			cfg.WorkerFairnessTenantBudgetBackoff,
		)
	}
}

func TestLoadFromEnv_EnablePoolOpsRoute_True(t *testing.T) {
	t.Setenv("ENABLE_POOLOPS_ROUTE", "true")

	cfg := LoadFromEnv()
	if !cfg.EnablePoolOpsRoute {
		t.Fatalf("expected EnablePoolOpsRoute=true when ENABLE_POOLOPS_ROUTE=true")
	}
}

func TestLoadFromEnv_PoolOpsRouteRollout_Defaults(t *testing.T) {
	t.Setenv("POOLOPS_ROUTE_ROLLOUT_PERCENT", "")
	t.Setenv("POOLOPS_ROUTE_ROLLOUT_SEED", "")
	t.Setenv("POOLOPS_ROUTE_KILL_SWITCH", "")

	cfg := LoadFromEnv()
	if cfg.PoolOpsRouteRolloutPercent != 1.0 {
		t.Fatalf("expected PoolOpsRouteRolloutPercent=1.0 by default, got %v", cfg.PoolOpsRouteRolloutPercent)
	}
	if cfg.PoolOpsRouteRolloutSeed != "" {
		t.Fatalf("expected empty PoolOpsRouteRolloutSeed by default, got %q", cfg.PoolOpsRouteRolloutSeed)
	}
	if cfg.PoolOpsRouteKillSwitch {
		t.Fatalf("expected PoolOpsRouteKillSwitch=false by default")
	}
}

func TestLoadFromEnv_PoolOpsRouteRolloutPercent_Normalized(t *testing.T) {
	tests := []struct {
		name      string
		envValue  string
		wantValue float64
	}{
		{name: "below_zero", envValue: "-1", wantValue: 0.0},
		{name: "above_one", envValue: "1.5", wantValue: 1.0},
		{name: "valid_half", envValue: "0.5", wantValue: 0.5},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Setenv("POOLOPS_ROUTE_ROLLOUT_PERCENT", tt.envValue)
			cfg := LoadFromEnv()
			if cfg.PoolOpsRouteRolloutPercent != tt.wantValue {
				t.Fatalf(
					"expected PoolOpsRouteRolloutPercent=%v for env %q, got %v",
					tt.wantValue,
					tt.envValue,
					cfg.PoolOpsRouteRolloutPercent,
				)
			}
		})
	}
}

func TestConfig_IsPoolOpsRouteEnabledForWorker_DisabledByFlag(t *testing.T) {
	cfg := &Config{
		EnablePoolOpsRoute:         false,
		PoolOpsRouteRolloutPercent: 1.0,
		WorkerID:                   "worker-a",
	}

	if cfg.IsPoolOpsRouteEnabledForWorker() {
		t.Fatalf("expected route disabled when feature flag is false")
	}
}

func TestConfig_IsPoolOpsRouteEnabledForWorker_RolloutBounds(t *testing.T) {
	cfg := &Config{
		EnablePoolOpsRoute:         true,
		PoolOpsRouteRolloutPercent: 0.0,
		WorkerID:                   "worker-a",
	}
	if cfg.IsPoolOpsRouteEnabledForWorker() {
		t.Fatalf("expected route disabled for rollout 0.0")
	}

	cfg.PoolOpsRouteRolloutPercent = 1.0
	if !cfg.IsPoolOpsRouteEnabledForWorker() {
		t.Fatalf("expected route enabled for rollout 1.0")
	}
}

func TestConfig_IsPoolOpsRouteEnabledForWorker_DeterministicCohort(t *testing.T) {
	cfg := &Config{
		EnablePoolOpsRoute:         true,
		PoolOpsRouteRolloutPercent: 0.5,
		PoolOpsRouteRolloutSeed:    "exp-poolops-canary",
		WorkerID:                   "worker-a",
	}

	first := cfg.IsPoolOpsRouteEnabledForWorker()
	for i := 0; i < 20; i++ {
		if cfg.IsPoolOpsRouteEnabledForWorker() != first {
			t.Fatalf("expected deterministic canary decision for worker cohort")
		}
	}
}

func TestLoadFromEnv_PoolOpsRouteKillSwitch_True(t *testing.T) {
	t.Setenv("POOLOPS_ROUTE_KILL_SWITCH", "true")

	cfg := LoadFromEnv()
	if !cfg.PoolOpsRouteKillSwitch {
		t.Fatalf("expected PoolOpsRouteKillSwitch=true when POOLOPS_ROUTE_KILL_SWITCH=true")
	}
}

func TestConfig_IsPoolOpsRouteEnabledForWorker_KillSwitchOverridesCanary(t *testing.T) {
	cfg := &Config{
		EnablePoolOpsRoute:         true,
		PoolOpsRouteRolloutPercent: 1.0,
		PoolOpsRouteKillSwitch:     true,
		WorkerID:                   "worker-a",
	}

	if cfg.IsPoolOpsRouteEnabledForWorker() {
		t.Fatalf("expected route disabled when kill-switch is enabled")
	}
}

func TestConfig_PoolOpsRoutingControls_IndependentFromProjectionHardeningCutoff(t *testing.T) {
	t.Setenv("ENABLE_POOLOPS_ROUTE", "true")
	t.Setenv("POOLOPS_ROUTE_ROLLOUT_PERCENT", "1.0")
	t.Setenv("POOLOPS_ROUTE_KILL_SWITCH", "false")
	// Projection hardening cutoff is an Orchestrator runtime setting and must not affect worker route decision.
	t.Setenv("POOLS_PROJECTION_PUBLICATION_HARDENING_CUTOFF_UTC", "2030-01-01T00:00:00Z")

	cfg := LoadFromEnv()
	if !cfg.IsPoolOpsRouteEnabledForWorker() {
		t.Fatalf("expected poolops route enabled independently of projection hardening cutoff")
	}
}

func TestLoadFromEnv_EnablePoolPublicationODataCore_DefaultFalse(t *testing.T) {
	t.Setenv("ENABLE_POOL_PUBLICATION_ODATA_CORE", "")

	cfg := LoadFromEnv()
	if cfg.EnablePoolPublicationODataCore {
		t.Fatalf("expected EnablePoolPublicationODataCore=false by default")
	}
}

func TestConfig_IsPoolPublicationODataCoreEnabledForWorker_RolloutAndKillSwitch(t *testing.T) {
	cfg := &Config{
		EnablePoolPublicationODataCore:         true,
		PoolPublicationODataCoreRolloutPercent: 1.0,
		WorkerID:                               "worker-a",
	}

	if !cfg.IsPoolPublicationODataCoreEnabledForWorker() {
		t.Fatalf("expected publication transport enabled for rollout 1.0")
	}

	cfg.PoolPublicationODataCoreKillSwitch = true
	if cfg.IsPoolPublicationODataCoreEnabledForWorker() {
		t.Fatalf("expected publication transport disabled when kill-switch is enabled")
	}
}

package queue

import (
	"math"
	"strings"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	fairnessOldestTaskAgeSeconds = promauto.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "worker_oldest_task_age_seconds",
			Help: "Age in seconds of observed tasks participating in fairness scheduling.",
		},
		[]string{"server_affinity", "role"},
	)
	fairnessManualRemediationQuotaSaturation = promauto.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "worker_manual_remediation_quota_saturation",
			Help: "Manual remediation reserve slot saturation (1 saturated, 0 available).",
		},
		[]string{"server_affinity"},
	)
	fairnessTenantBudgetThrottleTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "worker_tenant_budget_throttle_total",
			Help: "Total tenant budget throttle events in fairness scheduling.",
		},
		[]string{"server_affinity"},
	)
)

func recordFairnessOldestTaskAgeMetric(profile fairnessProfile) {
	affinity := normalizeFairnessMetricLabel(profile.affinity, "shared")
	role := normalizeFairnessMetricLabel(profile.role, "default")
	ageSeconds := math.Max(profile.age.Seconds(), 0)
	fairnessOldestTaskAgeSeconds.WithLabelValues(affinity, role).Set(ageSeconds)
}

func setManualRemediationQuotaSaturationMetric(affinity string, saturated bool) {
	value := 0.0
	if saturated {
		value = 1.0
	}
	fairnessManualRemediationQuotaSaturation.WithLabelValues(
		normalizeFairnessMetricLabel(affinity, "shared"),
	).Set(value)
}

func recordTenantBudgetThrottleMetric(affinity string) {
	fairnessTenantBudgetThrottleTotal.WithLabelValues(
		normalizeFairnessMetricLabel(affinity, "shared"),
	).Inc()
}

func normalizeFairnessMetricLabel(value string, fallback string) string {
	label := strings.TrimSpace(strings.ToLower(value))
	if label == "" {
		return fallback
	}
	return label
}

package queue

import (
	"testing"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	dto "github.com/prometheus/client_model/go"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func readGaugeMetricValue(t *testing.T, metric prometheus.Metric) float64 {
	t.Helper()
	snapshot := &dto.Metric{}
	require.NoError(t, metric.Write(snapshot))
	require.NotNil(t, snapshot.Gauge)
	return snapshot.GetGauge().GetValue()
}

func readCounterMetricValue(t *testing.T, metric prometheus.Metric) float64 {
	t.Helper()
	snapshot := &dto.Metric{}
	require.NoError(t, metric.Write(snapshot))
	require.NotNil(t, snapshot.Counter)
	return snapshot.GetCounter().GetValue()
}

func TestRecordFairnessOldestTaskAgeMetric_NormalizesLabelsAndClampsAge(t *testing.T) {
	recordFairnessOldestTaskAgeMetric(
		fairnessProfile{
			affinity: " Srv-A ",
			role:     " Reconcile ",
			age:      -5 * time.Second,
		},
	)

	got := readGaugeMetricValue(
		t,
		fairnessOldestTaskAgeSeconds.WithLabelValues("srv-a", "reconcile"),
	)
	assert.Equal(t, 0.0, got)

	recordFairnessOldestTaskAgeMetric(
		fairnessProfile{
			affinity: "srv-a",
			role:     "reconcile",
			age:      42 * time.Second,
		},
	)
	got = readGaugeMetricValue(
		t,
		fairnessOldestTaskAgeSeconds.WithLabelValues("srv-a", "reconcile"),
	)
	assert.Equal(t, 42.0, got)
}

func TestSetManualRemediationQuotaSaturationMetric_TracksState(t *testing.T) {
	setManualRemediationQuotaSaturationMetric(" Srv-B ", true)
	saturatedValue := readGaugeMetricValue(
		t,
		fairnessManualRemediationQuotaSaturation.WithLabelValues("srv-b"),
	)
	assert.Equal(t, 1.0, saturatedValue)

	setManualRemediationQuotaSaturationMetric("Srv-B", false)
	recoveredValue := readGaugeMetricValue(
		t,
		fairnessManualRemediationQuotaSaturation.WithLabelValues("srv-b"),
	)
	assert.Equal(t, 0.0, recoveredValue)
}

func TestRecordTenantBudgetThrottleMetric_IncrementsCounter(t *testing.T) {
	metric := fairnessTenantBudgetThrottleTotal.WithLabelValues("srv-c")
	before := readCounterMetricValue(t, metric)
	recordTenantBudgetThrottleMetric("Srv-C")
	after := readCounterMetricValue(t, metric)
	assert.Equal(t, before+1, after)
}

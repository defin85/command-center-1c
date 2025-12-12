package metrics

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

const (
	Namespace = "cc1c"
	Subsystem = "designer"
)

// DesignerMetrics contains all Prometheus metrics for Designer Agent
type DesignerMetrics struct {
	// HTTP metrics
	RequestsTotal   *prometheus.CounterVec
	RequestDuration *prometheus.HistogramVec

	// Designer commands
	CommandsTotal   *prometheus.CounterVec   // {command_type, status}
	CommandDuration *prometheus.HistogramVec // {command_type}
	// command_type: extension_install, extension_remove, config_dump, config_load, config_update, epf_export

	// SSH Pool
	SSHConnectionsActive prometheus.Gauge
	SSHConnectionsIdle   prometheus.Gauge
	SSHConnectionErrors  *prometheus.CounterVec   // {error_type}
	SSHCommandDuration   *prometheus.HistogramVec // {command_type} - limited cardinality
}

// NewDesignerMetrics creates and registers all Designer Agent metrics
func NewDesignerMetrics() *DesignerMetrics {
	return &DesignerMetrics{
		RequestsTotal: promauto.NewCounterVec(
			prometheus.CounterOpts{
				Namespace: Namespace,
				Subsystem: Subsystem,
				Name:      "requests_total",
				Help:      "Total HTTP requests to Designer Agent",
			},
			[]string{"method", "path", "status"},
		),
		RequestDuration: promauto.NewHistogramVec(
			prometheus.HistogramOpts{
				Namespace: Namespace,
				Subsystem: Subsystem,
				Name:      "request_duration_seconds",
				Help:      "HTTP request duration in seconds",
				Buckets:   prometheus.DefBuckets,
			},
			[]string{"method", "path"},
		),
		CommandsTotal: promauto.NewCounterVec(
			prometheus.CounterOpts{
				Namespace: Namespace,
				Subsystem: Subsystem,
				Name:      "commands_total",
				Help:      "Total designer commands executed",
			},
			[]string{"command_type", "status"},
		),
		CommandDuration: promauto.NewHistogramVec(
			prometheus.HistogramOpts{
				Namespace: Namespace,
				Subsystem: Subsystem,
				Name:      "command_duration_seconds",
				Help:      "Designer command execution duration",
				// Extended buckets for heavy 1C operations (up to 10 minutes)
				Buckets: []float64{1, 5, 10, 30, 60, 120, 300, 600},
			},
			[]string{"command_type"},
		),
		SSHConnectionsActive: promauto.NewGauge(
			prometheus.GaugeOpts{
				Namespace: Namespace,
				Subsystem: Subsystem,
				Name:      "ssh_connections_active",
				Help:      "Number of active SSH connections",
			},
		),
		SSHConnectionsIdle: promauto.NewGauge(
			prometheus.GaugeOpts{
				Namespace: Namespace,
				Subsystem: Subsystem,
				Name:      "ssh_connections_idle",
				Help:      "Number of idle SSH connections in pool",
			},
		),
		SSHConnectionErrors: promauto.NewCounterVec(
			prometheus.CounterOpts{
				Namespace: Namespace,
				Subsystem: Subsystem,
				Name:      "ssh_connection_errors_total",
				Help:      "Total SSH connection errors",
			},
			[]string{"error_type"}, // timeout, auth_failed, network_error
		),
		SSHCommandDuration: promauto.NewHistogramVec(
			prometheus.HistogramOpts{
				Namespace: Namespace,
				Subsystem: Subsystem,
				Name:      "ssh_command_duration_seconds",
				Help:      "SSH command execution duration by command type",
				Buckets:   []float64{0.1, 0.5, 1, 5, 10, 30, 60, 120},
			},
			[]string{"command_type"}, // Limited cardinality: extension_install, extension_remove, config_update, config_load, config_dump
		),
	}
}

// RecordCommand records a designer command execution
func (m *DesignerMetrics) RecordCommand(commandType, status string, duration float64) {
	m.CommandsTotal.WithLabelValues(commandType, status).Inc()
	m.CommandDuration.WithLabelValues(commandType).Observe(duration)
}

// RecordSSHError records an SSH connection error
func (m *DesignerMetrics) RecordSSHError(errorType string) {
	m.SSHConnectionErrors.WithLabelValues(errorType).Inc()
}

// RecordSSHCommand records SSH command duration by command type
// commandType should be one of: extension_install, extension_remove, config_update, config_load, config_dump
func (m *DesignerMetrics) RecordSSHCommand(commandType string, duration float64) {
	m.SSHCommandDuration.WithLabelValues(commandType).Observe(duration)
}

// SetSSHConnections sets the current SSH connection counts
func (m *DesignerMetrics) SetSSHConnections(active, idle float64) {
	m.SSHConnectionsActive.Set(active)
	m.SSHConnectionsIdle.Set(idle)
}

// IncrementActiveSSHConnections increments active SSH connection count
func (m *DesignerMetrics) IncrementActiveSSHConnections() {
	m.SSHConnectionsActive.Inc()
}

// DecrementActiveSSHConnections decrements active SSH connection count
func (m *DesignerMetrics) DecrementActiveSSHConnections() {
	m.SSHConnectionsActive.Dec()
}

// Command types for designer operations (limited cardinality)
const (
	CmdExtensionInstall = "extension_install"
	CmdExtensionRemove  = "extension_remove"
	CmdConfigUpdate     = "config_update"
	CmdConfigLoad       = "config_load"
	CmdConfigDump       = "config_dump"
	CmdEpfExport        = "epf_export"
)

// Status values for operations
const (
	StatusSuccess = "success"
	StatusError   = "error"
)

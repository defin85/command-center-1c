package config

import "time"

type GatewayRateLimitClass string

const (
	GatewayRateLimitClassShellCritical GatewayRateLimitClass = "shell_critical"
	GatewayRateLimitClassInteractive   GatewayRateLimitClass = "interactive"
	GatewayRateLimitClassBackground    GatewayRateLimitClass = "background_heavy"
	GatewayRateLimitClassTelemetry     GatewayRateLimitClass = "telemetry"
	GatewayRateLimitClassStreaming     GatewayRateLimitClass = "streaming"
)

type GatewayRateLimitBudget struct {
	Requests int
	Window   time.Duration
}

type GatewayRateLimitConfig struct {
	DefaultClass    GatewayRateLimitClass
	ShellCritical   GatewayRateLimitBudget
	Interactive     GatewayRateLimitBudget
	BackgroundHeavy GatewayRateLimitBudget
	Telemetry       GatewayRateLimitBudget
}

func loadGatewayRateLimitConfig() GatewayRateLimitConfig {
	defaultClass := NormalizeGatewayRateLimitClass(
		getEnv("API_GATEWAY_RATE_LIMIT_DEFAULT_CLASS", string(GatewayRateLimitClassInteractive)),
		GatewayRateLimitClassInteractive,
	)

	return GatewayRateLimitConfig{
		DefaultClass: defaultClass,
		ShellCritical: GatewayRateLimitBudget{
			Requests: getPositiveIntEnv("API_GATEWAY_RATE_LIMIT_SHELL_CRITICAL_REQUESTS", 60),
			Window:   getPositiveDurationEnv("API_GATEWAY_RATE_LIMIT_SHELL_CRITICAL_WINDOW", time.Minute),
		},
		Interactive: GatewayRateLimitBudget{
			Requests: getPositiveIntEnv("API_GATEWAY_RATE_LIMIT_INTERACTIVE_REQUESTS", 100),
			Window:   getPositiveDurationEnv("API_GATEWAY_RATE_LIMIT_INTERACTIVE_WINDOW", time.Minute),
		},
		BackgroundHeavy: GatewayRateLimitBudget{
			Requests: getPositiveIntEnv("API_GATEWAY_RATE_LIMIT_BACKGROUND_HEAVY_REQUESTS", 50),
			Window:   getPositiveDurationEnv("API_GATEWAY_RATE_LIMIT_BACKGROUND_HEAVY_WINDOW", time.Minute),
		},
		Telemetry: GatewayRateLimitBudget{
			Requests: getPositiveIntEnv("API_GATEWAY_RATE_LIMIT_TELEMETRY_REQUESTS", 20),
			Window:   getPositiveDurationEnv("API_GATEWAY_RATE_LIMIT_TELEMETRY_WINDOW", time.Minute),
		},
	}
}

func NormalizeGatewayRateLimitClass(raw string, fallback GatewayRateLimitClass) GatewayRateLimitClass {
	switch GatewayRateLimitClass(raw) {
	case GatewayRateLimitClassShellCritical,
		GatewayRateLimitClassInteractive,
		GatewayRateLimitClassBackground,
		GatewayRateLimitClassTelemetry:
		return GatewayRateLimitClass(raw)
	default:
		return fallback
	}
}

func (cfg GatewayRateLimitConfig) BudgetForClass(class GatewayRateLimitClass) GatewayRateLimitBudget {
	switch class {
	case GatewayRateLimitClassShellCritical:
		return normalizeGatewayRateLimitBudget(cfg.ShellCritical)
	case GatewayRateLimitClassBackground:
		return normalizeGatewayRateLimitBudget(cfg.BackgroundHeavy)
	case GatewayRateLimitClassTelemetry:
		return normalizeGatewayRateLimitBudget(cfg.Telemetry)
	case GatewayRateLimitClassStreaming:
		return GatewayRateLimitBudget{}
	default:
		return normalizeGatewayRateLimitBudget(cfg.Interactive)
	}
}

func normalizeGatewayRateLimitBudget(budget GatewayRateLimitBudget) GatewayRateLimitBudget {
	if budget.Requests <= 0 {
		budget.Requests = 1
	}
	if budget.Window <= 0 {
		budget.Window = time.Minute
	}
	return budget
}

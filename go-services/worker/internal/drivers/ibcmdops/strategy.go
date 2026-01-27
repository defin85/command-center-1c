package ibcmdops

import (
	"fmt"
	"strings"
)

func extractIbcmdIbAuthStrategy(data map[string]interface{}) string {
	if data == nil {
		return "actor"
	}
	raw, ok := data["ib_auth"]
	if !ok || raw == nil {
		return "actor"
	}
	ibAuth, ok := raw.(map[string]interface{})
	if !ok || ibAuth == nil {
		return "actor"
	}
	strategyRaw, ok := ibAuth["strategy"]
	if !ok || strategyRaw == nil {
		return "actor"
	}
	strategy := strings.ToLower(strings.TrimSpace(fmt.Sprintf("%v", strategyRaw)))
	switch strategy {
	case "actor", "service", "none":
		return strategy
	default:
		return "actor"
	}
}

func extractIbcmdDbmsAuthStrategy(data map[string]interface{}) string {
	if data == nil {
		return "actor"
	}
	raw, ok := data["dbms_auth"]
	if !ok || raw == nil {
		return "actor"
	}
	dbmsAuth, ok := raw.(map[string]interface{})
	if !ok || dbmsAuth == nil {
		return "actor"
	}
	strategyRaw, ok := dbmsAuth["strategy"]
	if !ok || strategyRaw == nil {
		return "actor"
	}
	strategy := strings.ToLower(strings.TrimSpace(fmt.Sprintf("%v", strategyRaw)))
	switch strategy {
	case "actor", "service":
		return strategy
	default:
		return "actor"
	}
}

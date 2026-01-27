package ibcmdops

import (
	"fmt"
	"strconv"
	"strings"
)

func extractString(data map[string]interface{}, key string) string {
	if data == nil {
		return ""
	}
	value, ok := data[key]
	if !ok || value == nil {
		return ""
	}
	switch v := value.(type) {
	case string:
		return v
	case fmt.Stringer:
		return v.String()
	default:
		return fmt.Sprintf("%v", v)
	}
}

func extractBool(data map[string]interface{}, key string) bool {
	if data == nil {
		return false
	}
	value, ok := data[key]
	if !ok || value == nil {
		return false
	}
	switch v := value.(type) {
	case bool:
		return v
	case string:
		parsed, _ := strconv.ParseBool(v)
		return parsed
	case int:
		return v != 0
	case int64:
		return v != 0
	case float64:
		return v != 0
	default:
		return false
	}
}

func extractInt(data map[string]interface{}, key string) int {
	if data == nil {
		return 0
	}
	value, ok := data[key]
	if !ok || value == nil {
		return 0
	}
	switch v := value.(type) {
	case int:
		return v
	case int64:
		return int(v)
	case float64:
		return int(v)
	case string:
		parsed, _ := strconv.Atoi(v)
		return parsed
	default:
		return 0
	}
}

func extractStringSlice(data map[string]interface{}, key string) []string {
	if data == nil {
		return nil
	}
	value, ok := data[key]
	if !ok || value == nil {
		return nil
	}
	switch v := value.(type) {
	case []string:
		return append([]string(nil), v...)
	case []interface{}:
		result := make([]string, 0, len(v))
		for _, item := range v {
			result = append(result, fmt.Sprintf("%v", item))
		}
		return result
	default:
		return nil
	}
}

func extractYesNoOption(data map[string]interface{}, key string) (string, bool, error) {
	if data == nil {
		return "", false, nil
	}
	raw, ok := data[key]
	if !ok || raw == nil {
		return "", false, nil
	}

	switch value := raw.(type) {
	case bool:
		if value {
			return "yes", true, nil
		}
		return "no", true, nil
	case string:
		v := strings.TrimSpace(strings.ToLower(value))
		if v == "" {
			return "", false, nil
		}
		switch v {
		case "yes", "true", "1":
			return "yes", true, nil
		case "no", "false", "0":
			return "no", true, nil
		default:
			return "", false, fmt.Errorf("invalid %s: %q (expected yes/no)", key, value)
		}
	case int:
		if value != 0 {
			return "yes", true, nil
		}
		return "no", true, nil
	case int64:
		if value != 0 {
			return "yes", true, nil
		}
		return "no", true, nil
	case float64:
		if value != 0 {
			return "yes", true, nil
		}
		return "no", true, nil
	default:
		return "", false, fmt.Errorf("invalid %s type: %T", key, raw)
	}
}

func extractEnumOption(data map[string]interface{}, key string, allowed []string) (string, bool, error) {
	raw := strings.TrimSpace(extractString(data, key))
	if raw == "" {
		return "", false, nil
	}
	for _, a := range allowed {
		if raw == a {
			return raw, true, nil
		}
	}
	return "", false, fmt.Errorf("invalid %s: %q (allowed: %s)", key, raw, strings.Join(allowed, ", "))
}

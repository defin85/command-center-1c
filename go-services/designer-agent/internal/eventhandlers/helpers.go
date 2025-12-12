package eventhandlers

import (
	"context"
	"fmt"
	"regexp"
	"strconv"
	"strings"
	"time"

	"go.uber.org/zap"
)

const (
	// IdempotencyTTL is the TTL for idempotency keys in Redis.
	IdempotencyTTL = 30 * time.Minute

	// IdempotencyKeyPrefix is the prefix for idempotency keys.
	IdempotencyKeyPrefix = "idempotency:designer"
)

// CheckIdempotency checks if an operation has already been processed using Redis SetNX.
// Returns (isFirst, error) where isFirst=true means this is the first time processing.
func CheckIdempotency(ctx context.Context, redisClient RedisClient, correlationID, operation string, logger *zap.Logger) (bool, error) {
	// Skip idempotency check if no correlationID
	if correlationID == "" {
		logger.Warn("empty correlation ID, skipping idempotency check")
		return true, nil
	}

	// Skip if Redis client not configured
	if redisClient == nil {
		logger.Debug("Redis client not configured, skipping idempotency check",
			zap.String("correlation_id", correlationID))
		return true, nil
	}

	key := fmt.Sprintf("%s:%s:%s", IdempotencyKeyPrefix, operation, correlationID)

	result := redisClient.SetNX(ctx, key, "processed", IdempotencyTTL)
	if result.Err() != nil {
		logger.Warn("idempotency check failed (Redis error), allowing operation to proceed (fail-open)",
			zap.String("correlation_id", correlationID),
			zap.String("operation", operation),
			zap.Error(result.Err()))
		return true, nil // Fail-open: allow operation
	}

	isFirst, err := result.Result()
	if err != nil {
		logger.Warn("failed to get SetNX result, allowing operation (fail-open)",
			zap.String("correlation_id", correlationID),
			zap.Error(err))
		return true, nil
	}

	return isFirst, nil
}

// ContainsError checks if the output contains error indicators.
// Returns true if output indicates an error condition.
func ContainsError(output string) bool {
	if output == "" {
		return false
	}

	lowerOutput := strings.ToLower(output)

	// Common 1C error indicators
	errorIndicators := []string{
		"error",
		"ошибка",
		"failed",
		"failure",
		"не удалось",
		"невозможно",
		"exception",
		"критическая",
		"critical",
		"fatal",
		"result: failed",
	}

	for _, indicator := range errorIndicators {
		if strings.Contains(lowerOutput, indicator) {
			return true
		}
	}

	return false
}

// ExtractError extracts the error message from output.
// Attempts to find the most relevant error message.
func ExtractError(output string) string {
	if output == "" {
		return "unknown error"
	}

	lines := strings.Split(output, "\n")

	// Look for lines that contain error indicators
	errorPatterns := []string{
		"error:",
		"ошибка:",
		"failed:",
		"Error",
		"Ошибка",
	}

	for _, line := range lines {
		trimmedLine := strings.TrimSpace(line)
		if trimmedLine == "" {
			continue
		}

		for _, pattern := range errorPatterns {
			if strings.Contains(strings.ToLower(trimmedLine), strings.ToLower(pattern)) {
				return trimmedLine
			}
		}
	}

	// If no specific error line found, return last non-empty lines
	var lastLines []string
	for i := len(lines) - 1; i >= 0 && len(lastLines) < 3; i-- {
		trimmedLine := strings.TrimSpace(lines[i])
		if trimmedLine != "" {
			lastLines = append([]string{trimmedLine}, lastLines...)
		}
	}

	if len(lastLines) > 0 {
		return strings.Join(lastLines, "; ")
	}

	return "unknown error"
}

// ParseProgressPercent extracts progress percentage from output line.
// Returns -1 if no percentage found.
func ParseProgressPercent(line string) int {
	// Pattern 1: "50%", "100%"
	percentPattern := regexp.MustCompile(`(\d{1,3})%`)
	if matches := percentPattern.FindStringSubmatch(line); len(matches) > 1 {
		if percent, err := strconv.Atoi(matches[1]); err == nil && percent >= 0 && percent <= 100 {
			return percent
		}
	}

	// Pattern 2: "Progress: 50 of 100" -> calculate percentage
	progressPattern := regexp.MustCompile(`(\d+)\s+(?:of|из)\s+(\d+)`)
	if matches := progressPattern.FindStringSubmatch(line); len(matches) > 2 {
		current, err1 := strconv.Atoi(matches[1])
		total, err2 := strconv.Atoi(matches[2])
		if err1 == nil && err2 == nil && total > 0 {
			percent := (current * 100) / total
			if percent > 100 {
				percent = 100
			}
			return percent
		}
	}

	// Pattern 3: "[====      ] 40%" style progress bars
	barPattern := regexp.MustCompile(`\[=*\s*\]\s*(\d{1,3})%`)
	if matches := barPattern.FindStringSubmatch(line); len(matches) > 1 {
		if percent, err := strconv.Atoi(matches[1]); err == nil && percent >= 0 && percent <= 100 {
			return percent
		}
	}

	return -1
}

// ParsePhase extracts the current phase from output line.
// Returns empty string if no phase indicator found.
func ParsePhase(line string) string {
	lowerLine := strings.ToLower(line)

	// Common 1C phases
	phases := map[string]string{
		"загрузка конфигурации":      "loading_config",
		"loading configuration":      "loading_config",
		"выгрузка конфигурации":      "dumping_config",
		"dumping configuration":      "dumping_config",
		"обновление конфигурации":    "updating_config",
		"updating configuration":     "updating_config",
		"реструктуризация":           "restructuring",
		"restructuring":              "restructuring",
		"проверка":                   "checking",
		"checking":                   "checking",
		"компиляция":                 "compiling",
		"compiling":                  "compiling",
		"загрузка расширения":        "loading_extension",
		"loading extension":          "loading_extension",
		"удаление расширения":        "removing_extension",
		"removing extension":         "removing_extension",
		"формирование внешней":       "exporting_epf",
		"exporting external":         "exporting_epf",
		"выгрузка метаданных":        "exporting_metadata",
		"exporting metadata":         "exporting_metadata",
		"обновление базы данных":     "updating_database",
		"updating database":          "updating_database",
		"синхронизация":              "synchronizing",
		"synchronizing":              "synchronizing",
		"подготовка":                 "preparing",
		"preparing":                  "preparing",
		"завершение":                 "finalizing",
		"finalizing":                 "finalizing",
		"запуск":                     "starting",
		"starting":                   "starting",
		"инициализация":              "initializing",
		"initializing":               "initializing",
	}

	for indicator, phase := range phases {
		if strings.Contains(lowerLine, indicator) {
			return phase
		}
	}

	return ""
}

// IsSuccess checks if output indicates successful completion.
func IsSuccess(output string, exitCode int) bool {
	if exitCode != 0 {
		return false
	}

	lowerOutput := strings.ToLower(output)

	// Success indicators
	successIndicators := []string{
		"result: success",
		"operation completed successfully",
		"завершено успешно",
		"успешно выполнено",
		"completed successfully",
		"done",
	}

	for _, indicator := range successIndicators {
		if strings.Contains(lowerOutput, indicator) {
			return true
		}
	}

	// If no error and exit code 0, consider it success
	return !ContainsError(output)
}

// GetStringOption safely extracts a string option from the options map.
func GetStringOption(options map[string]interface{}, key, defaultValue string) string {
	if options == nil {
		return defaultValue
	}
	if val, ok := options[key].(string); ok && val != "" {
		return val
	}
	return defaultValue
}

// GetIntOption safely extracts an int option from the options map.
func GetIntOption(options map[string]interface{}, key string, defaultValue int) int {
	if options == nil {
		return defaultValue
	}

	// Try int
	if val, ok := options[key].(int); ok {
		return val
	}

	// Try float64 (JSON unmarshaling uses float64 for numbers)
	if val, ok := options[key].(float64); ok {
		return int(val)
	}

	return defaultValue
}

// GetBoolOption safely extracts a bool option from the options map.
func GetBoolOption(options map[string]interface{}, key string, defaultValue bool) bool {
	if options == nil {
		return defaultValue
	}
	if val, ok := options[key].(bool); ok {
		return val
	}
	return defaultValue
}

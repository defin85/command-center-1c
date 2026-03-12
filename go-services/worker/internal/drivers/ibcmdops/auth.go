package ibcmdops

import (
	"fmt"
	"strings"

	"github.com/commandcenter1c/commandcenter/shared/credentials"
)

func pickIBUsername(creds *credentials.DatabaseCredentials) string {
	if creds == nil {
		return ""
	}
	return strings.TrimSpace(creds.IBUsername)
}

func pickIBPassword(creds *credentials.DatabaseCredentials) string {
	if creds == nil {
		return ""
	}
	return strings.TrimSpace(creds.IBPassword)
}

func injectInfobaseAuthArgs(args []string, creds *credentials.DatabaseCredentials) []string {
	if len(args) == 0 {
		return args
	}

	cleaned := stripInfobaseAuthArgs(args)
	if creds == nil {
		return cleaned
	}

	username := strings.TrimSpace(creds.IBUsername)
	if username == "" {
		return cleaned
	}
	password := strings.TrimSpace(creds.IBPassword)

	cleaned = append(cleaned, fmt.Sprintf("--user=%s", username))
	cleaned = append(cleaned, fmt.Sprintf("--password=%s", password))
	return cleaned
}

func stripInfobaseAuthArgs(args []string) []string {
	if len(args) == 0 {
		return args
	}

	result := make([]string, 0, len(args))
	skipNext := false
	for _, raw := range args {
		token := strings.TrimSpace(raw)
		if token == "" {
			continue
		}
		if skipNext {
			skipNext = false
			continue
		}

		lowered := strings.ToLower(token)
		if strings.HasPrefix(lowered, "--user") || strings.HasPrefix(lowered, "--password") {
			if strings.Contains(token, "=") {
				continue
			}
			skipNext = true
			continue
		}
		result = append(result, token)
	}

	return result
}

func shouldInjectInfobaseAuthArgs(commandID string, argv []string) bool {
	_ = commandID
	return len(argv) > 0
}

func isServiceDbmsAuthAllowed(commandID string) bool {
	// Keep this intentionally tight; expand only with explicit approval.
	switch commandID {
	case "infobase.extension.list", "infobase.extension.info", "infobase.config.generation-id", "infobase.config.export.objects":
		return true
	default:
		return false
	}
}

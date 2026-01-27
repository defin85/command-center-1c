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
	cmd := strings.TrimSpace(commandID)
	if cmd == "infobase.dump" || cmd == "infobase.restore" || cmd == "infobase.extension.list" || cmd == "infobase.extension.info" {
		return true
	}
	if len(argv) >= 2 && strings.TrimSpace(argv[0]) == "infobase" {
		sub := strings.TrimSpace(argv[1])
		if sub == "dump" || sub == "restore" {
			return true
		}
		// Some catalog command IDs flatten "infobase config extension <cmd>" into "infobase extension <cmd>".
		// By this point argv may already include "config" (normalizeIbcmdArgv), but we keep this robust.
		if sub == "extension" {
			if len(argv) >= 3 {
				action := strings.TrimSpace(argv[2])
				return action == "list" || action == "info"
			}
			return false
		}
		if sub == "config" && len(argv) >= 4 && strings.TrimSpace(argv[2]) == "extension" {
			action := strings.TrimSpace(argv[3])
			return action == "list" || action == "info"
		}
	}
	return false
}

func isServiceDbmsAuthAllowed(commandID string) bool {
	// Keep this intentionally tight; expand only with explicit approval.
	return commandID == "infobase.extension.list" || commandID == "infobase.extension.info"
}

func isServiceIbAuthAllowed(commandID string) bool {
	switch strings.TrimSpace(commandID) {
	case "infobase.extension.list", "infobase.extension.info":
		return true
	default:
		return false
	}
}

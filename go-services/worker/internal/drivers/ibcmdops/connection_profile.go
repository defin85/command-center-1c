package ibcmdops

import (
	"fmt"
	"sort"
	"strings"

	"github.com/commandcenter1c/commandcenter/shared/credentials"
	runnerartifacts "github.com/commandcenter1c/commandcenter/worker/internal/commandrunner/artifacts"
)

func isCommandToken(token string) bool {
	tok := strings.TrimSpace(token)
	if tok == "" {
		return false
	}
	if strings.HasPrefix(tok, "-") {
		return false
	}
	if strings.HasPrefix(tok, runnerartifacts.ArtifactPrefix) || strings.HasPrefix(tok, "s3://") {
		return false
	}
	if strings.ContainsAny(tok, "/\\.:") {
		return false
	}
	for _, ch := range tok {
		if (ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') || (ch >= '0' && ch <= '9') || ch == '-' || ch == '_' {
			continue
		}
		return false
	}
	return true
}

func connectionInsertAt(args []string) int {
	if len(args) == 0 {
		return 0
	}
	for idx := 0; idx < len(args); idx++ {
		if strings.HasPrefix(strings.TrimSpace(args[idx]), "-") {
			return idx
		}
	}
	end := 0
	for end < len(args) && isCommandToken(args[end]) {
		end++
	}
	return end
}

func injectConnectionProfileArgs(args []string, creds *credentials.DatabaseCredentials) ([]string, []map[string]interface{}, error) {
	if len(args) == 0 {
		return args, nil, nil
	}
	// If connection flags are already present, keep argv as-is.
	if hasAnyFlag(
		args,
		"--remote",
		"--pid",
		"--config",
		"--data",
		"--db-path",
		"--dbms",
		"--db-server",
		"--db-name",
	) {
		return args, []map[string]interface{}{
			{
				"target_ref": "ibcmd_connection_profile",
				"source_ref": "database.ibcmd_connection_profile",
				"resolve_at": "worker",
				"sensitive":  false,
				"status":     "skipped",
				"reason":     "already_specified",
			},
		}, nil
	}
	if creds == nil || creds.IbcmdConnection == nil {
		return args, nil, fmt.Errorf("ibcmd_connection profile is required for derived connection")
	}

	profile := creds.IbcmdConnection
	remote := strings.TrimSpace(profile.Remote)
	pid := profile.PID
	offline := profile.Offline

	hasRemote := remote != ""
	hasPid := pid != nil && *pid > 0
	hasOffline := false
	if len(offline) > 0 {
		for _, v := range offline {
			if strings.TrimSpace(v) != "" {
				hasOffline = true
				break
			}
		}
	}
	if !hasRemote && !hasPid && !hasOffline {
		return args, nil, fmt.Errorf("ibcmd_connection profile is empty for derived connection")
	}

	isSafeOfflineKey := func(key string) bool {
		k := strings.TrimSpace(key)
		if k == "" {
			return false
		}
		if strings.HasPrefix(k, "-") {
			return false
		}
		for _, ch := range k {
			if (ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') || (ch >= '0' && ch <= '9') || ch == '_' || ch == '-' {
				continue
			}
			return false
		}
		return true
	}
	offlineFlagForKey := func(key string) string {
		k := strings.ToLower(strings.TrimSpace(key))
		k = strings.ReplaceAll(k, "_", "-")
		return "--" + k
	}

	insertAt := connectionInsertAt(args)
	out := append([]string(nil), args...)
	bindings := make([]map[string]interface{}, 0)

	injected := make([]string, 0)

	if hasRemote {
		token := fmt.Sprintf("--remote=%s", remote)
		injected = append(injected, token)
		bindings = append(bindings, map[string]interface{}{
			"target_ref": "flag:--remote",
			"source_ref": "database.ibcmd_connection_profile.remote",
			"resolve_at": "worker",
			"sensitive":  false,
			"status":     "applied",
		})
	}

	if hasPid {
		token := fmt.Sprintf("--pid=%d", *pid)
		injected = append(injected, token)
		bindings = append(bindings, map[string]interface{}{
			"target_ref": "flag:--pid",
			"source_ref": "database.ibcmd_connection_profile.pid",
			"resolve_at": "worker",
			"sensitive":  false,
			"status":     "applied",
		})
	}

	if len(offline) > 0 {
		keys := make([]string, 0, len(offline))
		for k := range offline {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		for _, key := range keys {
			lowered := strings.ToLower(strings.TrimSpace(key))
			if lowered == "db_user" || lowered == "db_pwd" || lowered == "db_password" {
				continue
			}
			if !isSafeOfflineKey(key) {
				continue
			}
			value := strings.TrimSpace(offline[key])
			if value == "" {
				continue
			}
			flag := offlineFlagForKey(key)
			token := fmt.Sprintf("%s=%s", flag, value)
			injected = append(injected, token)
			bindings = append(bindings, map[string]interface{}{
				"target_ref": fmt.Sprintf("flag:%s", flag),
				"source_ref": fmt.Sprintf("database.ibcmd_connection_profile.offline.%s", key),
				"resolve_at": "worker",
				"sensitive":  false,
				"status":     "applied",
			})
		}
	}

	if len(injected) > 0 {
		out = append(out[:insertAt], append(injected, out[insertAt:]...)...)
	}
	if len(bindings) == 0 {
		bindings = append(bindings, map[string]interface{}{
			"target_ref": "ibcmd_connection_profile",
			"source_ref": "database.ibcmd_connection_profile",
			"resolve_at": "worker",
			"sensitive":  false,
			"status":     "skipped",
			"reason":     "no_flags",
		})
	}
	return out, bindings, nil
}

package ibcmdops

import (
	"fmt"
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
	if hasAnyFlag(args, "--remote", "--pid", "--config", "--data") {
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
	mode := strings.ToLower(strings.TrimSpace(profile.Mode))
	if mode == "" {
		mode = "auto"
	}
	if mode != "auto" && mode != "remote" && mode != "offline" {
		mode = "auto"
	}

	effective := mode
	if mode == "auto" {
		if strings.TrimSpace(profile.RemoteURL) != "" {
			effective = "remote"
		} else {
			effective = "offline"
		}
	}

	insertAt := connectionInsertAt(args)
	out := append([]string(nil), args...)
	bindings := make([]map[string]interface{}, 0)

	if effective == "remote" {
		remoteURL := strings.TrimSpace(profile.RemoteURL)
		if remoteURL == "" {
			return args, nil, fmt.Errorf("ibcmd_connection.mode=remote requires remote_url")
		}
		token := fmt.Sprintf("--remote=%s", remoteURL)
		out = append(out[:insertAt], append([]string{token}, out[insertAt:]...)...)
		bindings = append(bindings, map[string]interface{}{
			"target_ref": "flag:--remote",
			"source_ref": "database.ibcmd_connection_profile",
			"resolve_at": "worker",
			"sensitive":  false,
			"status":     "applied",
		})
		return out, bindings, nil
	}

	offline := profile.Offline
	if offline == nil {
		return args, nil, fmt.Errorf("ibcmd_connection.mode=offline requires offline profile")
	}
	config := strings.TrimSpace(offline.Config)
	data := strings.TrimSpace(offline.Data)
	if config == "" || data == "" {
		return args, nil, fmt.Errorf("offline profile requires config and data")
	}

	injected := make([]string, 0)
	injected = append(injected, fmt.Sprintf("--config=%s", config))
	injected = append(injected, fmt.Sprintf("--data=%s", data))
	bindings = append(bindings,
		map[string]interface{}{
			"target_ref": "flag:--config",
			"source_ref": "database.ibcmd_connection_profile",
			"resolve_at": "worker",
			"sensitive":  false,
			"status":     "applied",
		},
		map[string]interface{}{
			"target_ref": "flag:--data",
			"source_ref": "database.ibcmd_connection_profile",
			"resolve_at": "worker",
			"sensitive":  false,
			"status":     "applied",
		},
	)

	dbPath := strings.TrimSpace(offline.DBPath)
	if dbPath != "" {
		injected = append(injected, fmt.Sprintf("--db-path=%s", dbPath))
		bindings = append(bindings, map[string]interface{}{
			"target_ref": "flag:--db-path",
			"source_ref": "database.ibcmd_connection_profile",
			"resolve_at": "worker",
			"sensitive":  false,
			"status":     "applied",
		})
	} else {
		// If profile provides DBMS triplet, it should override database metadata from credentials.
		if v := strings.TrimSpace(offline.DBMS); v != "" {
			injected = append(injected, fmt.Sprintf("--dbms=%s", v))
			bindings = append(bindings, map[string]interface{}{
				"target_ref": "flag:--dbms",
				"source_ref": "database.ibcmd_connection_profile",
				"resolve_at": "worker",
				"sensitive":  false,
				"status":     "applied",
			})
		}
		if v := strings.TrimSpace(offline.DBServer); v != "" {
			injected = append(injected, fmt.Sprintf("--db-server=%s", v))
			bindings = append(bindings, map[string]interface{}{
				"target_ref": "flag:--db-server",
				"source_ref": "database.ibcmd_connection_profile",
				"resolve_at": "worker",
				"sensitive":  false,
				"status":     "applied",
			})
		}
		if v := strings.TrimSpace(offline.DBName); v != "" {
			injected = append(injected, fmt.Sprintf("--db-name=%s", v))
			bindings = append(bindings, map[string]interface{}{
				"target_ref": "flag:--db-name",
				"source_ref": "database.ibcmd_connection_profile",
				"resolve_at": "worker",
				"sensitive":  false,
				"status":     "applied",
			})
		}
	}

	if v := strings.TrimSpace(offline.Ftext2Data); v != "" {
		injected = append(injected, fmt.Sprintf("--ftext2-data=%s", v))
	}
	if v := strings.TrimSpace(offline.FtextData); v != "" {
		injected = append(injected, fmt.Sprintf("--ftext-data=%s", v))
	}
	if v := strings.TrimSpace(offline.Lock); v != "" {
		injected = append(injected, fmt.Sprintf("--lock=%s", v))
	}
	if v := strings.TrimSpace(offline.LogData); v != "" {
		injected = append(injected, fmt.Sprintf("--log-data=%s", v))
	}
	if v := strings.TrimSpace(offline.OpenidData); v != "" {
		injected = append(injected, fmt.Sprintf("--openid-data=%s", v))
	}
	if v := strings.TrimSpace(offline.SessionData); v != "" {
		injected = append(injected, fmt.Sprintf("--session-data=%s", v))
	}
	if v := strings.TrimSpace(offline.SttData); v != "" {
		injected = append(injected, fmt.Sprintf("--stt-data=%s", v))
	}
	if v := strings.TrimSpace(offline.System); v != "" {
		injected = append(injected, fmt.Sprintf("--system=%s", v))
	}
	if v := strings.TrimSpace(offline.Temp); v != "" {
		injected = append(injected, fmt.Sprintf("--temp=%s", v))
	}
	if v := strings.TrimSpace(offline.UsersData); v != "" {
		injected = append(injected, fmt.Sprintf("--users-data=%s", v))
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

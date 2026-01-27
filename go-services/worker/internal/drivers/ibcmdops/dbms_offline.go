package ibcmdops

import (
	"fmt"
	"strings"

	"github.com/commandcenter1c/commandcenter/shared/credentials"
	runnerartifacts "github.com/commandcenter1c/commandcenter/worker/internal/commandrunner/artifacts"
)

func hasAnyFlag(args []string, flags ...string) bool {
	for idx := 0; idx < len(args); idx++ {
		token := strings.TrimSpace(args[idx])
		if token == "" {
			continue
		}
		for _, flag := range flags {
			if token == flag || strings.HasPrefix(token, flag+"=") {
				return true
			}
		}
	}
	return false
}

func injectDbmsOfflineArgs(args []string, creds *credentials.DatabaseCredentials, sourceRef string) ([]string, []map[string]interface{}, error) {
	if len(args) == 0 {
		return args, nil, nil
	}
	// If remote/pid is specified, treat it as non-offline execution and do not inject DBMS args.
	if hasAnyFlag(args, "--remote", "--pid") {
		return args, []map[string]interface{}{
			{
				"target_ref": "dbms_offline",
				"source_ref": "credentials.db_metadata",
				"resolve_at": "worker",
				"sensitive":  true,
				"status":     "skipped",
				"reason":     "remote_or_pid",
			},
		}, nil
	}

	if creds == nil {
		return args, nil, fmt.Errorf("credentials are required for offline DBMS injection")
	}

	hasDBPath := hasAnyFlag(args, "--db-path", "--database-path")
	if hasDBPath {
		// File infobase: no DBMS credentials should be injected/required.
		return args, []map[string]interface{}{
			{
				"target_ref": "dbms_offline",
				"source_ref": "credentials.db_metadata",
				"resolve_at": "worker",
				"sensitive":  false,
				"status":     "skipped",
				"reason":     "file_db_path",
			},
		}, nil
	}

	needsDBMS := !hasAnyFlag(args, "--dbms", "--database-management-system")
	needsDBServer := !hasAnyFlag(args, "--db-server", "--database-server")
	needsDBName := !hasAnyFlag(args, "--db-name", "--database-name")
	needsDBUser := !hasAnyFlag(args, "--db-user", "--database-user")
	needsDBPwd := !hasAnyFlag(args, "--db-pwd", "--database-password")

	dbms := strings.TrimSpace(creds.DBMS)
	dbServer := strings.TrimSpace(creds.DBServer)
	dbName := strings.TrimSpace(creds.DBName)
	dbUser := strings.TrimSpace(creds.DBUser)
	dbPwd := strings.TrimSpace(creds.DBPassword)

	missing := make([]string, 0)
	if needsDBMS && dbms == "" {
		missing = append(missing, "dbms")
	}
	if needsDBServer && dbServer == "" {
		missing = append(missing, "db_server")
	}
	if needsDBName && dbName == "" {
		missing = append(missing, "db_name")
	}
	if needsDBUser && dbUser == "" {
		missing = append(missing, "db_user")
	}
	if needsDBPwd && dbPwd == "" {
		missing = append(missing, "db_password")
	}
	if len(missing) > 0 {
		return args, nil, fmt.Errorf("missing DBMS credentials/metadata for offline connection: %s", strings.Join(missing, ", "))
	}

	out := append([]string(nil), args...)
	bindings := make([]map[string]interface{}, 0)

	isCommandToken := func(token string) bool {
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

	// Prefer inserting before the first flag token, otherwise after the initial command tokens.
	insertAt := len(out)
	for idx := 0; idx < len(out); idx++ {
		if strings.HasPrefix(strings.TrimSpace(out[idx]), "-") {
			insertAt = idx
			break
		}
	}
	if insertAt == len(out) {
		end := 0
		for end < len(out) && isCommandToken(out[end]) {
			end++
		}
		insertAt = end
	}

	injected := make([]string, 0)
	if needsDBMS {
		injected = append(injected, fmt.Sprintf("--dbms=%s", dbms))
		bindings = append(bindings, map[string]interface{}{
			"target_ref": "flag:--dbms",
			"source_ref": "credentials.db_metadata",
			"resolve_at": "worker",
			"sensitive":  false,
			"status":     "applied",
		})
	}
	if needsDBServer {
		injected = append(injected, fmt.Sprintf("--db-server=%s", dbServer))
		bindings = append(bindings, map[string]interface{}{
			"target_ref": "flag:--db-server",
			"source_ref": "credentials.db_metadata",
			"resolve_at": "worker",
			"sensitive":  false,
			"status":     "applied",
		})
	}
	if needsDBName {
		injected = append(injected, fmt.Sprintf("--db-name=%s", dbName))
		bindings = append(bindings, map[string]interface{}{
			"target_ref": "flag:--db-name",
			"source_ref": "credentials.db_metadata",
			"resolve_at": "worker",
			"sensitive":  false,
			"status":     "applied",
		})
	}
	if needsDBUser {
		injected = append(injected, fmt.Sprintf("--db-user=%s", dbUser))
		bindings = append(bindings, map[string]interface{}{
			"target_ref": "flag:--db-user",
			"source_ref": sourceRef,
			"resolve_at": "worker",
			"sensitive":  false,
			"status":     "applied",
		})
	}
	if needsDBPwd {
		injected = append(injected, fmt.Sprintf("--db-pwd=%s", dbPwd))
		bindings = append(bindings, map[string]interface{}{
			"target_ref": "flag:--db-pwd",
			"source_ref": sourceRef,
			"resolve_at": "worker",
			"sensitive":  true,
			"status":     "applied",
		})
	}

	if len(injected) > 0 {
		out = append(out[:insertAt], append(injected, out[insertAt:]...)...)
	}

	return out, bindings, nil
}

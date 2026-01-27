package ibcmdops

import (
	"fmt"
	"strings"

	"github.com/commandcenter1c/commandcenter/shared/credentials"
)

type dbConfig struct {
	DBMS       string
	DBServer   string
	DBName     string
	DBUser     string
	DBPassword string
	User       string
	Password   string
}

type replicateTargetConfig struct {
	DBMS       string
	DBServer   string
	DBName     string
	DBUser     string
	DBPassword string
}

func buildDBArgs(cfg dbConfig) []string {
	args := []string{
		fmt.Sprintf("--dbms=%s", cfg.DBMS),
		fmt.Sprintf("--db-server=%s", cfg.DBServer),
		fmt.Sprintf("--db-name=%s", cfg.DBName),
		fmt.Sprintf("--db-user=%s", cfg.DBUser),
		fmt.Sprintf("--db-pwd=%s", cfg.DBPassword),
	}
	if cfg.User != "" {
		args = append(args, fmt.Sprintf("--user=%s", cfg.User))
	}
	if cfg.Password != "" {
		args = append(args, fmt.Sprintf("--password=%s", cfg.Password))
	}
	return args
}

func buildTargetArgs(cfg replicateTargetConfig) []string {
	return []string{
		fmt.Sprintf("--target-dbms=%s", cfg.DBMS),
		fmt.Sprintf("--target-database-server=%s", cfg.DBServer),
		fmt.Sprintf("--target-database-name=%s", cfg.DBName),
		fmt.Sprintf("--target-database-user=%s", cfg.DBUser),
		fmt.Sprintf("--target-database-password=%s", cfg.DBPassword),
	}
}

func extractDBConfig(data map[string]interface{}, creds *credentials.DatabaseCredentials) (dbConfig, error) {
	cfg := dbConfig{
		DBMS:       extractString(data, "dbms"),
		DBServer:   extractString(data, "db_server"),
		DBName:     extractString(data, "db_name"),
		DBUser:     extractString(data, "db_user"),
		DBPassword: extractString(data, "db_password"),
		User:       extractString(data, "user"),
		Password:   extractString(data, "password"),
	}

	if cfg.User == "" && creds != nil {
		cfg.User = pickIBUsername(creds)
	}
	if cfg.Password == "" && creds != nil {
		cfg.Password = pickIBPassword(creds)
	}

	missing := []string{}
	if cfg.DBMS == "" {
		missing = append(missing, "dbms")
	}
	if cfg.DBServer == "" {
		missing = append(missing, "db_server")
	}
	if cfg.DBName == "" {
		missing = append(missing, "db_name")
	}
	if cfg.DBUser == "" {
		missing = append(missing, "db_user")
	}
	if cfg.DBPassword == "" {
		missing = append(missing, "db_password")
	}
	if len(missing) > 0 {
		return dbConfig{}, fmt.Errorf("missing required fields: %s", strings.Join(missing, ", "))
	}

	return cfg, nil
}

func extractReplicateTargetConfig(data map[string]interface{}) (replicateTargetConfig, error) {
	cfg := replicateTargetConfig{
		DBMS:       extractString(data, "target_dbms"),
		DBServer:   extractString(data, "target_db_server"),
		DBName:     extractString(data, "target_db_name"),
		DBUser:     extractString(data, "target_db_user"),
		DBPassword: extractString(data, "target_db_password"),
	}

	missing := []string{}
	if cfg.DBMS == "" {
		missing = append(missing, "target_dbms")
	}
	if cfg.DBServer == "" {
		missing = append(missing, "target_db_server")
	}
	if cfg.DBName == "" {
		missing = append(missing, "target_db_name")
	}
	if cfg.DBUser == "" {
		missing = append(missing, "target_db_user")
	}
	if cfg.DBPassword == "" {
		missing = append(missing, "target_db_password")
	}
	if len(missing) > 0 {
		return replicateTargetConfig{}, fmt.Errorf("missing required fields: %s", strings.Join(missing, ", "))
	}

	return cfg, nil
}

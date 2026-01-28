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

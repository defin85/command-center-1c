package ibcmdops

import (
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/credentials"
	cliutil "github.com/commandcenter1c/commandcenter/worker/internal/drivers/cli"
	"github.com/commandcenter1c/commandcenter/worker/internal/drivers/ibsrv"
)

func validateIbsrvAllowed() error {
	if os.Getenv("IBSRV_ENABLED") != "true" {
		return fmt.Errorf("ibsrv disabled (IBSRV_ENABLED != true)")
	}

	env := strings.ToLower(os.Getenv("APP_ENV"))
	if env == "" {
		env = strings.ToLower(os.Getenv("ENVIRONMENT"))
	}
	if env == "production" || env == "prod" {
		return fmt.Errorf("ibsrv is not allowed in production")
	}
	return nil
}

func buildAgentConfig(data map[string]interface{}, creds *credentials.DatabaseCredentials) (ibsrv.AgentConfig, error) {
	exePath, err := cliutil.Resolve1cv8PathFromEnv()
	if err != nil {
		return ibsrv.AgentConfig{}, err
	}

	server := ""
	if creds != nil {
		server = strings.TrimSpace(creds.ServerAddress)
		if creds.ServerPort > 0 {
			server = fmt.Sprintf("%s:%d", server, creds.ServerPort)
		}
	}
	if server == "" {
		return ibsrv.AgentConfig{}, fmt.Errorf("server address is required for agent mode")
	}

	infobase := ""
	if creds != nil {
		infobase = strings.TrimSpace(creds.InfobaseName)
		if infobase == "" {
			infobase = strings.TrimSpace(creds.BaseName)
		}
	}
	if infobase == "" {
		return ibsrv.AgentConfig{}, fmt.Errorf("infobase name is required for agent mode")
	}

	port := extractInt(data, "agent_port")
	listen := extractString(data, "agent_listen_address")
	baseDir := extractString(data, "agent_base_dir")
	hostKey := extractString(data, "agent_ssh_host_key")
	hostKeyAuto := extractBool(data, "agent_ssh_host_key_auto")
	if hostKey == "" && !hostKeyAuto {
		hostKeyAuto = true
	}

	startupTimeout := time.Duration(extractInt(data, "agent_startup_timeout_seconds")) * time.Second
	shutdownTimeout := time.Duration(extractInt(data, "agent_shutdown_timeout_seconds")) * time.Second

	return ibsrv.AgentConfig{
		ExecPath:        exePath,
		Server:          server,
		Infobase:        infobase,
		Username:        pickIBUsername(creds),
		Password:        pickIBPassword(creds),
		Port:            port,
		ListenAddress:   listen,
		SSHHostKeyPath:  hostKey,
		SSHHostKeyAuto:  hostKeyAuto,
		BaseDir:         baseDir,
		Visible:         extractBool(data, "agent_visible"),
		StartupTimeout:  startupTimeout,
		ShutdownTimeout: shutdownTimeout,
	}, nil
}

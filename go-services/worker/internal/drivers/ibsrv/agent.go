// go-services/worker/internal/drivers/ibsrv/agent.go
package ibsrv

import (
	"bytes"
	"context"
	"fmt"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

const (
	defaultAgentPort       = 1543
	defaultListenAddress   = "127.0.0.1"
	defaultStartupTimeout  = 30 * time.Second
	defaultShutdownTimeout = 5 * time.Second
)

type AgentConfig struct {
	ExecPath        string
	Server          string
	Infobase        string
	Username        string
	Password        string
	Port            int
	ListenAddress   string
	SSHHostKeyPath  string
	SSHHostKeyAuto  bool
	BaseDir         string
	Visible         bool
	StartupTimeout  time.Duration
	ShutdownTimeout time.Duration
}

type AgentProcess struct {
	cmd    *exec.Cmd
	stdout bytes.Buffer
	stderr bytes.Buffer
}

func StartAgent(ctx context.Context, cfg AgentConfig) (*AgentProcess, error) {
	exe := strings.TrimSpace(cfg.ExecPath)
	if exe == "" {
		return nil, fmt.Errorf("EXE_1CV8_PATH is not configured")
	}
	if _, err := os.Stat(exe); os.IsNotExist(err) {
		return nil, fmt.Errorf("1cv8.exe not found at path: %s", exe)
	}

	server := strings.TrimSpace(cfg.Server)
	infobase := strings.TrimSpace(cfg.Infobase)
	if server == "" || infobase == "" {
		return nil, fmt.Errorf("agent server or infobase is missing")
	}

	args := []string{"DESIGNER"}
	args = append(args, fmt.Sprintf("/S%s\\%s", server, infobase))
	if cfg.Username != "" {
		args = append(args, fmt.Sprintf("/N%s", cfg.Username))
	}
	if cfg.Password != "" {
		args = append(args, fmt.Sprintf("/P%s", cfg.Password))
	}
	args = append(args, "/AgentMode")

	port := cfg.Port
	if port <= 0 {
		port = defaultAgentPort
	}
	args = append(args, "/AgentPort", fmt.Sprintf("%d", port))

	listen := strings.TrimSpace(cfg.ListenAddress)
	if listen == "" {
		listen = defaultListenAddress
	}
	if listen != "" {
		args = append(args, "/AgentListenAddress", listen)
	}

	if cfg.SSHHostKeyPath != "" {
		hostKeyPath := filepath.Clean(cfg.SSHHostKeyPath)
		args = append(args, "/AgentSSHHostKey", hostKeyPath)
	} else if cfg.SSHHostKeyAuto {
		args = append(args, "/AgentSSHHostKeyAuto")
	} else {
		return nil, fmt.Errorf("AgentSSHHostKey or AgentSSHHostKeyAuto is required")
	}

	if cfg.BaseDir != "" {
		args = append(args, "/AgentBaseDir", cfg.BaseDir)
	}

	if cfg.Visible {
		args = append(args, "/Visible")
	}

	cmd := exec.CommandContext(ctx, exe, args...)
	proc := &AgentProcess{cmd: cmd}
	cmd.Stdout = &proc.stdout
	cmd.Stderr = &proc.stderr

	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("failed to start agent process: %w", err)
	}

	startupTimeout := cfg.StartupTimeout
	if startupTimeout == 0 {
		startupTimeout = defaultStartupTimeout
	}
	if err := waitForPort(ctx, listen, port, startupTimeout); err != nil {
		_ = proc.Stop(ctx, cfg.ShutdownTimeout)
		return nil, fmt.Errorf("agent did not start: %w", err)
	}

	return proc, nil
}

func (p *AgentProcess) Stop(ctx context.Context, timeout time.Duration) error {
	if p == nil || p.cmd == nil || p.cmd.Process == nil {
		return nil
	}

	if timeout == 0 {
		timeout = defaultShutdownTimeout
	}

	done := make(chan error, 1)
	go func() {
		done <- p.cmd.Process.Kill()
	}()

	select {
	case err := <-done:
		return err
	case <-time.After(timeout):
		return fmt.Errorf("agent stop timeout")
	case <-ctx.Done():
		return ctx.Err()
	}
}

func (p *AgentProcess) Output() string {
	if p == nil {
		return ""
	}
	stdout := strings.TrimSpace(p.stdout.String())
	stderr := strings.TrimSpace(p.stderr.String())
	if stdout == "" {
		return stderr
	}
	if stderr == "" {
		return stdout
	}
	return stdout + "\n" + stderr
}

func waitForPort(ctx context.Context, host string, port int, timeout time.Duration) error {
	deadline := time.Now().Add(timeout)
	address := fmt.Sprintf("%s:%d", host, port)

	for {
		if time.Now().After(deadline) {
			return fmt.Errorf("timeout waiting for agent port")
		}

		dialer := net.Dialer{Timeout: 500 * time.Millisecond}
		conn, err := dialer.DialContext(ctx, "tcp", address)
		if err == nil {
			_ = conn.Close()
			return nil
		}

		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(500 * time.Millisecond):
		}
	}
}

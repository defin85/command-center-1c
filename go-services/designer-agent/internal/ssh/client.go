package ssh

import (
	"bufio"
	"context"
	"errors"
	"fmt"
	"io"
	"strings"
	"sync"
	"time"

	"go.uber.org/zap"
	"golang.org/x/crypto/ssh"
)

// ClientConfig holds configuration for SSH client.
type ClientConfig struct {
	// Host is the SSH server hostname or IP
	Host string

	// Port is the SSH server port (default 22)
	Port int

	// User is the SSH username
	User string

	// Password for password authentication (optional)
	Password string

	// PrivateKey for key-based authentication (optional, PEM format)
	PrivateKey []byte

	// PrivateKeyPassphrase for encrypted private keys
	PrivateKeyPassphrase string

	// ConnectTimeout for establishing connection
	ConnectTimeout time.Duration

	// CommandTimeout for command execution
	CommandTimeout time.Duration

	// KeepAliveInterval for sending keep-alive packets
	KeepAliveInterval time.Duration

	// KeepAliveTimeout for keep-alive response
	KeepAliveTimeout time.Duration
}

// Key returns unique identifier for this connection config.
func (c ClientConfig) Key() string {
	return fmt.Sprintf("%s@%s:%d", c.User, c.Host, c.Port)
}

// Addr returns host:port string.
func (c ClientConfig) Addr() string {
	return fmt.Sprintf("%s:%d", c.Host, c.Port)
}

// Client represents an SSH client for 1C Agent Mode.
type Client struct {
	mu     sync.Mutex
	config ClientConfig
	logger *zap.Logger

	conn    *ssh.Client
	session *ssh.Session
	stdin   io.WriteCloser
	stdout  io.Reader
	stderr  io.Reader

	// Keep-alive management
	keepAliveDone chan struct{}
	keepAliveWg   sync.WaitGroup

	// Connection state
	connected bool
	lastUsed  time.Time
	createdAt time.Time
}

// CommandResult holds the result of command execution.
type CommandResult struct {
	Output   string
	Error    string
	ExitCode int
	Duration time.Duration
}

// ProgressInfo holds progress information during command execution.
type ProgressInfo struct {
	Line      string
	Timestamp time.Time
	IsError   bool
}

// NewClient creates a new SSH client and establishes connection.
func NewClient(cfg ClientConfig, logger *zap.Logger) (*Client, error) {
	if cfg.Port == 0 {
		cfg.Port = 22
	}
	if cfg.ConnectTimeout == 0 {
		cfg.ConnectTimeout = 30 * time.Second
	}
	if cfg.CommandTimeout == 0 {
		cfg.CommandTimeout = 300 * time.Second
	}
	if cfg.KeepAliveInterval == 0 {
		cfg.KeepAliveInterval = 30 * time.Second
	}
	if cfg.KeepAliveTimeout == 0 {
		cfg.KeepAliveTimeout = 15 * time.Second
	}

	client := &Client{
		config:        cfg,
		logger:        logger.With(zap.String("component", "ssh-client"), zap.String("host", cfg.Addr())),
		keepAliveDone: make(chan struct{}),
		createdAt:     time.Now(),
	}

	if err := client.connect(); err != nil {
		return nil, fmt.Errorf("failed to connect: %w", err)
	}

	return client, nil
}

// connect establishes SSH connection and starts interactive session.
func (c *Client) connect() error {
	c.mu.Lock()
	defer c.mu.Unlock()

	// Build auth methods
	var authMethods []ssh.AuthMethod

	if len(c.config.PrivateKey) > 0 {
		var signer ssh.Signer
		var err error

		if c.config.PrivateKeyPassphrase != "" {
			signer, err = ssh.ParsePrivateKeyWithPassphrase(c.config.PrivateKey, []byte(c.config.PrivateKeyPassphrase))
		} else {
			signer, err = ssh.ParsePrivateKey(c.config.PrivateKey)
		}

		if err != nil {
			return fmt.Errorf("failed to parse private key: %w", err)
		}
		authMethods = append(authMethods, ssh.PublicKeys(signer))
	}

	if c.config.Password != "" {
		authMethods = append(authMethods, ssh.Password(c.config.Password))
	}

	if len(authMethods) == 0 {
		return errors.New("no authentication method provided")
	}

	// SSH client config
	sshConfig := &ssh.ClientConfig{
		User:            c.config.User,
		Auth:            authMethods,
		HostKeyCallback: ssh.InsecureIgnoreHostKey(), // TODO: Add proper host key verification
		Timeout:         c.config.ConnectTimeout,
	}

	c.logger.Debug("connecting to SSH server")

	// Establish connection
	conn, err := ssh.Dial("tcp", c.config.Addr(), sshConfig)
	if err != nil {
		return fmt.Errorf("failed to dial: %w", err)
	}
	c.conn = conn

	// Create session
	session, err := conn.NewSession()
	if err != nil {
		conn.Close()
		return fmt.Errorf("failed to create session: %w", err)
	}
	c.session = session

	// Set up pipes for interactive communication
	stdin, err := session.StdinPipe()
	if err != nil {
		session.Close()
		conn.Close()
		return fmt.Errorf("failed to get stdin pipe: %w", err)
	}
	c.stdin = stdin

	stdout, err := session.StdoutPipe()
	if err != nil {
		stdin.Close()
		session.Close()
		conn.Close()
		return fmt.Errorf("failed to get stdout pipe: %w", err)
	}
	c.stdout = stdout

	stderr, err := session.StderrPipe()
	if err != nil {
		stdin.Close()
		session.Close()
		conn.Close()
		return fmt.Errorf("failed to get stderr pipe: %w", err)
	}
	c.stderr = stderr

	// Request PTY for interactive mode (1C agent requires this)
	modes := ssh.TerminalModes{
		ssh.ECHO:          0,     // Disable echoing
		ssh.TTY_OP_ISPEED: 14400, // Input speed = 14.4kbaud
		ssh.TTY_OP_OSPEED: 14400, // Output speed = 14.4kbaud
	}

	if err := session.RequestPty("xterm", 80, 40, modes); err != nil {
		c.logger.Warn("failed to request PTY, continuing without", zap.Error(err))
	}

	// Start shell
	if err := session.Shell(); err != nil {
		stdin.Close()
		session.Close()
		conn.Close()
		return fmt.Errorf("failed to start shell: %w", err)
	}

	c.connected = true
	c.lastUsed = time.Now()

	// Start keep-alive goroutine
	c.startKeepAlive()

	c.logger.Info("SSH connection established")
	return nil
}

// startKeepAlive starts the keep-alive goroutine.
func (c *Client) startKeepAlive() {
	c.keepAliveWg.Add(1)
	go func() {
		defer c.keepAliveWg.Done()

		ticker := time.NewTicker(c.config.KeepAliveInterval)
		defer ticker.Stop()

		for {
			select {
			case <-c.keepAliveDone:
				return
			case <-ticker.C:
				c.mu.Lock()
				if c.conn != nil {
					_, _, err := c.conn.SendRequest("keepalive@openssh.com", true, nil)
					if err != nil {
						c.logger.Warn("keep-alive failed", zap.Error(err))
					}
				}
				c.mu.Unlock()
			}
		}
	}()
}

// ExecuteCommand executes a command and returns the result.
func (c *Client) ExecuteCommand(ctx context.Context, command string) (*CommandResult, error) {
	return c.ExecuteCommandWithProgress(ctx, command, nil)
}

// ExecuteCommandWithProgress executes a command with progress reporting.
func (c *Client) ExecuteCommandWithProgress(ctx context.Context, command string, progressCh chan<- ProgressInfo) (*CommandResult, error) {
	c.mu.Lock()
	if !c.connected {
		c.mu.Unlock()
		return nil, errors.New("client not connected")
	}
	c.lastUsed = time.Now()
	c.mu.Unlock()

	startTime := time.Now()
	result := &CommandResult{}

	// Create timeout context
	ctx, cancel := context.WithTimeout(ctx, c.config.CommandTimeout)
	defer cancel()

	// Send command
	c.logger.Debug("executing command", zap.String("command", command))

	c.mu.Lock()
	_, err := fmt.Fprintf(c.stdin, "%s\n", command)
	c.mu.Unlock()

	if err != nil {
		return nil, fmt.Errorf("failed to send command: %w", err)
	}

	// Read output with progress
	var outputBuilder strings.Builder
	var errorBuilder strings.Builder

	outputDone := make(chan struct{})
	errorDone := make(chan struct{})

	// Read stdout
	go func() {
		defer close(outputDone)
		scanner := bufio.NewScanner(c.stdout)
		for scanner.Scan() {
			line := scanner.Text()
			outputBuilder.WriteString(line)
			outputBuilder.WriteString("\n")

			if progressCh != nil {
				select {
				case progressCh <- ProgressInfo{
					Line:      line,
					Timestamp: time.Now(),
					IsError:   false,
				}:
				default:
					// Don't block if channel is full
				}
			}

			// Check for completion marker (1C Agent specific)
			if c.isCompletionMarker(line) {
				return
			}
		}
	}()

	// Read stderr
	go func() {
		defer close(errorDone)
		scanner := bufio.NewScanner(c.stderr)
		for scanner.Scan() {
			line := scanner.Text()
			errorBuilder.WriteString(line)
			errorBuilder.WriteString("\n")

			if progressCh != nil {
				select {
				case progressCh <- ProgressInfo{
					Line:      line,
					Timestamp: time.Now(),
					IsError:   true,
				}:
				default:
				}
			}
		}
	}()

	// Wait for completion or timeout
	select {
	case <-ctx.Done():
		result.Output = outputBuilder.String()
		result.Error = errorBuilder.String()
		result.ExitCode = -1
		result.Duration = time.Since(startTime)
		return result, ctx.Err()
	case <-outputDone:
		// Command completed
	}

	result.Output = outputBuilder.String()
	result.Error = errorBuilder.String()
	result.ExitCode = c.parseExitCode(result.Output)
	result.Duration = time.Since(startTime)

	c.logger.Debug("command completed",
		zap.Duration("duration", result.Duration),
		zap.Int("exit_code", result.ExitCode))

	return result, nil
}

// isCompletionMarker checks if the line indicates command completion.
// 1C Agent Mode outputs specific markers when command finishes.
func (c *Client) isCompletionMarker(line string) bool {
	// Common completion markers for 1C Agent
	markers := []string{
		"Operation completed",
		"Result: Success",
		"Result: Failed",
		"Batch complete",
		"Process completed",
		">>>", // Common shell prompt return
	}

	for _, marker := range markers {
		if strings.Contains(line, marker) {
			return true
		}
	}
	return false
}

// parseExitCode extracts exit code from output.
func (c *Client) parseExitCode(output string) int {
	// Try to find exit code in output
	if strings.Contains(output, "Result: Success") ||
		strings.Contains(output, "Operation completed successfully") {
		return 0
	}
	if strings.Contains(output, "Result: Failed") ||
		strings.Contains(output, "Error:") {
		return 1
	}
	return 0 // Default to success if no indicators
}

// IsConnected returns true if the client is connected.
func (c *Client) IsConnected() bool {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.connected
}

// LastUsed returns the time when the client was last used.
func (c *Client) LastUsed() time.Time {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.lastUsed
}

// CreatedAt returns the time when the client was created.
func (c *Client) CreatedAt() time.Time {
	return c.createdAt
}

// Config returns the client configuration.
func (c *Client) Config() ClientConfig {
	return c.config
}

// Close closes the SSH connection.
func (c *Client) Close() error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if !c.connected {
		return nil
	}

	c.logger.Debug("closing SSH connection")

	// Stop keep-alive
	close(c.keepAliveDone)
	c.keepAliveWg.Wait()

	var errs []error

	if c.stdin != nil {
		if err := c.stdin.Close(); err != nil {
			errs = append(errs, fmt.Errorf("stdin close: %w", err))
		}
	}

	if c.session != nil {
		if err := c.session.Close(); err != nil {
			errs = append(errs, fmt.Errorf("session close: %w", err))
		}
	}

	if c.conn != nil {
		if err := c.conn.Close(); err != nil {
			errs = append(errs, fmt.Errorf("connection close: %w", err))
		}
	}

	c.connected = false
	c.logger.Info("SSH connection closed")

	if len(errs) > 0 {
		return errors.Join(errs...)
	}
	return nil
}

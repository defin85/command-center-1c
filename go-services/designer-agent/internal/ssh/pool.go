package ssh

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"time"

	"go.uber.org/zap"
)

// PoolConfig holds configuration for the SSH connection pool.
type PoolConfig struct {
	// MaxConnectionsPerHost is the maximum number of connections per host:port
	MaxConnectionsPerHost int

	// IdleTimeout is the duration after which idle connections are closed
	IdleTimeout time.Duration

	// CleanupInterval is the interval for running idle connection cleanup
	CleanupInterval time.Duration

	// DefaultConnectTimeout for new connections
	DefaultConnectTimeout time.Duration

	// DefaultCommandTimeout for command execution
	DefaultCommandTimeout time.Duration

	// KeepAliveInterval for keep-alive packets
	KeepAliveInterval time.Duration

	// KeepAliveTimeout for keep-alive response
	KeepAliveTimeout time.Duration
}

// DefaultPoolConfig returns default pool configuration.
func DefaultPoolConfig() PoolConfig {
	return PoolConfig{
		MaxConnectionsPerHost: 5,
		IdleTimeout:           10 * time.Minute,
		CleanupInterval:       1 * time.Minute,
		DefaultConnectTimeout: 30 * time.Second,
		DefaultCommandTimeout: 300 * time.Second,
		KeepAliveInterval:     30 * time.Second,
		KeepAliveTimeout:      15 * time.Second,
	}
}

// pooledClient wraps a Client with pool metadata.
type pooledClient struct {
	client  *Client
	inUse   bool
	lastUse time.Time
}

// hostPool manages connections for a single host:port.
type hostPool struct {
	mu      sync.Mutex
	clients []*pooledClient
	maxSize int
}

// Pool manages SSH connections with connection pooling.
type Pool struct {
	mu     sync.RWMutex
	pools  map[string]*hostPool // key = host:port
	config PoolConfig
	logger *zap.Logger

	// Cleanup management
	cleanupDone chan struct{}
	cleanupWg   sync.WaitGroup
	closed      bool
}

// PoolStats contains pool statistics.
type PoolStats struct {
	TotalHosts            int
	TotalConnections      int
	ActiveConnections     int
	IdleConnections       int
	MaxConnectionsPerHost int
	IdleTimeout           time.Duration
}

// NewPool creates a new SSH connection pool.
func NewPool(cfg PoolConfig, logger *zap.Logger) *Pool {
	if cfg.MaxConnectionsPerHost <= 0 {
		cfg.MaxConnectionsPerHost = 5
	}
	if cfg.IdleTimeout <= 0 {
		cfg.IdleTimeout = 10 * time.Minute
	}
	if cfg.CleanupInterval <= 0 {
		cfg.CleanupInterval = 1 * time.Minute
	}

	pool := &Pool{
		pools:       make(map[string]*hostPool),
		config:      cfg,
		logger:      logger.With(zap.String("component", "ssh-pool")),
		cleanupDone: make(chan struct{}),
	}

	// Start cleanup goroutine
	pool.startCleanup()

	pool.logger.Info("SSH connection pool created",
		zap.Int("max_connections_per_host", cfg.MaxConnectionsPerHost),
		zap.Duration("idle_timeout", cfg.IdleTimeout))

	return pool
}

// startCleanup starts the cleanup goroutine.
func (p *Pool) startCleanup() {
	p.cleanupWg.Add(1)
	go func() {
		defer p.cleanupWg.Done()

		ticker := time.NewTicker(p.config.CleanupInterval)
		defer ticker.Stop()

		for {
			select {
			case <-p.cleanupDone:
				return
			case <-ticker.C:
				p.cleanupIdleConnections()
			}
		}
	}()
}

// cleanupIdleConnections removes idle connections that exceeded idle timeout.
func (p *Pool) cleanupIdleConnections() {
	p.mu.Lock()
	defer p.mu.Unlock()

	now := time.Now()
	removedCount := 0

	for hostKey, hp := range p.pools {
		hp.mu.Lock()

		// Filter out idle connections
		activeClients := make([]*pooledClient, 0, len(hp.clients))
		for _, pc := range hp.clients {
			if !pc.inUse && now.Sub(pc.lastUse) > p.config.IdleTimeout {
				// Close idle connection
				if err := pc.client.Close(); err != nil {
					p.logger.Warn("failed to close idle connection",
						zap.String("host", hostKey),
						zap.Error(err))
				}
				removedCount++
			} else {
				activeClients = append(activeClients, pc)
			}
		}
		hp.clients = activeClients

		// Remove empty host pools
		if len(hp.clients) == 0 {
			delete(p.pools, hostKey)
		}

		hp.mu.Unlock()
	}

	if removedCount > 0 {
		p.logger.Debug("cleaned up idle connections",
			zap.Int("removed", removedCount))
	}
}

// GetClient gets or creates an SSH client for the given configuration.
func (p *Pool) GetClient(ctx context.Context, cfg ClientConfig) (*Client, error) {
	p.mu.Lock()
	if p.closed {
		p.mu.Unlock()
		return nil, errors.New("pool is closed")
	}

	// Apply default timeouts if not set
	if cfg.ConnectTimeout == 0 {
		cfg.ConnectTimeout = p.config.DefaultConnectTimeout
	}
	if cfg.CommandTimeout == 0 {
		cfg.CommandTimeout = p.config.DefaultCommandTimeout
	}
	if cfg.KeepAliveInterval == 0 {
		cfg.KeepAliveInterval = p.config.KeepAliveInterval
	}
	if cfg.KeepAliveTimeout == 0 {
		cfg.KeepAliveTimeout = p.config.KeepAliveTimeout
	}

	hostKey := cfg.Addr()

	// Get or create host pool
	hp, exists := p.pools[hostKey]
	if !exists {
		hp = &hostPool{
			clients: make([]*pooledClient, 0, p.config.MaxConnectionsPerHost),
			maxSize: p.config.MaxConnectionsPerHost,
		}
		p.pools[hostKey] = hp
	}
	p.mu.Unlock()

	// Try to get existing idle connection
	hp.mu.Lock()
	for _, pc := range hp.clients {
		if !pc.inUse && pc.client.IsConnected() {
			// Check if credentials match
			if pc.client.Config().User == cfg.User {
				pc.inUse = true
				pc.lastUse = time.Now()
				hp.mu.Unlock()

				p.logger.Debug("reusing existing connection",
					zap.String("host", hostKey))
				return pc.client, nil
			}
		}
	}

	// Check if we can create a new connection
	if len(hp.clients) >= hp.maxSize {
		hp.mu.Unlock()
		return nil, fmt.Errorf("connection limit reached for %s (max: %d)", hostKey, hp.maxSize)
	}
	hp.mu.Unlock()

	// Create new connection
	p.logger.Debug("creating new connection",
		zap.String("host", hostKey))

	client, err := NewClient(cfg, p.logger)
	if err != nil {
		return nil, fmt.Errorf("failed to create client: %w", err)
	}

	// Add to pool
	hp.mu.Lock()
	pc := &pooledClient{
		client:  client,
		inUse:   true,
		lastUse: time.Now(),
	}
	hp.clients = append(hp.clients, pc)
	hp.mu.Unlock()

	return client, nil
}

// ReleaseClient returns a client to the pool for reuse.
func (p *Pool) ReleaseClient(client *Client) {
	if client == nil {
		return
	}

	p.mu.RLock()
	if p.closed {
		p.mu.RUnlock()
		client.Close()
		return
	}

	hostKey := client.Config().Addr()
	hp, exists := p.pools[hostKey]
	p.mu.RUnlock()

	if !exists {
		client.Close()
		return
	}

	hp.mu.Lock()
	defer hp.mu.Unlock()

	for _, pc := range hp.clients {
		if pc.client == client {
			pc.inUse = false
			pc.lastUse = time.Now()
			p.logger.Debug("released connection to pool",
				zap.String("host", hostKey))
			return
		}
	}

	// Client not found in pool, close it
	client.Close()
}

// RemoveClient removes a client from the pool and closes it.
func (p *Pool) RemoveClient(client *Client) {
	if client == nil {
		return
	}

	p.mu.Lock()
	hostKey := client.Config().Addr()
	hp, exists := p.pools[hostKey]
	p.mu.Unlock()

	if !exists {
		client.Close()
		return
	}

	hp.mu.Lock()
	defer hp.mu.Unlock()

	for i, pc := range hp.clients {
		if pc.client == client {
			// Remove from slice
			hp.clients = append(hp.clients[:i], hp.clients[i+1:]...)
			client.Close()
			p.logger.Debug("removed connection from pool",
				zap.String("host", hostKey))
			return
		}
	}

	// Client not found, just close it
	client.Close()
}

// Stats returns pool statistics.
func (p *Pool) Stats() PoolStats {
	p.mu.RLock()
	defer p.mu.RUnlock()

	stats := PoolStats{
		TotalHosts:            len(p.pools),
		MaxConnectionsPerHost: p.config.MaxConnectionsPerHost,
		IdleTimeout:           p.config.IdleTimeout,
	}

	for _, hp := range p.pools {
		hp.mu.Lock()
		for _, pc := range hp.clients {
			stats.TotalConnections++
			if pc.inUse {
				stats.ActiveConnections++
			} else {
				stats.IdleConnections++
			}
		}
		hp.mu.Unlock()
	}

	return stats
}

// HostStats returns statistics for a specific host.
func (p *Pool) HostStats(host string, port int) (total, active, idle int) {
	hostKey := fmt.Sprintf("%s:%d", host, port)

	p.mu.RLock()
	hp, exists := p.pools[hostKey]
	p.mu.RUnlock()

	if !exists {
		return 0, 0, 0
	}

	hp.mu.Lock()
	defer hp.mu.Unlock()

	for _, pc := range hp.clients {
		total++
		if pc.inUse {
			active++
		} else {
			idle++
		}
	}

	return total, active, idle
}

// Close closes all connections and shuts down the pool.
func (p *Pool) Close() error {
	p.mu.Lock()
	if p.closed {
		p.mu.Unlock()
		return nil
	}
	p.closed = true
	p.mu.Unlock()

	p.logger.Info("closing SSH connection pool")

	// Stop cleanup goroutine
	close(p.cleanupDone)
	p.cleanupWg.Wait()

	// Close all connections
	p.mu.Lock()
	defer p.mu.Unlock()

	var errs []error
	for hostKey, hp := range p.pools {
		hp.mu.Lock()
		for _, pc := range hp.clients {
			if err := pc.client.Close(); err != nil {
				errs = append(errs, fmt.Errorf("close %s: %w", hostKey, err))
			}
		}
		hp.clients = nil
		hp.mu.Unlock()
	}

	p.pools = make(map[string]*hostPool)

	p.logger.Info("SSH connection pool closed")

	if len(errs) > 0 {
		return errors.Join(errs...)
	}
	return nil
}

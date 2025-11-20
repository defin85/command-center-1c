package ras

import (
	"context"
	"fmt"
	"sync"
	"time"

	"go.uber.org/zap"
)

// Pool manages a pool of RAS connections
type Pool struct {
	serverAddr  string
	connTimeout time.Duration
	reqTimeout  time.Duration
	maxConns    int

	mu      sync.Mutex
	clients []*Client
	logger  *zap.Logger
}

// NewPool creates a new RAS connection pool
func NewPool(serverAddr string, maxConns int, connTimeout, reqTimeout time.Duration, logger *zap.Logger) (*Pool, error) {
	if serverAddr == "" {
		return nil, ErrInvalidParams
	}

	if maxConns <= 0 {
		maxConns = 10 // Default
	}

	return &Pool{
		serverAddr:  serverAddr,
		connTimeout: connTimeout,
		reqTimeout:  reqTimeout,
		maxConns:    maxConns,
		clients:     make([]*Client, 0, maxConns),
		logger:      logger,
	}, nil
}

// GetConnection acquires a RAS client from the pool
func (p *Pool) GetConnection(ctx context.Context) (*Client, error) {
	p.mu.Lock()
	defer p.mu.Unlock()

	// Try to reuse existing connection
	if len(p.clients) > 0 {
		client := p.clients[0]
		p.clients = p.clients[1:]
		return client, nil
	}

	// Create new connection if pool not exhausted
	client, err := NewClient(p.serverAddr, p.connTimeout, p.reqTimeout, p.logger)
	if err != nil {
		return nil, fmt.Errorf("failed to create RAS client: %w", err)
	}

	p.logger.Debug("created new RAS client connection",
		zap.String("server", p.serverAddr))

	return client, nil
}

// ReleaseConnection returns a RAS client to the pool with health check
func (p *Pool) ReleaseConnection(client *Client) {
	if client == nil {
		return
	}

	// Health check: verify connection is still alive
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	_, err := client.GetClusters(ctx)
	if err != nil {
		p.logger.Warn("Connection health check failed, closing client", zap.Error(err))
		client.Close()
		return
	}

	p.mu.Lock()
	defer p.mu.Unlock()

	// Return to pool if not full
	if len(p.clients) < p.maxConns {
		p.clients = append(p.clients, client)
		p.logger.Debug("returned RAS client to pool",
			zap.Int("pool_size", len(p.clients)))
	} else {
		// Pool is full, close connection
		client.Close()
		p.logger.Debug("pool full, closed excess RAS client")
	}
}

// Close closes all connections in the pool
func (p *Pool) Close() error {
	p.mu.Lock()
	defer p.mu.Unlock()

	for _, client := range p.clients {
		if err := client.Close(); err != nil {
			p.logger.Warn("error closing RAS client", zap.Error(err))
		}
	}

	p.clients = nil
	p.logger.Info("RAS connection pool closed")

	return nil
}

// Stats returns pool statistics
func (p *Pool) Stats() map[string]interface{} {
	p.mu.Lock()
	defer p.mu.Unlock()

	return map[string]interface{}{
		"server":          p.serverAddr,
		"max_connections": p.maxConns,
		"active":          len(p.clients),
	}
}

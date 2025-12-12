package odata

import (
	"crypto/tls"
	"net"
	"net/http"
	"sync"
	"time"
)

// Pool manages HTTP transports for connection reuse.
// Each unique baseURL gets its own transport to maximize connection pooling.
type Pool struct {
	mu         sync.RWMutex
	transports map[string]*http.Transport // key = baseURL
	maxConns   int
	timeout    time.Duration
}

// NewPool creates a new connection pool.
func NewPool(maxConnsPerHost int, timeout time.Duration) *Pool {
	if maxConnsPerHost <= 0 {
		maxConnsPerHost = 10
	}
	if timeout <= 0 {
		timeout = 30 * time.Second
	}

	return &Pool{
		transports: make(map[string]*http.Transport),
		maxConns:   maxConnsPerHost,
		timeout:    timeout,
	}
}

// GetTransport returns transport for baseURL (creates if not exists).
// Transports are cached per baseURL to maximize TCP connection reuse.
func (p *Pool) GetTransport(baseURL string) *http.Transport {
	// Try read lock first (common path)
	p.mu.RLock()
	transport, exists := p.transports[baseURL]
	p.mu.RUnlock()

	if exists {
		return transport
	}

	// Create new transport under write lock
	p.mu.Lock()
	defer p.mu.Unlock()

	// Double-check after acquiring write lock
	if transport, exists = p.transports[baseURL]; exists {
		return transport
	}

	transport = &http.Transport{
		// Connection pooling
		MaxIdleConns:        p.maxConns * 2, // Total idle connections
		MaxIdleConnsPerHost: p.maxConns,     // Per-host idle connections
		MaxConnsPerHost:     p.maxConns,     // Max concurrent connections per host
		IdleConnTimeout:     90 * time.Second,

		// Timeouts
		DialContext: (&net.Dialer{
			Timeout:   10 * time.Second, // Connection timeout
			KeepAlive: 30 * time.Second,
		}).DialContext,
		TLSHandshakeTimeout:   10 * time.Second,
		ResponseHeaderTimeout: p.timeout,
		ExpectContinueTimeout: 1 * time.Second,

		// TLS config (1C often uses self-signed certs)
		TLSClientConfig: &tls.Config{
			InsecureSkipVerify: true, // TODO: Make configurable
		},

		// Disable compression (1C OData responses are usually small)
		DisableCompression: false,
	}

	p.transports[baseURL] = transport
	return transport
}

// Close closes all transports and releases connections.
func (p *Pool) Close() {
	p.mu.Lock()
	defer p.mu.Unlock()

	for _, transport := range p.transports {
		transport.CloseIdleConnections()
	}

	// Clear the map
	p.transports = make(map[string]*http.Transport)
}

// Stats returns pool statistics.
func (p *Pool) Stats() PoolStats {
	p.mu.RLock()
	defer p.mu.RUnlock()

	return PoolStats{
		TransportCount: len(p.transports),
		MaxConnsPerHost: p.maxConns,
		Timeout:        p.timeout,
	}
}

// PoolStats contains pool statistics.
type PoolStats struct {
	TransportCount  int
	MaxConnsPerHost int
	Timeout         time.Duration
}

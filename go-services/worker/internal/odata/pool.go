package odata

import (
	"sync"
)

// ClientPool provides shared OData clients across worker subsystems.
type ClientPool struct {
	mu      sync.RWMutex
	clients map[string]*Client
}

var (
	defaultPoolOnce sync.Once
	defaultPool     *ClientPool
)

// DefaultPool returns a shared pool for OData clients.
func DefaultPool() *ClientPool {
	defaultPoolOnce.Do(func() {
		defaultPool = NewClientPool()
	})
	return defaultPool
}

// NewClientPool creates a new client pool.
func NewClientPool() *ClientPool {
	return &ClientPool{
		clients: make(map[string]*Client),
	}
}

// Get returns a cached client or creates a new one.
func (p *ClientPool) Get(baseURL, username, password string) *Client {
	if p == nil {
		return DefaultPool().Get(baseURL, username, password)
	}

	key := baseURL + "|" + username + "|" + password

	p.mu.RLock()
	if client, ok := p.clients[key]; ok {
		p.mu.RUnlock()
		return client
	}
	p.mu.RUnlock()

	p.mu.Lock()
	defer p.mu.Unlock()

	if client, ok := p.clients[key]; ok {
		return client
	}

	client := NewClient(ClientConfig{
		BaseURL: baseURL,
		Auth: Auth{
			Username: username,
			Password: password,
		},
	})

	p.clients[key] = client
	return client
}

// CacheSize returns number of cached clients.
func (p *ClientPool) CacheSize() int {
	if p == nil {
		return DefaultPool().CacheSize()
	}
	p.mu.RLock()
	defer p.mu.RUnlock()
	return len(p.clients)
}

package odata

import (
	"testing"
	"time"
)

func TestNewPool(t *testing.T) {
	tests := []struct {
		name            string
		maxConnsPerHost int
		timeout         time.Duration
		wantMaxConns    int
		wantTimeout     time.Duration
	}{
		{
			name:            "default values",
			maxConnsPerHost: 0,
			timeout:         0,
			wantMaxConns:    10,
			wantTimeout:     30 * time.Second,
		},
		{
			name:            "custom values",
			maxConnsPerHost: 20,
			timeout:         60 * time.Second,
			wantMaxConns:    20,
			wantTimeout:     60 * time.Second,
		},
		{
			name:            "negative values",
			maxConnsPerHost: -5,
			timeout:         -10 * time.Second,
			wantMaxConns:    10,
			wantTimeout:     30 * time.Second,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			pool := NewPool(tt.maxConnsPerHost, tt.timeout)
			if pool == nil {
				t.Fatal("NewPool() returned nil")
			}

			stats := pool.Stats()
			if stats.MaxConnsPerHost != tt.wantMaxConns {
				t.Errorf("MaxConnsPerHost = %v, want %v", stats.MaxConnsPerHost, tt.wantMaxConns)
			}
			if stats.Timeout != tt.wantTimeout {
				t.Errorf("Timeout = %v, want %v", stats.Timeout, tt.wantTimeout)
			}

			pool.Close()
		})
	}
}

func TestPoolGetTransport(t *testing.T) {
	pool := NewPool(10, 30*time.Second)
	defer pool.Close()

	// Get transport for first URL
	url1 := "http://server1/odata"
	transport1 := pool.GetTransport(url1)
	if transport1 == nil {
		t.Fatal("GetTransport() returned nil")
	}

	// Get same transport again (should be cached)
	transport1Again := pool.GetTransport(url1)
	if transport1Again != transport1 {
		t.Error("GetTransport() should return cached transport")
	}

	// Get transport for different URL
	url2 := "http://server2/odata"
	transport2 := pool.GetTransport(url2)
	if transport2 == nil {
		t.Fatal("GetTransport() returned nil for second URL")
	}
	if transport2 == transport1 {
		t.Error("GetTransport() should return different transport for different URL")
	}

	// Check stats
	stats := pool.Stats()
	if stats.TransportCount != 2 {
		t.Errorf("TransportCount = %v, want 2", stats.TransportCount)
	}
}

func TestPoolClose(t *testing.T) {
	pool := NewPool(10, 30*time.Second)

	// Create some transports
	pool.GetTransport("http://server1/odata")
	pool.GetTransport("http://server2/odata")

	// Close pool
	pool.Close()

	// Check that transports are cleared
	stats := pool.Stats()
	if stats.TransportCount != 0 {
		t.Errorf("TransportCount after Close() = %v, want 0", stats.TransportCount)
	}
}

func TestPoolConcurrency(t *testing.T) {
	pool := NewPool(10, 30*time.Second)
	defer pool.Close()

	// Concurrent access to same URL
	done := make(chan bool, 10)
	url := "http://server/odata"

	for i := 0; i < 10; i++ {
		go func() {
			transport := pool.GetTransport(url)
			if transport == nil {
				t.Error("GetTransport() returned nil in concurrent access")
			}
			done <- true
		}()
	}

	// Wait for all goroutines
	for i := 0; i < 10; i++ {
		<-done
	}

	// Should still be only one transport
	stats := pool.Stats()
	if stats.TransportCount != 1 {
		t.Errorf("TransportCount after concurrent access = %v, want 1", stats.TransportCount)
	}
}

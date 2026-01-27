package pool

import (
	"context"
	"sync/atomic"

	"github.com/commandcenter1c/commandcenter/ras-client/serialize/esig"
)

func (p *endpointPool) NewEndpoint(ctx context.Context) (*Endpoint, error) {
	if p.closed() {
		return nil, ErrClosed
	}

	err := p.waitTurn(ctx)
	if err != nil {
		return nil, err
	}

	for {
		p.connsMu.Lock()
		endpoint := p.popIdle(esig.ESIG{})
		p.connsMu.Unlock()

		if endpoint == nil {
			break
		}

		if p.isStaleConn(endpoint.conn) {
			_ = p.CloseConn(endpoint.conn)
			continue
		}

		if !endpoint.Inited {
			endpoint, err = p.openEndpoint(ctx, endpoint.conn)

			if err != nil {
				return nil, err
			}
		}

		return endpoint, nil
	}

	newConn, err := p.newConn(ctx, true)
	if err != nil {
		p.freeTurn()
		return nil, err
	}

	endpoint, err := p.openEndpoint(ctx, newConn)

	return endpoint, err
}

func (p *endpointPool) Put(ctx context.Context, cn *Endpoint) {
	if !cn.conn.pooled {
		p.Remove(ctx, cn, nil)
		return
	}

	p.connsMu.Lock()
	p.idleConns = append(p.idleConns, cn.conn)
	p.idleConnsLen++
	p.connsMu.Unlock()
	p.freeTurn()
}

// Get returns existed connection from the pool or creates a new one.
func (p *endpointPool) Get(ctx context.Context, sig esig.ESIG) (*Endpoint, error) {
	if p.closed() {
		return nil, ErrClosed
	}

	err := p.waitTurn(ctx)
	if err != nil {
		return nil, err
	}

	for {
		p.connsMu.Lock()
		endpoint := p.popIdle(sig)
		p.connsMu.Unlock()

		if endpoint == nil {
			break
		}

		if p.isStaleConn(endpoint.conn) {
			_ = p.CloseConn(endpoint.conn)
			continue
		}

		if !endpoint.Inited {
			endpoint, err = p.openEndpoint(ctx, endpoint.conn)
			if err != nil {
				return nil, err
			}
		}

		return endpoint, nil
	}

	newConn, err := p.newConn(ctx, true)
	if err != nil {
		p.freeTurn()
		return nil, err
	}

	endpoint, err := p.openEndpoint(ctx, newConn)

	return endpoint, err
}

func (p *endpointPool) Remove(_ context.Context, cn *Endpoint, _ error) {
	p.removeConnWithLock(cn.conn)
	p.freeTurn()
	_ = p.closeConn(cn.conn)
}

func (p *endpointPool) CloseConn(cn *Conn) error {
	p.removeConnWithLock(cn)
	return p.closeConn(cn)
}

// Len returns total number of connections.
func (p *endpointPool) Len() int {
	p.connsMu.Lock()
	n := len(p.conns)
	p.connsMu.Unlock()
	return n
}

// IdleLen returns number of idle connections.
func (p *endpointPool) IdleLen() int {
	p.connsMu.Lock()
	n := p.idleConnsLen
	p.connsMu.Unlock()
	return n
}

func (p *endpointPool) Close() error {
	if !atomic.CompareAndSwapUint32(&p._closed, 0, 1) {
		return ErrClosed
	}

	var firstErr error
	p.connsMu.Lock()
	for _, cn := range p.conns {
		if err := p.closeConn(cn); err != nil && firstErr == nil {
			firstErr = err
		}
	}
	p.conns = nil
	p.poolSize = 0
	p.idleConns = nil
	p.idleConnsLen = 0
	p.connsMu.Unlock()

	return firstErr
}

func (p *endpointPool) CloseEndpoint(*Endpoint) error {
	panic("implement me")
}

func (p *endpointPool) ReapStaleConns() (int, error) {
	var n int
	for {
		p.getTurn()

		p.connsMu.Lock()
		cn := p.reapStaleConn()
		p.connsMu.Unlock()

		p.freeTurn()

		if cn != nil {
			_ = p.closeConn(cn)
			n++
		} else {
			break
		}
	}
	return n, nil
}

func (p *endpointPool) openEndpoint(ctx context.Context, conn *Conn) (*Endpoint, error) {
	if p.closed() {
		return nil, ErrClosed
	}

	if !conn.Inited {
		err := p.opt.InitConnection(ctx, conn)
		if err != nil {
			return nil, err
		}
		conn.Inited = true
	}

	openAck, err := p.opt.OpenEndpoint(ctx, conn)
	if err != nil {
		return nil, err
	}

	endpoint := NewEndpoint(openAck)
	endpoint.Inited = true
	endpoint.onRequest = p.onRequest
	endpoint.conn = conn
	conn.endpoints = append(conn.endpoints, endpoint)

	return endpoint, nil
}

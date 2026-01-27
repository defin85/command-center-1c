package pool

import (
	"sync/atomic"
	"time"

	"github.com/commandcenter1c/commandcenter/ras-client/serialize/esig"
)

func (p *endpointPool) popIdle(sig esig.ESIG) *Endpoint {
	if len(p.idleConns) == 0 {
		return nil
	}

	endpoint := p.idleConns.Pop(sig, p.opt.MaxOpenEndpoints)
	if endpoint == nil {
		return nil
	}

	p.idleConnsLen--
	p.checkMinIdleConns()
	return endpoint
}

func (p *endpointPool) removeConnWithLock(cn *Conn) {
	p.connsMu.Lock()
	p.removeConn(cn)
	p.connsMu.Unlock()
}

func (p *endpointPool) removeConn(cn *Conn) {
	for i, c := range p.conns {
		if c == cn {
			p.conns = append(p.conns[:i], p.conns[i+1:]...)
			if cn.pooled {
				p.poolSize--
				p.checkMinIdleConns()
			}

			return
		}
	}
}

func (p *endpointPool) closeConn(cn *Conn) error {
	if p.opt.OnClose != nil {
		_ = p.opt.OnClose(cn)
	}
	return cn.Close()
}

func (p *endpointPool) closed() bool {
	return atomic.LoadUint32(&p._closed) == 1
}

func (p *endpointPool) reaper(frequency time.Duration) {
	ticker := time.NewTicker(frequency)
	defer ticker.Stop()

	for range ticker.C {
		if p.closed() {
			break
		}
		_, err := p.ReapStaleConns()
		if err != nil {
			continue
		}
	}
}

func (p *endpointPool) reapStaleConn() *Conn {
	if len(p.idleConns) == 0 {
		return nil
	}

	cn := p.idleConns[0]
	if !p.isStaleConn(cn) {
		return nil
	}

	p.idleConns = append(p.idleConns[:0], p.idleConns[1:]...)
	p.idleConnsLen--
	p.removeConn(cn)

	return cn
}

func (p *endpointPool) isStaleConn(cn *Conn) bool {
	if cn.closed() {
		return true
	}

	if p.opt.IdleTimeout == 0 && p.opt.MaxConnAge == 0 {
		return false
	}

	now := time.Now()
	if p.opt.IdleTimeout > 0 && now.Sub(cn.UsedAt()) >= p.opt.IdleTimeout {
		return true
	}
	if p.opt.MaxConnAge > 0 && now.Sub(cn.createdAt) >= p.opt.MaxConnAge {
		return true
	}

	return false
}

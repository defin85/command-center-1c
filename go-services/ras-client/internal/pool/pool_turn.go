package pool

import (
	"context"
	"time"
)

func (p *endpointPool) getTurn() {
	p.queue <- struct{}{}
}

func (p *endpointPool) waitTurn(c context.Context) error {
	select {
	case <-c.Done():
		return c.Err()
	default:
	}

	select {
	case p.queue <- struct{}{}:
		return nil
	default:
	}

	timer := timers.Get().(*time.Timer)
	timer.Reset(p.opt.PoolTimeout)

	select {
	case <-c.Done():
		if !timer.Stop() {
			<-timer.C
		}
		timers.Put(timer)
		return c.Err()
	case p.queue <- struct{}{}:
		if !timer.Stop() {
			<-timer.C
		}
		timers.Put(timer)
		return nil
	case <-timer.C:
		timers.Put(timer)
		//atomic.AddUint32(&p.stats.Timeouts, 1)
		return ErrPoolTimeout
	}
}

func (p *endpointPool) freeTurn() {
	<-p.queue
}

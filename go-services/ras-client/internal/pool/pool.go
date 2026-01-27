package pool

import (
	"context"
	"errors"
	"sync"
	"time"

	"github.com/commandcenter1c/commandcenter/ras-client/messages"
	"github.com/commandcenter1c/commandcenter/ras-client/serialize/esig"
	uuid "github.com/satori/go.uuid"
)

// What exists
// 1) Connection client (Conn).
// 2) Multiple endpoints per client:
//   - cluster auth
//   - infobase auth (per infobase, may require re-auth on change)
// 3) Endpoints split by scope (cluster vs infobase).
//
// Goal: endpoint pool that can reuse connections and minimize auth churn.

var (
	ErrClosed         = errors.New("protocol: pool is closed")
	ErrUnknownMessage = errors.New("protocol: unknown message packet")
	ErrPoolTimeout    = errors.New("protocol: endpoint pool timeout")
)

var timers = sync.Pool{
	New: func() interface{} {
		t := time.NewTimer(time.Hour)
		t.Stop()
		return t
	},
}

var _ EndpointPool = (*endpointPool)(nil)

func NewEndpointPool(opt *Options) EndpointPool {
	p := &endpointPool{
		opt:             opt,
		queue:           make(chan struct{}, opt.PoolSize),
		conns:           make([]*Conn, 0, opt.PoolSize),
		idleConns:       make([]*Conn, 0, opt.PoolSize),
		authInfobaseIdx: make(map[uuid.UUID]struct{ user, password string }),
		authClusterIdx:  make(map[uuid.UUID]struct{ user, password string }),
	}

	p.connsMu.Lock()
	p.checkMinIdleConns()
	p.connsMu.Unlock()

	if opt.IdleTimeout > 0 && opt.IdleCheckFrequency > 0 {
		go p.reaper(opt.IdleCheckFrequency)
	}

	return p
}

type EndpointPool interface {
	NewEndpoint(ctx context.Context) (*Endpoint, error)
	CloseEndpoint(endpoint *Endpoint) error

	Get(ctx context.Context, sig esig.ESIG) (*Endpoint, error)
	Put(ctx context.Context, endpoint *Endpoint)
	Remove(ctx context.Context, endpoint *Endpoint, err error)

	Len() int
	IdleLen() int

	Close() error

	SetAgentAuth(user, password string)
	SetClusterAuth(id uuid.UUID, user, password string)
	SetInfobaseAuth(id uuid.UUID, user, password string)
	GetClusterAuth(id uuid.UUID) (user, password string)
	GetInfobaseAuth(id uuid.UUID) (user, password string)
}

type Pooler interface {
	NewConn(context.Context) (*Conn, error)
	CloseConn(*Conn) error

	Get(context.Context) (*Conn, error)
	Put(context.Context, *Conn)
	Remove(context.Context, *Conn, error)

	Len() int
	IdleLen() int
	Close() error
}

type endpointPool struct {
	opt *Options

	dialErrorsNum uint32 // atomic

	_closed uint32 // atomic

	lastDialErrorMu sync.RWMutex
	lastDialError   error

	queue chan struct{}

	poolSize     int
	idleConnsLen int

	connsMu   sync.Mutex
	conns     []*Conn
	idleConns IdleConns

	authClusterIdx  map[uuid.UUID]struct{ user, password string }
	authInfobaseIdx map[uuid.UUID]struct{ user, password string }
	authAgent       struct{ user, password string }
}

func needAgentAuth(req messages.EndpointRequestMessage) bool {
	switch req.(type) {
	case *messages.GetAgentAdminsRequest, *messages.RegAgentAdminRequest, *messages.UnregAgentAdminRequest,
		*messages.RegClusterRequest, *messages.UnregClusterRequest:
		return true
	}

	return false
}

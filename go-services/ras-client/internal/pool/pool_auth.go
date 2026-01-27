package pool

import (
	uuid "github.com/satori/go.uuid"
)

func (p *endpointPool) SetAgentAuth(user, password string) {
	p.authAgent = struct{ user, password string }{user: user, password: password}
}

func (p *endpointPool) SetClusterAuth(id uuid.UUID, user, password string) {
	p.authClusterIdx[id] = struct{ user, password string }{user: user, password: password}
}

func (p *endpointPool) SetInfobaseAuth(id uuid.UUID, user, password string) {
	p.authInfobaseIdx[id] = struct{ user, password string }{user: user, password: password}
}

func (p *endpointPool) GetClusterAuth(id uuid.UUID) (user, password string) {
	return p.getAuth(p.authClusterIdx, id)
}

func (p *endpointPool) GetInfobaseAuth(id uuid.UUID) (user, password string) {
	return p.getAuth(p.authInfobaseIdx, id)
}

func (p *endpointPool) getAuth(idx map[uuid.UUID]struct{ user, password string }, id uuid.UUID) (user, password string) {
	if auth, ok := idx[id]; ok {
		user, password = auth.user, auth.password
		return
	}

	if auth, ok := idx[uuid.Nil]; ok {
		user, password = auth.user, auth.password
	}

	return
}

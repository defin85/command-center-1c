package pool

import (
	"context"

	"github.com/commandcenter1c/commandcenter/ras-client/messages"
	"github.com/commandcenter1c/commandcenter/ras-client/serialize/esig"
	uuid "github.com/satori/go.uuid"
)

// Get returns existed connection from the pool or creates a new one.
func (p *endpointPool) onRequest(ctx context.Context, endpoint *Endpoint, req messages.EndpointRequestMessage) error {
	if needAgentAuth(req) {
		err := p.setAgentAuth(ctx, endpoint)
		if err != nil {
			return err
		}
	}

	sig := req.Sig()
	if esig.IsNul(sig) {
		return nil
	}

	if esig.Equal(endpoint.sig, sig) {
		return p.updateAuthIfNeed(ctx, endpoint, sig.High(), sig.Low())
	}

	err := p.updateAuthIfNeed(ctx, endpoint, sig.High(), sig.Low())
	if err != nil {
		return err
	}

	endpoint.sig = sig

	return nil
}

func (p *endpointPool) updateAuthIfNeed(ctx context.Context, endpoint *Endpoint, clusterID, infobaseID uuid.UUID) error {
	if user, password := p.GetClusterAuth(clusterID); !endpoint.CheckClusterAuth(user, password) {
		err := p.updateClusterAuth(ctx, endpoint, clusterID, user, password)
		if err != nil {
			return err
		}
	}

	if user, password := p.GetInfobaseAuth(infobaseID); !endpoint.CheckInfobaseAuth(user, password) {
		err := p.updateInfobaseAuth(ctx, endpoint, clusterID, user, password)
		if err != nil {
			return err
		}
	}

	return nil
}

func (p *endpointPool) updateClusterAuth(ctx context.Context, endpoint *Endpoint, clusterID uuid.UUID, user, password string) error {
	authMessage := endpoint.newEndpointMessage(messages.ClusterAuthenticateRequest{
		ClusterID: clusterID,
		User:      user,
		Password:  password,
	})

	message, err := endpoint.sendRequest(ctx, authMessage)
	if err != nil {
		return err
	}

	switch err := message.Message.(type) {
	case *messages.EndpointMessageFailure:
		return err
	}

	endpoint.SetClusterAuth(user, password)

	return nil
}

func (p *endpointPool) setAgentAuth(ctx context.Context, endpoint *Endpoint) error {
	authMessage := endpoint.newEndpointMessage(messages.AuthenticateAgentRequest{
		User:     p.authAgent.user,
		Password: p.authAgent.password,
	})

	message, err := endpoint.sendRequest(ctx, authMessage)
	if err != nil {
		return err
	}

	switch err := message.Message.(type) {
	case *messages.EndpointMessageFailure:
		return err
	}

	return nil
}

func (p *endpointPool) updateInfobaseAuth(ctx context.Context, endpoint *Endpoint, clusterID uuid.UUID, user, password string) error {
	authMessage := endpoint.newEndpointMessage(messages.AuthenticateInfobaseRequest{
		ClusterID: clusterID,
		User:      user,
		Password:  password,
	})

	message, err := endpoint.sendRequest(ctx, authMessage)
	if err != nil {
		return err
	}

	switch err := message.Message.(type) {
	case *messages.EndpointMessageFailure:
		return err
	}

	endpoint.SetInfobaseAuth(user, password)

	return nil
}

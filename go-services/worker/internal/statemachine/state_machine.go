package statemachine

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/redis/go-redis/v9"
	"github.com/sony/gobreaker"
)

// ExtensionInstallStateMachine orchestrates extension installation workflow
type ExtensionInstallStateMachine struct {
	// Identity
	ID            string
	OperationID   string
	DatabaseID    string
	CorrelationID string

	// State
	State         InstallState
	mu            sync.RWMutex
	lastActivity  time.Time

	// Workflow data
	ClusterID     string
	InfobaseID    string
	ExtensionPath string
	ExtensionName string

	// Event integration (используем Task 1.1!)
	publisher   EventPublisher
	subscriber  EventSubscriber
	eventChan   chan *events.Envelope
	eventBuffer []*events.Envelope // Buffer for unexpected events

	// Circuit breakers for external services
	clusterServiceBreaker *gobreaker.CircuitBreaker
	batchServiceBreaker   *gobreaker.CircuitBreaker

	// Dependencies
	redisClient *redis.Client
	config      *Config

	// Compensation
	compensationStack []CompensationAction

	// Deduplication
	processedEvents map[string]bool

	// Control
	ctx    context.Context
	cancel context.CancelFunc
	closed bool
}

// CompensationAction represents a compensation action
type CompensationAction struct {
	Name   string
	Action func(context.Context) error
}

// NewStateMachine creates new state machine instance
func NewStateMachine(
	ctx context.Context,
	operationID, databaseID, correlationID string,
	publisher EventPublisher,
	subscriber EventSubscriber,
	redisClient *redis.Client,
	config *Config,
) (*ExtensionInstallStateMachine, error) {

	if publisher == nil {
		return nil, fmt.Errorf("publisher is required")
	}
	if subscriber == nil {
		return nil, fmt.Errorf("subscriber is required")
	}
	// redisClient is optional (for unit tests without persistence)
	if config == nil {
		config = DefaultConfig()
	}

	smCtx, cancel := context.WithCancel(ctx)

	// Create circuit breakers
	clusterBreaker, batchBreaker := createCircuitBreakers()

	sm := &ExtensionInstallStateMachine{
		ID:            fmt.Sprintf("sm-%s", correlationID),
		OperationID:   operationID,
		DatabaseID:    databaseID,
		CorrelationID: correlationID,
		State:         StateInit,
		lastActivity:  time.Now(),
		publisher:     publisher,
		subscriber:    subscriber,
		redisClient:   redisClient,
		config:        config,
		eventChan:     make(chan *events.Envelope, 100),
		eventBuffer:   make([]*events.Envelope, 0, 10),
		processedEvents: make(map[string]bool),
		compensationStack: make([]CompensationAction, 0),
		clusterServiceBreaker: clusterBreaker,
		batchServiceBreaker:   batchBreaker,
		ctx:           smCtx,
		cancel:        cancel,
	}

	return sm, nil
}

// Run executes the state machine main loop
func (sm *ExtensionInstallStateMachine) Run(ctx context.Context) error {
	defer sm.cancel()
	defer sm.Close()

	// Start event listener
	go sm.listenEvents(ctx)

	// Load state if exists (for recovery)
	if err := sm.loadState(ctx); err != nil {
		// Ignore error, start from Init
	}

	// Main state loop
	for !sm.State.IsFinal() {
		select {
		case <-ctx.Done():
			sm.saveState(ctx)
			return ctx.Err()
		default:
		}

		var err error
		switch sm.State {
		case StateInit:
			err = sm.handleInit(ctx)
		case StateJobsLocked:
			err = sm.handleJobsLocked(ctx)
		case StateSessionsClosed:
			err = sm.handleSessionsClosed(ctx)
		case StateExtensionInstalled:
			err = sm.handleExtensionInstalled(ctx)
		case StateCompensating:
			err = sm.executeCompensations(ctx)
		default:
			return fmt.Errorf("unknown state: %s", sm.State)
		}

		if err != nil {
			sm.transitionTo(StateCompensating)
		}
	}

	return nil
}

// transitionTo transitions to new state
func (sm *ExtensionInstallStateMachine) transitionTo(newState InstallState) error {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	if !CanTransition(sm.State, newState) {
		return fmt.Errorf("invalid transition from %s to %s", sm.State, newState)
	}

	oldState := sm.State
	sm.State = newState
	sm.lastActivity = time.Now()

	// Log transition
	fmt.Printf("[StateMachine] Transition: %s -> %s (correlation_id=%s)\n",
		oldState, newState, sm.CorrelationID)

	// Save state
	if err := sm.saveState(sm.ctx); err != nil {
		fmt.Printf("[StateMachine] Failed to save state: %v\n", err)
	}

	return nil
}

// Close closes state machine and releases resources
func (sm *ExtensionInstallStateMachine) Close() error {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	if sm.closed {
		return nil // Already closed
	}

	sm.cancel()
	sm.closed = true

	// Clear event buffer
	sm.eventBuffer = nil

	// Close channel safely
	select {
	case <-sm.eventChan:
	default:
		close(sm.eventChan)
	}

	return nil
}

// clearEventBuffer clears the event buffer (for cleanup)
func (sm *ExtensionInstallStateMachine) clearEventBuffer() {
	sm.mu.Lock()
	defer sm.mu.Unlock()
	sm.eventBuffer = sm.eventBuffer[:0]
}

// listenEvents listens for incoming events
func (sm *ExtensionInstallStateMachine) listenEvents(ctx context.Context) {
	// Subscribe to events for this correlation ID
	// Используем Subscriber из Task 1.1!
	handler := func(ctx context.Context, envelope *events.Envelope) error {
		if envelope.CorrelationID == sm.CorrelationID {
			select {
			case sm.eventChan <- envelope:
			case <-ctx.Done():
				return ctx.Err()
			}
		}
		return nil
	}

	// Subscribe to orchestrator events
	sm.subscriber.Subscribe("events:orchestrator:*", handler)

	// Wait for context cancellation to prevent goroutine leak
	<-ctx.Done()
}

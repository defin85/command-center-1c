package statemachine

// InstallState represents the current state of extension installation workflow
type InstallState string

const (
	StateInit               InstallState = "init"
	StateJobsLocked         InstallState = "jobs_locked"
	StateSessionsClosed     InstallState = "sessions_closed"
	StateExtensionInstalled InstallState = "extension_installed"
	StateCompleted          InstallState = "completed"
	StateFailed             InstallState = "failed"
	StateCompensating       InstallState = "compensating"
)

// ValidTransitions defines allowed state transitions
var ValidTransitions = map[InstallState][]InstallState{
	StateInit: {StateJobsLocked, StateFailed},
	StateJobsLocked: {StateSessionsClosed, StateCompensating, StateFailed},
	StateSessionsClosed: {StateExtensionInstalled, StateCompensating, StateFailed},
	StateExtensionInstalled: {StateCompleted, StateCompensating, StateFailed},
	StateCompensating: {StateFailed},
	StateFailed: {},
	StateCompleted: {},
}

// CanTransition checks if transition from current state to new state is valid
func CanTransition(from, to InstallState) bool {
	allowed, ok := ValidTransitions[from]
	if !ok {
		return false
	}
	for _, allowedState := range allowed {
		if allowedState == to {
			return true
		}
	}
	return false
}

// String returns string representation of state
func (s InstallState) String() string {
	return string(s)
}

// IsFinal returns true if state is final (completed or failed)
func (s InstallState) IsFinal() bool {
	return s == StateCompleted || s == StateFailed
}

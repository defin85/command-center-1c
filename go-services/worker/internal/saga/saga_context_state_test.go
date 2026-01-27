package saga

import (
	"context"
	"errors"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestNewSagaContext(t *testing.T) {
	ctx := NewSagaContext("test-saga", "exec-1", "corr-1")

	assert.Equal(t, "test-saga", ctx.SagaID)
	assert.Equal(t, "exec-1", ctx.ExecutionID)
	assert.Equal(t, "corr-1", ctx.CorrelationID)
	assert.Equal(t, SagaStatusPending, ctx.Status)
	assert.NotNil(t, ctx.Variables)
}

func TestSagaContextVariables(t *testing.T) {
	ctx := NewSagaContext("test-saga", "exec-1", "corr-1")

	// Test Set and Get
	ctx.Set("key1", "value1")
	val, ok := ctx.Get("key1")
	assert.True(t, ok)
	assert.Equal(t, "value1", val)

	// Test GetString
	ctx.Set("string_key", "hello")
	assert.Equal(t, "hello", ctx.GetString("string_key"))
	assert.Equal(t, "", ctx.GetString("nonexistent"))

	// Test GetBool
	ctx.Set("bool_key", true)
	assert.True(t, ctx.GetBool("bool_key"))
	assert.False(t, ctx.GetBool("nonexistent"))

	// Test GetStringSlice
	ctx.Set("slice_key", []string{"a", "b", "c"})
	slice := ctx.GetStringSlice("slice_key")
	assert.Equal(t, []string{"a", "b", "c"}, slice)

	// Test GetStringSlice with []interface{}
	ctx.Set("interface_slice", []interface{}{"x", "y", "z"})
	slice2 := ctx.GetStringSlice("interface_slice")
	assert.Equal(t, []string{"x", "y", "z"}, slice2)
}

func TestSagaContextClone(t *testing.T) {
	ctx := NewSagaContext("test-saga", "exec-1", "corr-1")
	ctx.Set("key", "value")
	ctx.DatabaseIDs = []string{"db-1", "db-2"}
	ctx.CurrentStep = 5
	ctx.Status = SagaStatusRunning

	clone := ctx.Clone()

	// Verify clone has same values
	assert.Equal(t, ctx.SagaID, clone.SagaID)
	assert.Equal(t, ctx.ExecutionID, clone.ExecutionID)
	assert.Equal(t, ctx.CurrentStep, clone.CurrentStep)
	assert.Equal(t, ctx.Status, clone.Status)

	// Verify independence
	clone.Set("key", "new_value")
	assert.Equal(t, "value", ctx.GetString("key"))
	assert.Equal(t, "new_value", clone.GetString("key"))

	clone.DatabaseIDs[0] = "modified"
	assert.Equal(t, "db-1", ctx.DatabaseIDs[0])
}

func TestSagaDefinitionValidation(t *testing.T) {
	tests := []struct {
		name    string
		saga    *SagaDefinition
		wantErr bool
	}{
		{
			name:    "empty ID",
			saga:    &SagaDefinition{},
			wantErr: true,
		},
		{
			name:    "no steps",
			saga:    &SagaDefinition{ID: "test"},
			wantErr: true,
		},
		{
			name: "step without ID",
			saga: &SagaDefinition{
				ID: "test",
				Steps: []*Step{
					{Execute: func(ctx context.Context, sagaCtx *SagaContext) error { return nil }},
				},
			},
			wantErr: true,
		},
		{
			name: "step without Execute",
			saga: &SagaDefinition{
				ID: "test",
				Steps: []*Step{
					{ID: "step1"},
				},
			},
			wantErr: true,
		},
		{
			name: "duplicate step IDs",
			saga: &SagaDefinition{
				ID: "test",
				Steps: []*Step{
					{ID: "step1", Execute: func(ctx context.Context, sagaCtx *SagaContext) error { return nil }},
					{ID: "step1", Execute: func(ctx context.Context, sagaCtx *SagaContext) error { return nil }},
				},
			},
			wantErr: true,
		},
		{
			name: "valid saga",
			saga: &SagaDefinition{
				ID:   "test",
				Name: "Test Saga",
				Steps: []*Step{
					{
						ID:      "step1",
						Name:    "Step 1",
						Execute: func(ctx context.Context, sagaCtx *SagaContext) error { return nil },
					},
					{
						ID:      "step2",
						Name:    "Step 2",
						Execute: func(ctx context.Context, sagaCtx *SagaContext) error { return nil },
					},
				},
			},
			wantErr: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.saga.Validate()
			if tt.wantErr {
				assert.Error(t, err)
			} else {
				assert.NoError(t, err)
			}
		})
	}
}

func TestSagaState(t *testing.T) {
	state := NewSagaState("exec-1", "saga-1", "corr-1")

	assert.Equal(t, SagaStatusPending, state.Status)
	assert.Empty(t, state.CompletedSteps)
	assert.Empty(t, state.CompensationStack)

	// Test AddCompletedStep
	state.AddCompletedStep("step1", true)
	assert.Equal(t, []string{"step1"}, state.CompletedSteps)
	assert.Equal(t, []string{"step1"}, state.CompensationStack)

	state.AddCompletedStep("step2", false) // No compensation
	assert.Equal(t, []string{"step1", "step2"}, state.CompletedSteps)
	assert.Equal(t, []string{"step1"}, state.CompensationStack) // step2 not added

	state.AddCompletedStep("step3", true)
	assert.Equal(t, []string{"step1", "step3"}, state.CompensationStack)

	// Test PopCompensationStep (LIFO order)
	stepID, ok := state.PopCompensationStep()
	assert.True(t, ok)
	assert.Equal(t, "step3", stepID)

	stepID, ok = state.PopCompensationStep()
	assert.True(t, ok)
	assert.Equal(t, "step1", stepID)

	stepID, ok = state.PopCompensationStep()
	assert.False(t, ok)
	assert.Empty(t, stepID)
}

func TestSagaStateStatusTransitions(t *testing.T) {
	state := NewSagaState("exec-1", "saga-1", "corr-1")

	// Test SetCompleted
	state.SetCompleted()
	assert.Equal(t, SagaStatusCompleted, state.Status)
	assert.NotNil(t, state.CompletedAt)

	// Reset for next test
	state = NewSagaState("exec-2", "saga-1", "corr-1")

	// Test SetFailed
	state.SetFailed(errors.New("test error"))
	assert.Equal(t, SagaStatusFailed, state.Status)
	assert.Equal(t, "test error", state.Error)
	assert.NotNil(t, state.CompletedAt)

	// Reset for compensation test
	state = NewSagaState("exec-3", "saga-1", "corr-1")
	state.AddCompletedStep("step1", true)

	// Test SetCompensating
	state.SetCompensating()
	assert.Equal(t, SagaStatusCompensating, state.Status)

	// Test SetCompensated with all success
	results := []CompensationResult{
		{StepID: "step1", Success: true},
	}
	state.SetCompensated(results)
	assert.Equal(t, SagaStatusCompensated, state.Status)

	// Test SetCompensated with partial failure
	state = NewSagaState("exec-4", "saga-1", "corr-1")
	state.AddCompletedStep("step1", true)
	state.AddCompletedStep("step2", true)
	state.SetCompensating()

	results = []CompensationResult{
		{StepID: "step2", Success: true},
		{StepID: "step1", Success: false, Error: "compensation failed"},
	}
	state.SetCompensated(results)
	assert.Equal(t, SagaStatusPartiallyCompensated, state.Status)
}

func TestSagaStateSerialization(t *testing.T) {
	state := NewSagaState("exec-1", "saga-1", "corr-1")
	state.Status = SagaStatusRunning
	state.CurrentStep = 2
	state.Variables["key1"] = "value1"
	state.Variables["key2"] = 42
	state.AddCompletedStep("step1", true)
	state.AddCompletedStep("step2", true)

	// Serialize
	data, err := state.ToJSON()
	require.NoError(t, err)

	// Deserialize
	restored, err := SagaStateFromJSON(data)
	require.NoError(t, err)

	assert.Equal(t, state.ExecutionID, restored.ExecutionID)
	assert.Equal(t, state.SagaID, restored.SagaID)
	assert.Equal(t, state.Status, restored.Status)
	assert.Equal(t, state.CurrentStep, restored.CurrentStep)
	assert.Equal(t, state.CompletedSteps, restored.CompletedSteps)
	assert.Equal(t, state.CompensationStack, restored.CompensationStack)
	assert.Equal(t, "value1", restored.Variables["key1"])
}

func TestSagaStatusIsFinal(t *testing.T) {
	assert.False(t, SagaStatusPending.IsFinal())
	assert.False(t, SagaStatusRunning.IsFinal())
	assert.False(t, SagaStatusCompensating.IsFinal())
	assert.True(t, SagaStatusCompleted.IsFinal())
	assert.True(t, SagaStatusFailed.IsFinal())
	assert.True(t, SagaStatusCompensated.IsFinal())
	assert.True(t, SagaStatusPartiallyCompensated.IsFinal())
}

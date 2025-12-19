package drivers

import (
	"context"
	"testing"

	"github.com/commandcenter1c/commandcenter/shared/models"
)

type dummyMeta struct{}

func (d dummyMeta) Name() string             { return "dummy-meta" }
func (d dummyMeta) OperationTypes() []string { return []string{"op.a"} }
func (d dummyMeta) Execute(context.Context, *models.OperationMessage) (*models.OperationResultV2, error) {
	return &models.OperationResultV2{Status: "completed"}, nil
}

type dummyDB struct{}

func (d dummyDB) Name() string             { return "dummy-db" }
func (d dummyDB) OperationTypes() []string { return []string{"op.b"} }
func (d dummyDB) Execute(context.Context, *models.OperationMessage, string) (models.DatabaseResultV2, error) {
	return models.DatabaseResultV2{Success: true}, nil
}

func TestRegistry_RegisterAndLookup(t *testing.T) {
	r := NewRegistry()
	if err := r.RegisterMeta(dummyMeta{}); err != nil {
		t.Fatalf("register meta: %v", err)
	}
	if err := r.RegisterDatabase(dummyDB{}); err != nil {
		t.Fatalf("register db: %v", err)
	}

	if _, ok := r.LookupMeta("op.a"); !ok {
		t.Fatalf("expected meta driver")
	}
	if _, ok := r.LookupDatabase("op.b"); !ok {
		t.Fatalf("expected db driver")
	}
	if _, ok := r.LookupMeta("missing"); ok {
		t.Fatalf("unexpected meta driver")
	}
	if _, ok := r.LookupDatabase("missing"); ok {
		t.Fatalf("unexpected db driver")
	}
}

func TestRegistry_DuplicateRegistration(t *testing.T) {
	r := NewRegistry()
	if err := r.RegisterMeta(dummyMeta{}); err != nil {
		t.Fatalf("register meta: %v", err)
	}
	if err := r.RegisterMeta(dummyMeta{}); err == nil {
		t.Fatalf("expected duplicate registration error")
	}
}

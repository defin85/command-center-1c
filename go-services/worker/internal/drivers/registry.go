package drivers

import (
	"context"
	"fmt"

	"github.com/commandcenter1c/commandcenter/shared/models"
)

type MetaDriver interface {
	Name() string
	OperationTypes() []string
	Execute(ctx context.Context, msg *models.OperationMessage) (*models.OperationResultV2, error)
}

type DatabaseDriver interface {
	Name() string
	OperationTypes() []string
	Execute(ctx context.Context, msg *models.OperationMessage, databaseID string) (models.DatabaseResultV2, error)
}

type Registry struct {
	meta map[string]MetaDriver
	db   map[string]DatabaseDriver
}

func NewRegistry() *Registry {
	return &Registry{
		meta: make(map[string]MetaDriver),
		db:   make(map[string]DatabaseDriver),
	}
}

func (r *Registry) RegisterMeta(driver MetaDriver) error {
	for _, t := range driver.OperationTypes() {
		if t == "" {
			continue
		}
		if _, exists := r.meta[t]; exists {
			return fmt.Errorf("meta driver already registered for operation_type=%q", t)
		}
		r.meta[t] = driver
	}
	return nil
}

func (r *Registry) RegisterDatabase(driver DatabaseDriver) error {
	for _, t := range driver.OperationTypes() {
		if t == "" {
			continue
		}
		if _, exists := r.db[t]; exists {
			return fmt.Errorf("database driver already registered for operation_type=%q", t)
		}
		r.db[t] = driver
	}
	return nil
}

func (r *Registry) LookupMeta(operationType string) (MetaDriver, bool) {
	d, ok := r.meta[operationType]
	return d, ok
}

func (r *Registry) LookupDatabase(operationType string) (DatabaseDriver, bool) {
	d, ok := r.db[operationType]
	return d, ok
}

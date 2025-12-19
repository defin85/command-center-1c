package drivers

import (
	"context"

	"github.com/commandcenter1c/commandcenter/shared/models"
)

type MetaFunc func(ctx context.Context, msg *models.OperationMessage) (*models.OperationResultV2, error)

type FuncMetaDriver struct {
	name           string
	operationTypes []string
	fn             MetaFunc
}

func NewFuncMetaDriver(name string, operationTypes []string, fn MetaFunc) *FuncMetaDriver {
	return &FuncMetaDriver{name: name, operationTypes: operationTypes, fn: fn}
}

func (d *FuncMetaDriver) Name() string { return d.name }
func (d *FuncMetaDriver) OperationTypes() []string {
	return append([]string(nil), d.operationTypes...)
}
func (d *FuncMetaDriver) Execute(ctx context.Context, msg *models.OperationMessage) (*models.OperationResultV2, error) {
	return d.fn(ctx, msg)
}

type DatabaseFunc func(ctx context.Context, msg *models.OperationMessage, databaseID string) (models.DatabaseResultV2, error)

type FuncDatabaseDriver struct {
	name           string
	operationTypes []string
	fn             DatabaseFunc
}

func NewFuncDatabaseDriver(name string, operationTypes []string, fn DatabaseFunc) *FuncDatabaseDriver {
	return &FuncDatabaseDriver{name: name, operationTypes: operationTypes, fn: fn}
}

func (d *FuncDatabaseDriver) Name() string { return d.name }
func (d *FuncDatabaseDriver) OperationTypes() []string {
	return append([]string(nil), d.operationTypes...)
}
func (d *FuncDatabaseDriver) Execute(ctx context.Context, msg *models.OperationMessage, databaseID string) (models.DatabaseResultV2, error) {
	return d.fn(ctx, msg, databaseID)
}

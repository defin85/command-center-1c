package service

import "fmt"

type ServiceError struct {
	Code    string
	Message string
	Err     error
}

func (e *ServiceError) Error() string {
	if e.Err != nil {
		return fmt.Sprintf("%s: %v", e.Message, e.Err)
	}
	return e.Message
}

func (e *ServiceError) Unwrap() error {
	return e.Err
}

var (
	ErrInvalidServer   = &ServiceError{Code: "INVALID_SERVER", Message: "invalid server address"}
	ErrGRPCUnavailable = &ServiceError{Code: "GRPC_UNAVAILABLE", Message: "gRPC service unavailable"}
	ErrClusterNotFound = &ServiceError{Code: "CLUSTER_NOT_FOUND", Message: "cluster not found"}
)

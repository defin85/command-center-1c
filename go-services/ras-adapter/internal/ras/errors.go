package ras

import "errors"

var (
	// ErrConnectionFailed indicates RAS server connection failure
	ErrConnectionFailed = errors.New("failed to connect to RAS server")

	// ErrTimeout indicates operation timeout
	ErrTimeout = errors.New("operation timeout")

	// ErrNotFound indicates requested resource not found
	ErrNotFound = errors.New("resource not found")

	// ErrAuthenticationFailed indicates cluster authentication failure
	ErrAuthenticationFailed = errors.New("cluster authentication failed")

	// ErrInvalidParams indicates invalid parameters
	ErrInvalidParams = errors.New("invalid parameters")

	// ErrTerminateFailed indicates session termination failure
	ErrTerminateFailed = errors.New("session termination failed")
)

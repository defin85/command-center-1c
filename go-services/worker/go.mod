module github.com/commandcenter1c/commandcenter/worker

go 1.24

require (
	github.com/commandcenter1c/commandcenter/shared v0.0.0
	github.com/redis/go-redis/v9 v9.14.0
)

require (
	github.com/cespare/xxhash/v2 v2.3.0 // indirect
	github.com/dgryski/go-rendezvous v0.0.0-20200823014737-9f7001d12a5f // indirect
	github.com/sirupsen/logrus v1.9.3 // indirect
	github.com/stretchr/testify v1.11.1 // indirect
	go.uber.org/multierr v1.10.0 // indirect
	go.uber.org/zap v1.27.0 // indirect
	golang.org/x/sys v0.35.0 // indirect
)

replace github.com/commandcenter1c/commandcenter/shared => ../shared

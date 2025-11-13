module github.com/commandcenter1c/commandcenter/tests/integration

go 1.24.0

require (
	github.com/ThreeDotsLabs/watermill v1.5.1
	github.com/commandcenter1c/commandcenter/shared v0.0.0
	github.com/commandcenter1c/commandcenter/worker v0.0.0
	github.com/redis/go-redis/v9 v9.16.0
	github.com/stretchr/testify v1.11.1
)

require (
	github.com/Rican7/retry v0.3.1 // indirect
	github.com/ThreeDotsLabs/watermill-redisstream v1.4.4 // indirect
	github.com/beorn7/perks v1.0.1 // indirect
	github.com/cespare/xxhash/v2 v2.3.0 // indirect
	github.com/davecgh/go-spew v1.1.1 // indirect
	github.com/dgryski/go-rendezvous v0.0.0-20200823014737-9f7001d12a5f // indirect
	github.com/golang/protobuf v1.5.4 // indirect
	github.com/google/uuid v1.6.0 // indirect
	github.com/lithammer/shortuuid/v3 v3.0.7 // indirect
	github.com/munnerz/goautoneg v0.0.0-20191010083416-a7dc8b61c822 // indirect
	github.com/oklog/ulid v1.3.1 // indirect
	github.com/pkg/errors v0.9.1 // indirect
	github.com/pmezard/go-difflib v1.0.0 // indirect
	github.com/prometheus/client_golang v1.23.0 // indirect
	github.com/prometheus/client_model v0.6.2 // indirect
	github.com/prometheus/common v0.65.0 // indirect
	github.com/prometheus/procfs v0.17.0 // indirect
	github.com/sony/gobreaker v1.0.0 // indirect
	github.com/vmihailenco/msgpack v4.0.4+incompatible // indirect
	golang.org/x/sys v0.35.0 // indirect
	google.golang.org/appengine v1.6.8 // indirect
	google.golang.org/protobuf v1.36.9 // indirect
	gopkg.in/yaml.v3 v3.0.1 // indirect
)

replace (
	github.com/commandcenter1c/commandcenter/cluster-service => ../../go-services/cluster-service
	github.com/commandcenter1c/commandcenter/shared => ../../go-services/shared
	github.com/commandcenter1c/commandcenter/worker => ../../go-services/worker
)

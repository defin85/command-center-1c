package models

import (
	"encoding/json"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// Cluster tests

func TestCluster_JSONMarshaling(t *testing.T) {
	cluster := Cluster{
		UUID: "cluster-uuid",
		Name: "Test Cluster",
		Host: "localhost",
		Port: 1545,
	}

	// Marshal
	data, err := json.Marshal(cluster)
	require.NoError(t, err)
	assert.Contains(t, string(data), "cluster-uuid")
	assert.Contains(t, string(data), "Test Cluster")

	// Unmarshal
	var decoded Cluster
	err = json.Unmarshal(data, &decoded)
	require.NoError(t, err)
	assert.Equal(t, cluster.UUID, decoded.UUID)
	assert.Equal(t, cluster.Name, decoded.Name)
	assert.Equal(t, cluster.Host, decoded.Host)
	assert.Equal(t, cluster.Port, decoded.Port)
}

func TestCluster_ZeroValues(t *testing.T) {
	cluster := Cluster{}

	assert.Equal(t, "", cluster.UUID)
	assert.Equal(t, "", cluster.Name)
	assert.Equal(t, "", cluster.Host)
	assert.Equal(t, int32(0), cluster.Port)
}

func TestClustersResponse_JSONMarshaling(t *testing.T) {
	response := ClustersResponse{
		Clusters: []Cluster{
			{UUID: "uuid1", Name: "Cluster 1", Host: "host1", Port: 1545},
			{UUID: "uuid2", Name: "Cluster 2", Host: "host2", Port: 1646},
		},
	}

	// Marshal
	data, err := json.Marshal(response)
	require.NoError(t, err)

	// Unmarshal
	var decoded ClustersResponse
	err = json.Unmarshal(data, &decoded)
	require.NoError(t, err)

	assert.Len(t, decoded.Clusters, 2)
	assert.Equal(t, "uuid1", decoded.Clusters[0].UUID)
}

func TestClustersResponse_Empty(t *testing.T) {
	response := ClustersResponse{
		Clusters: []Cluster{},
	}

	assert.Len(t, response.Clusters, 0)

	// Marshal
	data, err := json.Marshal(response)
	require.NoError(t, err)
	assert.Contains(t, string(data), "clusters")
}

// Infobase tests

func TestInfobase_JSONMarshaling(t *testing.T) {
	infobase := Infobase{
		UUID:     "ib-uuid",
		Name:     "Test Infobase",
		DBMS:     "PostgreSQL",
		DBServer: "localhost",
		DBName:   "testdb",
	}

	// Marshal
	data, err := json.Marshal(infobase)
	require.NoError(t, err)
	assert.Contains(t, string(data), "ib-uuid")
	assert.Contains(t, string(data), "PostgreSQL")

	// Unmarshal
	var decoded Infobase
	err = json.Unmarshal(data, &decoded)
	require.NoError(t, err)
	assert.Equal(t, infobase.UUID, decoded.UUID)
	assert.Equal(t, infobase.Name, decoded.Name)
	assert.Equal(t, infobase.DBMS, decoded.DBMS)
}

func TestInfobase_ZeroValues(t *testing.T) {
	infobase := Infobase{}

	assert.Equal(t, "", infobase.UUID)
	assert.Equal(t, "", infobase.Name)
	assert.Equal(t, "", infobase.DBMS)
	assert.Equal(t, "", infobase.DBServer)
	assert.Equal(t, "", infobase.DBName)
}

func TestInfobasesResponse_JSONMarshaling(t *testing.T) {
	response := InfobasesResponse{
		Infobases: []Infobase{
			{UUID: "uuid1", Name: "DB 1", DBMS: "PostgreSQL"},
			{UUID: "uuid2", Name: "DB 2", DBMS: "MSSQLServer"},
		},
	}

	// Marshal
	data, err := json.Marshal(response)
	require.NoError(t, err)

	// Unmarshal
	var decoded InfobasesResponse
	err = json.Unmarshal(data, &decoded)
	require.NoError(t, err)

	assert.Len(t, decoded.Infobases, 2)
	assert.Equal(t, "uuid1", decoded.Infobases[0].UUID)
	assert.Equal(t, "PostgreSQL", decoded.Infobases[0].DBMS)
}

func TestInfobasesResponse_Empty(t *testing.T) {
	response := InfobasesResponse{
		Infobases: []Infobase{},
	}

	assert.Len(t, response.Infobases, 0)

	// Marshal
	data, err := json.Marshal(response)
	require.NoError(t, err)
	assert.Contains(t, string(data), "infobases")
}

// Response models tests

func TestErrorResponse_JSONMarshaling(t *testing.T) {
	errResp := ErrorResponse{
		Error: "test error message",
	}

	// Marshal
	data, err := json.Marshal(errResp)
	require.NoError(t, err)
	assert.Contains(t, string(data), "test error message")

	// Unmarshal
	var decoded ErrorResponse
	err = json.Unmarshal(data, &decoded)
	require.NoError(t, err)
	assert.Equal(t, errResp.Error, decoded.Error)
}

func TestHealthResponse_JSONMarshaling(t *testing.T) {
	healthResp := HealthResponse{
		Status:  "healthy",
		Service: "cluster-service",
		Version: "1.0.0",
	}

	// Marshal
	data, err := json.Marshal(healthResp)
	require.NoError(t, err)
	assert.Contains(t, string(data), "healthy")
	assert.Contains(t, string(data), "cluster-service")

	// Unmarshal
	var decoded HealthResponse
	err = json.Unmarshal(data, &decoded)
	require.NoError(t, err)
	assert.Equal(t, healthResp.Status, decoded.Status)
	assert.Equal(t, healthResp.Service, decoded.Service)
	assert.Equal(t, healthResp.Version, decoded.Version)
}

func TestHealthResponse_ZeroValues(t *testing.T) {
	healthResp := HealthResponse{}

	assert.Equal(t, "", healthResp.Status)
	assert.Equal(t, "", healthResp.Service)
	assert.Equal(t, "", healthResp.Version)
}

// Table-driven tests для различных сценариев

func TestCluster_DifferentPortValues(t *testing.T) {
	tests := []struct {
		name string
		port int32
	}{
		{"standard port", 1545},
		{"alternative port", 1646},
		{"custom port", 8080},
		{"zero port", 0},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cluster := Cluster{
				UUID: "test-uuid",
				Name: "Test",
				Host: "localhost",
				Port: tt.port,
			}

			assert.Equal(t, tt.port, cluster.Port)

			// Проверяем JSON marshaling
			data, err := json.Marshal(cluster)
			require.NoError(t, err)

			var decoded Cluster
			err = json.Unmarshal(data, &decoded)
			require.NoError(t, err)
			assert.Equal(t, tt.port, decoded.Port)
		})
	}
}

func TestInfobase_DifferentDBMS(t *testing.T) {
	dbmsList := []string{"PostgreSQL", "MSSQLServer", "IBMDB2", "OracleDatabase", ""}

	for _, dbms := range dbmsList {
		t.Run("dbms_"+dbms, func(t *testing.T) {
			infobase := Infobase{
				UUID: "test-uuid",
				Name: "Test DB",
				DBMS: dbms,
			}

			assert.Equal(t, dbms, infobase.DBMS)
		})
	}
}

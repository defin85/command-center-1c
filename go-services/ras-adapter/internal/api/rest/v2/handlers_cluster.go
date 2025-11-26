package v2

import (
	"net/http"

	"github.com/gin-gonic/gin"
)

// Discovery Handlers

// ListClusters retrieves all clusters from RAS server
// @Summary      List clusters
// @Description  Get list of all 1C clusters from RAS server
// @Tags         Clusters
// @Accept       json
// @Produce      json
// @Param        server    query     string  true  "RAS server address (host:port)"
// @Success      200  {object}  ClustersResponse
// @Failure      400  {object}  ErrorResponse
// @Failure      500  {object}  ErrorResponse
// @Router       /list-clusters [get]
func ListClusters(svc ClusterService) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Query params
		server := c.Query("server")
		if server == "" {
			c.JSON(http.StatusBadRequest, ErrorResponse{
				Error: "server parameter is required (format: host:port)",
				Code:  "MISSING_PARAMETER",
			})
			return
		}

		// Call service layer
		clusters, err := svc.GetClusters(c.Request.Context(), server)
		if err != nil {
			c.JSON(http.StatusInternalServerError, ErrorResponse{
				Error:   "Failed to retrieve clusters",
				Details: err.Error(),
			})
			return
		}

		c.JSON(http.StatusOK, ClustersResponse{
			Clusters: clusters,
			Count:    len(clusters),
		})
	}
}

// GetCluster retrieves specific cluster by ID
// @Summary      Get cluster
// @Description  Get specific cluster by UUID
// @Tags         Clusters
// @Accept       json
// @Produce      json
// @Param        server      query     string  true  "RAS server address (host:port)"
// @Param        cluster_id  query     string  true  "Cluster UUID"
// @Success      200  {object}  ClusterResponse
// @Failure      400  {object}  ErrorResponse
// @Failure      404  {object}  ErrorResponse
// @Router       /get-cluster [get]
func GetCluster(svc ClusterService) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Query params validation
		clusterID := c.Query("cluster_id")
		server := c.Query("server")

		if clusterID == "" || server == "" {
			c.JSON(http.StatusBadRequest, ErrorResponse{
				Error: "cluster_id and server are required",
				Code:  "MISSING_PARAMETER",
			})
			return
		}

		if !isValidUUID(clusterID) {
			c.JSON(http.StatusBadRequest, ErrorResponse{
				Error: "cluster_id must be a valid UUID",
				Code:  "INVALID_UUID",
			})
			return
		}

		// Call service layer
		cluster, err := svc.GetClusterByID(c.Request.Context(), server, clusterID)
		if err != nil {
			c.JSON(http.StatusNotFound, ErrorResponse{
				Error:   "Cluster not found",
				Details: err.Error(),
			})
			return
		}

		c.JSON(http.StatusOK, ClusterResponse{
			Cluster: cluster,
		})
	}
}

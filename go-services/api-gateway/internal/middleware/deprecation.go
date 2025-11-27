package middleware

import "github.com/gin-gonic/gin"

// DeprecationWarning adds deprecation headers to indicate API version is deprecated
// Headers conform to RFC 8594 (The Sunset HTTP Header Field)
func DeprecationWarning(sunsetDate string) gin.HandlerFunc {
	return func(c *gin.Context) {
		// RFC 8594: Deprecation header indicates the resource is deprecated
		c.Header("Deprecation", "true")
		// RFC 8594: Sunset header indicates when the resource will become unavailable
		c.Header("Sunset", sunsetDate)
		// Link header pointing to the successor version
		c.Header("Link", `</api/v2>; rel="successor-version"`)
		c.Next()
	}
}

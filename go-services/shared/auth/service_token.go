package auth

import (
	"fmt"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

// ServiceClaims represents JWT claims for service-to-service authentication
// Compatible with Django Simple JWT by including user_id claim
type ServiceClaims struct {
	UserID  string `json:"user_id"` // Required by Django SimpleJWT
	Service string `json:"service"` // "worker", "api-gateway", etc.
	jwt.RegisteredClaims
}

// GenerateServiceToken generates a long-lived JWT token for service-to-service authentication
// This token is used by Worker to authenticate with Django Orchestrator
// Token includes user_id="service:worker" to be compatible with Django SimpleJWT
func (m *JWTManager) GenerateServiceToken(serviceName string, ttl time.Duration) (string, error) {
	now := time.Now()
	claims := ServiceClaims{
		UserID:  fmt.Sprintf("service:%s", serviceName), // Pseudo user_id for Django
		Service: serviceName,
		RegisteredClaims: jwt.RegisteredClaims{
			Subject:   serviceName,     // "worker"
			Issuer:    "commandcenter", // Static issuer for all services
			IssuedAt:  jwt.NewNumericDate(now),
			NotBefore: jwt.NewNumericDate(now),
			ExpiresAt: jwt.NewNumericDate(now.Add(ttl)), // Long TTL (e.g., 24h)
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	return token.SignedString([]byte(m.config.Secret))
}

// ValidateServiceToken validates a service JWT token and returns claims
func (m *JWTManager) ValidateServiceToken(tokenString string) (*ServiceClaims, error) {
	token, err := jwt.ParseWithClaims(
		tokenString,
		&ServiceClaims{},
		func(token *jwt.Token) (interface{}, error) {
			if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
				return nil, jwt.ErrSignatureInvalid
			}
			return []byte(m.config.Secret), nil
		},
	)

	if err != nil {
		return nil, err
	}

	if claims, ok := token.Claims.(*ServiceClaims); ok && token.Valid {
		return claims, nil
	}

	return nil, jwt.ErrTokenInvalidClaims
}

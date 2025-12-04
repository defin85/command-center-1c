package handlers

import (
	"fmt"
	"net/http"
	"net/url"
	"os"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/gorilla/websocket"
	"github.com/sirupsen/logrus"

	"github.com/commandcenter1c/commandcenter/shared/logger"
)

const (
	writeWait      = 10 * time.Second
	pongWait       = 60 * time.Second
	pingPeriod     = (pongWait * 9) / 10
	maxMessageSize = 512 * 1024
)

var wsUpgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin: func(r *http.Request) bool {
		return true // Allow all origins in development
	},
}

func getWsOrchestratorURL() string {
	url := os.Getenv("ORCHESTRATOR_URL")
	if url == "" {
		url = "http://localhost:8200"
	}
	return url
}

// WebSocketWorkflowProxy handles /ws/workflow/:execution_id/
func WebSocketWorkflowProxy(c *gin.Context) {
	executionID := c.Param("execution_id")
	if executionID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "execution_id is required"})
		return
	}
	upstreamPath := fmt.Sprintf("/ws/workflow/%s/", executionID)
	proxyWebSocket(c, upstreamPath)
}

// WebSocketServiceMeshProxy handles /ws/service-mesh/
func WebSocketServiceMeshProxy(c *gin.Context) {
	proxyWebSocket(c, "/ws/service-mesh/")
}

func proxyWebSocket(c *gin.Context, upstreamPath string) {
	log := logger.GetLogger()

	// Build upstream URL
	upstreamURL, err := buildUpstreamWsURL(upstreamPath, c.Request.URL.RawQuery)
	if err != nil {
		log.WithError(err).Error("Failed to build upstream URL")
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		return
	}

	// Upgrade client connection
	clientConn, err := wsUpgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		log.WithError(err).Error("Failed to upgrade client connection")
		return
	}
	defer clientConn.Close()

	// Connect to upstream
	upstreamConn, resp, err := websocket.DefaultDialer.Dial(upstreamURL, buildUpstreamHeaders(c))
	if err != nil {
		statusCode := 0
		if resp != nil {
			statusCode = resp.StatusCode
		}
		log.WithFields(logrus.Fields{
			"error":       err.Error(),
			"upstream":    upstreamURL,
			"status_code": statusCode,
		}).Error("Failed to connect to upstream")
		clientConn.WriteMessage(websocket.CloseMessage,
			websocket.FormatCloseMessage(websocket.CloseInternalServerErr, "upstream unavailable"))
		return
	}
	defer upstreamConn.Close()

	connectionID := fmt.Sprintf("%s-%d", c.ClientIP(), time.Now().UnixNano())
	log.WithFields(logrus.Fields{
		"connection_id": connectionID,
		"upstream":      upstreamURL,
		"remote":        c.ClientIP(),
	}).Info("WebSocket connection established")

	// Run bidirectional proxy
	runBidirectionalProxy(clientConn, upstreamConn, log)

	log.WithField("connection_id", connectionID).Info("WebSocket connection closed")
}

func runBidirectionalProxy(clientConn, upstreamConn *websocket.Conn, log *logrus.Logger) {
	var wg sync.WaitGroup
	done := make(chan struct{})
	var closeOnce sync.Once // Thread-safe close to prevent panic

	// Helper to safely close done channel
	closeDone := func() {
		closeOnce.Do(func() {
			close(done)
		})
	}

	clientConn.SetReadLimit(maxMessageSize)
	upstreamConn.SetReadLimit(maxMessageSize)

	clientConn.SetReadDeadline(time.Now().Add(pongWait))
	clientConn.SetPongHandler(func(string) error {
		clientConn.SetReadDeadline(time.Now().Add(pongWait))
		return nil
	})

	upstreamConn.SetReadDeadline(time.Now().Add(pongWait))
	upstreamConn.SetPongHandler(func(string) error {
		upstreamConn.SetReadDeadline(time.Now().Add(pongWait))
		return nil
	})

	// Client -> Upstream
	wg.Add(1)
	go func() {
		defer wg.Done()
		pumpMessages(clientConn, upstreamConn, "client->upstream", done, closeDone, log)
	}()

	// Upstream -> Client
	wg.Add(1)
	go func() {
		defer wg.Done()
		pumpMessages(upstreamConn, clientConn, "upstream->client", done, closeDone, log)
	}()

	// Ping ticker
	wg.Add(1)
	go func() {
		defer wg.Done()
		pingTicker(clientConn, done, closeDone)
	}()

	wg.Wait()
}

func pumpMessages(src, dst *websocket.Conn, direction string, done chan struct{}, closeDone func(), log *logrus.Logger) {
	defer closeDone() // Thread-safe signal to stop other goroutines

	for {
		select {
		case <-done:
			return
		default:
			messageType, message, err := src.ReadMessage()
			if err != nil {
				if websocket.IsUnexpectedCloseError(err,
					websocket.CloseGoingAway,
					websocket.CloseNormalClosure,
					websocket.CloseNoStatusReceived) {
					log.WithFields(logrus.Fields{
						"error":     err.Error(),
						"direction": direction,
					}).Debug("WebSocket read error")
				}
				return
			}

			dst.SetWriteDeadline(time.Now().Add(writeWait))
			if err := dst.WriteMessage(messageType, message); err != nil {
				log.WithFields(logrus.Fields{
					"error":     err.Error(),
					"direction": direction,
				}).Debug("WebSocket write error")
				return
			}
		}
	}
}

func pingTicker(conn *websocket.Conn, done chan struct{}, closeDone func()) {
	ticker := time.NewTicker(pingPeriod)
	defer ticker.Stop()

	for {
		select {
		case <-done:
			return
		case <-ticker.C:
			conn.SetWriteDeadline(time.Now().Add(writeWait))
			if err := conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				closeDone() // Signal other goroutines to stop
				return
			}
		}
	}
}

func buildUpstreamWsURL(path string, queryString string) (string, error) {
	baseURL, err := url.Parse(getWsOrchestratorURL())
	if err != nil {
		return "", err
	}

	scheme := "ws"
	if baseURL.Scheme == "https" {
		scheme = "wss"
	}

	wsURL := fmt.Sprintf("%s://%s%s", scheme, baseURL.Host, path)
	if queryString != "" {
		wsURL += "?" + queryString
	}
	return wsURL, nil
}

func buildUpstreamHeaders(c *gin.Context) http.Header {
	headers := http.Header{}

	// Forward X-Forwarded-For
	xff := c.GetHeader("X-Forwarded-For")
	if xff != "" {
		headers.Set("X-Forwarded-For", xff+", "+c.ClientIP())
	} else {
		headers.Set("X-Forwarded-For", c.ClientIP())
	}

	// Forward Authorization if present
	if auth := c.GetHeader("Authorization"); auth != "" {
		headers.Set("Authorization", auth)
	}

	return headers
}

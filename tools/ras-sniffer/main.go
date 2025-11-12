package main

import (
	"encoding/hex"
	"fmt"
	"io"
	"log"
	"net"
	"os"
	"strings"
	"sync"
	"time"
)

const (
	listenAddr = "localhost:1546" // Proxy listen address (rac.exe подключается сюда)
	targetAddr = "localhost:1545" // RAS Server address
)

var (
	logFile *os.File
	logMu   sync.Mutex
)

func main() {
	// Open log file
	var err error
	logFile, err = os.Create("ras-protocol-capture.log")
	if err != nil {
		log.Fatal(err)
	}
	defer logFile.Close()

	logMessage("RAS Protocol Proxy Sniffer started")
	logMessage(fmt.Sprintf("Listening on: %s", listenAddr))
	logMessage(fmt.Sprintf("Forwarding to: %s", targetAddr))
	logMessage("Usage: rac.exe cluster list localhost:1546")
	logMessage(strings.Repeat("=", 80))

	// Start TCP listener
	listener, err := net.Listen("tcp", listenAddr)
	if err != nil {
		log.Fatal(err)
	}
	defer listener.Close()

	log.Printf("Proxy listening on %s, forwarding to %s\n", listenAddr, targetAddr)
	log.Println("Waiting for rac.exe connection...")

	connectionID := 0
	for {
		clientConn, err := listener.Accept()
		if err != nil {
			log.Println("Accept error:", err)
			continue
		}

		connectionID++
		log.Printf("New connection #%d from %s\n", connectionID, clientConn.RemoteAddr())

		go handleConnection(clientConn, connectionID)
	}
}

func handleConnection(clientConn net.Conn, connID int) {
	defer clientConn.Close()

	// Connect to RAS Server
	serverConn, err := net.Dial("tcp", targetAddr)
	if err != nil {
		log.Printf("Connection #%d: Failed to connect to RAS: %v\n", connID, err)
		return
	}
	defer serverConn.Close()

	logMessage(fmt.Sprintf("\n[CONNECTION #%d ESTABLISHED] %s", connID, time.Now().Format("15:04:05.000")))
	logMessage(fmt.Sprintf("Client: %s -> Proxy: %s -> RAS: %s",
		clientConn.RemoteAddr(), listenAddr, targetAddr))

	// Bi-directional copy with logging
	var wg sync.WaitGroup
	wg.Add(2)

	// Client → Server (rac.exe → RAS)
	go func() {
		defer wg.Done()
		copyAndLog(clientConn, serverConn, connID, "CLIENT→SERVER")
	}()

	// Server → Client (RAS → rac.exe)
	go func() {
		defer wg.Done()
		copyAndLog(serverConn, clientConn, connID, "SERVER→CLIENT")
	}()

	wg.Wait()
	logMessage(fmt.Sprintf("[CONNECTION #%d CLOSED] %s\n", connID, time.Now().Format("15:04:05.000")))
}

func copyAndLog(src, dst net.Conn, connID int, direction string) {
	buf := make([]byte, 32*1024) // 32KB buffer
	packetNum := 0

	for {
		n, err := src.Read(buf)
		if err != nil {
			if err != io.EOF {
				log.Printf("Connection #%d %s read error: %v\n", connID, direction, err)
			}
			return
		}

		if n > 0 {
			packetNum++

			// Log packet
			logPacket(connID, direction, packetNum, buf[:n])

			// Forward to destination
			if _, err := dst.Write(buf[:n]); err != nil {
				log.Printf("Connection #%d %s write error: %v\n", connID, direction, err)
				return
			}
		}
	}
}

func logPacket(connID int, direction string, packetNum int, data []byte) {
	logMu.Lock()
	defer logMu.Unlock()

	timestamp := time.Now().Format("15:04:05.000")

	// Header
	msg := fmt.Sprintf("\n--- Packet #%d [Conn #%d] %s @ %s ---\n",
		packetNum, connID, direction, timestamp)
	msg += fmt.Sprintf("Length: %d bytes\n\n", len(data))

	// Hex dump с ASCII representation
	msg += "Offset  | Hex                                              | ASCII\n"
	msg += "--------|--------------------------------------------------|------------------\n"

	for i := 0; i < len(data); i += 16 {
		// Offset
		msg += fmt.Sprintf("%06x  | ", i)

		// Hex bytes
		hexPart := ""
		asciiPart := ""
		for j := 0; j < 16; j++ {
			if i+j < len(data) {
				b := data[i+j]
				hexPart += fmt.Sprintf("%02x ", b)

				// ASCII (printable или '.')
				if b >= 32 && b <= 126 {
					asciiPart += string(b)
				} else {
					asciiPart += "."
				}
			} else {
				hexPart += "   "
			}

			// Space after 8 bytes для readability
			if j == 7 {
				hexPart += " "
			}
		}

		msg += hexPart + "| " + asciiPart + "\n"
	}

	// Try to analyze packet structure
	msg += "\n[ANALYSIS]\n"
	msg += analyzePacket(data)
	msg += "\n" + strings.Repeat("=", 80) + "\n"

	// Write to log file
	logFile.WriteString(msg)
	logFile.Sync() // Force flush для real-time viewing

	// Also print to console (summary)
	fmt.Printf("[%s] Conn#%d %s: %d bytes\n", timestamp, connID, direction, len(data))
}

func analyzePacket(data []byte) string {
	if len(data) < 4 {
		return "Packet too small for analysis"
	}

	analysis := ""

	// Attempt to detect patterns
	// Header detection (based on existing ras-grpc-gw code patterns)
	if len(data) >= 8 {
		analysis += fmt.Sprintf("First 8 bytes (possible header): %s\n", hex.EncodeToString(data[:8]))
	}

	// Check for common strings (cluster, infobase, session IDs are UUIDs)
	analysis += fmt.Sprintf("Contains printable strings: %v\n", containsPrintable(data))

	// Length encoding detection
	if len(data) >= 4 {
		possibleLen1 := int(data[0]) | int(data[1])<<8 | int(data[2])<<16 | int(data[3])<<24
		possibleLen2 := int(data[0])<<24 | int(data[1])<<16 | int(data[2])<<8 | int(data[3])

		analysis += fmt.Sprintf("Possible length encoding (LE): %d\n", possibleLen1)
		analysis += fmt.Sprintf("Possible length encoding (BE): %d\n", possibleLen2)
	}

	// Look for UUID patterns (36 chars: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
	uuids := findUUIDs(data)
	if len(uuids) > 0 {
		analysis += fmt.Sprintf("Found UUIDs: %s\n", strings.Join(uuids, ", "))
	}

	// Look for string patterns
	strings := extractStrings(data, 4)
	if len(strings) > 0 {
		analysis += fmt.Sprintf("Extracted strings (min 4 chars): %v\n", strings)
	}

	return analysis
}

func containsPrintable(data []byte) bool {
	printable := 0
	for _, b := range data {
		if b >= 32 && b <= 126 {
			printable++
		}
	}
	return float64(printable)/float64(len(data)) > 0.3
}

func findUUIDs(data []byte) []string {
	var uuids []string
	str := string(data)

	// Simple UUID pattern search
	for i := 0; i < len(str)-35; i++ {
		if str[i+8] == '-' && str[i+13] == '-' && str[i+18] == '-' && str[i+23] == '-' {
			candidate := str[i : i+36]
			if isValidUUID(candidate) {
				uuids = append(uuids, candidate)
			}
		}
	}

	return uuids
}

func isValidUUID(s string) bool {
	if len(s) != 36 {
		return false
	}
	for i, c := range s {
		if i == 8 || i == 13 || i == 18 || i == 23 {
			if c != '-' {
				return false
			}
		} else {
			if !((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F')) {
				return false
			}
		}
	}
	return true
}

func extractStrings(data []byte, minLen int) []string {
	var result []string
	var current []byte

	for _, b := range data {
		if b >= 32 && b <= 126 { // Printable ASCII
			current = append(current, b)
		} else {
			if len(current) >= minLen {
				result = append(result, string(current))
			}
			current = nil
		}
	}

	if len(current) >= minLen {
		result = append(result, string(current))
	}

	return result
}

func logMessage(msg string) {
	logMu.Lock()
	defer logMu.Unlock()

	timestamp := time.Now().Format("2006-01-02 15:04:05.000")
	fullMsg := fmt.Sprintf("[%s] %s\n", timestamp, msg)

	logFile.WriteString(fullMsg)
	logFile.Sync()

	fmt.Print(fullMsg)
}

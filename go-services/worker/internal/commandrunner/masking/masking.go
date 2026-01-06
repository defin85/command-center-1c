package masking

import "strings"

const mask = "***"

var sensitivePrefixes = []string{
	"--db-pwd",
	"--db-password",
	"--password",
	"--target-database-password",
	"--target-db-password",
	"--target-db-pwd",
	"--secret",
	"--token",
	"--api-key",
}

func MaskArgs(args []string) []string {
	if len(args) == 0 {
		return nil
	}

	masked := make([]string, 0, len(args))
	idx := 0
	for idx < len(args) {
		token := strings.TrimSpace(args[idx])
		lowered := strings.ToLower(token)

		if strings.HasPrefix(token, "/P") && token != "/P***" && len(token) > 2 {
			masked = append(masked, "/P***")
			idx += 1
			continue
		}

		matched := ""
		for _, prefix := range sensitivePrefixes {
			if lowered == prefix || strings.HasPrefix(lowered, prefix+"=") {
				matched = prefix
				break
			}
		}

		if matched != "" {
			if eq := strings.Index(token, "="); eq >= 0 {
				masked = append(masked, token[:eq+1]+mask)
				idx += 1
				continue
			}

			masked = append(masked, token)
			if idx+1 < len(args) {
				masked = append(masked, mask)
				idx += 2
				continue
			}
			idx += 1
			continue
		}

		masked = append(masked, token)
		idx += 1
	}

	return masked
}

package ibcmdops

func stringSliceEqual(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

func normalizeIbcmdArgv(argv []string) []string {
	// Backward compatible alias:
	// Driver catalog IDs intentionally flatten "infobase config extension <cmd>"
	// into "infobase extension <cmd>". The real ibcmd CLI expects "config" here.
	if len(argv) >= 2 && argv[0] == "infobase" && argv[1] == "extension" {
		next := make([]string, 0, len(argv)+1)
		next = append(next, "infobase", "config")
		next = append(next, argv[1:]...)
		return next
	}
	return argv
}

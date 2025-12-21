package ibcmdops

import "testing"

func TestParseS3Path(t *testing.T) {
	bucket, key, err := parseS3Path("s3://my-bucket/path/to/file.dt")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if bucket != "my-bucket" {
		t.Fatalf("unexpected bucket: %s", bucket)
	}
	if key != "path/to/file.dt" {
		t.Fatalf("unexpected key: %s", key)
	}
}

func TestApplyPrefix(t *testing.T) {
	key := applyPrefix("prefix", "dir/file.dt")
	if key != "prefix/dir/file.dt" {
		t.Fatalf("unexpected key: %s", key)
	}
}

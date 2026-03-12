package ibcmdops

import (
	"context"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"github.com/commandcenter1c/commandcenter/shared/credentials"
	"github.com/commandcenter1c/commandcenter/shared/models"
)

func TestExtractDBConfigMissingFields(t *testing.T) {
	_, err := extractDBConfig(map[string]interface{}{}, &credentials.DatabaseCredentials{})
	if err == nil {
		t.Fatalf("expected error for missing fields")
	}
}

func TestBuildRequestIbcmdCliInjectsInfobaseAuthArgs(t *testing.T) {
	msg := &models.OperationMessage{
		OperationID:   "op-1",
		OperationType: "ibcmd_cli",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"argv":  []string{"infobase", "dump"},
				"stdin": "hello",
			},
		},
	}

	req, err := buildRequest(
		context.Background(),
		msg,
		"db-1",
		&credentials.DatabaseCredentials{
			DBMS:       "PostgreSQL",
			DBServer:   "localhost",
			DBName:     "testdb",
			DBUser:     "dbuser",
			DBPassword: "dbpass",
			IBUsername: "ibuser",
			IBPassword: "ibpass",
		},
		nil,
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if req == nil {
		t.Fatalf("expected request")
	}
	if req.Stdin != "hello" {
		t.Fatalf("expected stdin=hello, got %q", req.Stdin)
	}

	expected := []string{
		"infobase",
		"dump",
		"--dbms=PostgreSQL",
		"--db-server=localhost",
		"--db-name=testdb",
		"--db-user=dbuser",
		"--db-pwd=dbpass",
		"--user=ibuser",
		"--password=ibpass",
	}
	if !reflect.DeepEqual(req.Args, expected) {
		t.Fatalf("unexpected args: %#v", req.Args)
	}
	if len(req.RuntimeBindings) != 7 {
		t.Fatalf("expected 7 runtime bindings, got %#v", req.RuntimeBindings)
	}
	if req.RuntimeBindings[0]["target_ref"] != "flag:--dbms" || req.RuntimeBindings[0]["status"] != "applied" {
		t.Fatalf("unexpected runtime binding: %#v", req.RuntimeBindings[0])
	}
	if req.RuntimeBindings[5]["target_ref"] != "flag:--user" || req.RuntimeBindings[5]["status"] != "applied" {
		t.Fatalf("unexpected runtime binding: %#v", req.RuntimeBindings[5])
	}
	if req.RuntimeBindings[6]["target_ref"] != "flag:--password" || req.RuntimeBindings[6]["status"] != "applied" {
		t.Fatalf("unexpected runtime binding: %#v", req.RuntimeBindings[6])
	}
}

func TestBuildRequestIbcmdCliDerivesRemoteConnectionFromProfile(t *testing.T) {
	msg := &models.OperationMessage{
		OperationID:   "op-1",
		OperationType: "ibcmd_cli",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"argv":              []string{"infobase", "dump"},
				"connection_source": "database_profile",
			},
		},
	}

	req, err := buildRequest(
		context.Background(),
		msg,
		"db-1",
		&credentials.DatabaseCredentials{
			IBUsername: "ibuser",
			IBPassword: "ibpass",
			IbcmdConnection: &credentials.IbcmdConnectionProfile{
				Remote: "ssh://agent:1234",
			},
		},
		nil,
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	expected := []string{
		"infobase",
		"dump",
		"--remote=ssh://agent:1234",
		"--user=ibuser",
		"--password=ibpass",
	}
	if !reflect.DeepEqual(req.Args, expected) {
		t.Fatalf("unexpected args: %#v", req.Args)
	}
	if len(req.RuntimeBindings) != 4 {
		t.Fatalf("expected 4 runtime bindings, got %#v", req.RuntimeBindings)
	}
	if req.RuntimeBindings[0]["target_ref"] != "flag:--remote" || req.RuntimeBindings[0]["status"] != "applied" {
		t.Fatalf("unexpected runtime binding: %#v", req.RuntimeBindings[0])
	}
	if req.RuntimeBindings[1]["target_ref"] != "dbms_offline" || req.RuntimeBindings[1]["status"] != "skipped" {
		t.Fatalf("unexpected runtime binding: %#v", req.RuntimeBindings[1])
	}
	if req.RuntimeBindings[2]["target_ref"] != "flag:--user" || req.RuntimeBindings[2]["status"] != "applied" {
		t.Fatalf("unexpected runtime binding: %#v", req.RuntimeBindings[2])
	}
	if req.RuntimeBindings[3]["target_ref"] != "flag:--password" || req.RuntimeBindings[3]["status"] != "applied" {
		t.Fatalf("unexpected runtime binding: %#v", req.RuntimeBindings[3])
	}
}

func TestBuildRequestIbcmdCliDerivesOfflineConnectionFromProfileWithDbPath(t *testing.T) {
	msg := &models.OperationMessage{
		OperationID:   "op-1",
		OperationType: "ibcmd_cli",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"argv":              []string{"infobase", "dump"},
				"connection_source": "database_profile",
			},
		},
	}

	req, err := buildRequest(
		context.Background(),
		msg,
		"db-1",
		&credentials.DatabaseCredentials{
			IBUsername: "ibuser",
			IBPassword: "ibpass",
			IbcmdConnection: &credentials.IbcmdConnectionProfile{
				Offline: map[string]string{
					"config":  "C:\\config",
					"data":    "C:\\data",
					"db_path": "C:\\bases\\filebase",
				},
			},
		},
		nil,
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	expected := []string{
		"infobase",
		"dump",
		"--config=C:\\config",
		"--data=C:\\data",
		"--db-path=C:\\bases\\filebase",
		"--user=ibuser",
		"--password=ibpass",
	}
	if !reflect.DeepEqual(req.Args, expected) {
		t.Fatalf("unexpected args: %#v", req.Args)
	}
	if len(req.RuntimeBindings) != 6 {
		t.Fatalf("expected 6 runtime bindings, got %#v", req.RuntimeBindings)
	}
	if req.RuntimeBindings[0]["target_ref"] != "flag:--config" || req.RuntimeBindings[0]["status"] != "applied" {
		t.Fatalf("unexpected runtime binding: %#v", req.RuntimeBindings[0])
	}
	if req.RuntimeBindings[1]["target_ref"] != "flag:--data" || req.RuntimeBindings[1]["status"] != "applied" {
		t.Fatalf("unexpected runtime binding: %#v", req.RuntimeBindings[1])
	}
	if req.RuntimeBindings[2]["target_ref"] != "flag:--db-path" || req.RuntimeBindings[2]["status"] != "applied" {
		t.Fatalf("unexpected runtime binding: %#v", req.RuntimeBindings[2])
	}
	if req.RuntimeBindings[3]["target_ref"] != "dbms_offline" || req.RuntimeBindings[3]["status"] != "skipped" {
		t.Fatalf("unexpected runtime binding: %#v", req.RuntimeBindings[3])
	}
	if req.RuntimeBindings[4]["target_ref"] != "flag:--user" || req.RuntimeBindings[4]["status"] != "applied" {
		t.Fatalf("unexpected runtime binding: %#v", req.RuntimeBindings[4])
	}
	if req.RuntimeBindings[5]["target_ref"] != "flag:--password" || req.RuntimeBindings[5]["status"] != "applied" {
		t.Fatalf("unexpected runtime binding: %#v", req.RuntimeBindings[5])
	}
}

func TestBuildRequestIbcmdCliReplacesExistingInfobaseAuthArgs(t *testing.T) {
	msg := &models.OperationMessage{
		OperationID:   "op-1",
		OperationType: "ibcmd_cli",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"argv": []string{
					"infobase",
					"restore",
					"--user=old",
					"--password=old",
				},
			},
		},
	}

	req, err := buildRequest(
		context.Background(),
		msg,
		"db-1",
		&credentials.DatabaseCredentials{
			DBMS:       "PostgreSQL",
			DBServer:   "localhost",
			DBName:     "testdb",
			DBUser:     "dbuser",
			DBPassword: "dbpass",
			IBUsername: "ibuser",
			IBPassword: "ibpass",
		},
		nil,
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	expected := []string{
		"infobase",
		"restore",
		"--dbms=PostgreSQL",
		"--db-server=localhost",
		"--db-name=testdb",
		"--db-user=dbuser",
		"--db-pwd=dbpass",
		"--user=ibuser",
		"--password=ibpass",
	}
	if !reflect.DeepEqual(req.Args, expected) {
		t.Fatalf("unexpected args: %#v", req.Args)
	}
	if len(req.RuntimeBindings) != 7 {
		t.Fatalf("expected 7 runtime bindings, got %#v", req.RuntimeBindings)
	}
}

func TestBuildRequestIbcmdCliRecordsNormalizeAndInjectsInfobaseAuthArgsForExtensionsList(t *testing.T) {
	msg := &models.OperationMessage{
		OperationID:   "op-1",
		OperationType: "ibcmd_cli",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"command_id": "infobase.extension.list",
				"argv":       []string{"infobase", "extension", "list"},
			},
		},
	}

	req, err := buildRequest(
		context.Background(),
		msg,
		"db-1",
		&credentials.DatabaseCredentials{
			DBMS:       "PostgreSQL",
			DBServer:   "localhost",
			DBName:     "testdb",
			DBUser:     "dbuser",
			DBPassword: "dbpass",
			IBUsername: "ibuser",
			IBPassword: "ibpass",
		},
		nil,
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	expected := []string{
		"infobase",
		"config",
		"extension",
		"list",
		"--dbms=PostgreSQL",
		"--db-server=localhost",
		"--db-name=testdb",
		"--db-user=dbuser",
		"--db-pwd=dbpass",
		"--user=ibuser",
		"--password=ibpass",
	}
	if !reflect.DeepEqual(req.Args, expected) {
		t.Fatalf("unexpected args: %#v", req.Args)
	}
	if len(req.RuntimeBindings) != 8 {
		t.Fatalf("expected 8 runtime bindings, got %#v", req.RuntimeBindings)
	}
	if req.RuntimeBindings[0]["source_ref"] != "worker.normalizeIbcmdArgv" || req.RuntimeBindings[0]["status"] != "applied" {
		t.Fatalf("unexpected runtime binding: %#v", req.RuntimeBindings[0])
	}
	if req.RuntimeBindings[6]["target_ref"] != "flag:--user" || req.RuntimeBindings[6]["status"] != "applied" {
		t.Fatalf("unexpected runtime binding: %#v", req.RuntimeBindings[6])
	}
	if req.RuntimeBindings[7]["target_ref"] != "flag:--password" || req.RuntimeBindings[7]["status"] != "applied" {
		t.Fatalf("unexpected runtime binding: %#v", req.RuntimeBindings[7])
	}
	if req.Stdin != "" {
		t.Fatalf("unexpected stdin: %q", req.Stdin)
	}
}

func TestBuildRequestIbcmdCliServiceStrategyInjectsInfobaseAuthArgsForExtensionsList(t *testing.T) {
	msg := &models.OperationMessage{
		OperationID:   "op-1",
		OperationType: "ibcmd_cli",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"command_id": "infobase.extension.list",
				"argv":       []string{"infobase", "extension", "list"},
				"ib_auth":    map[string]interface{}{"strategy": "service"},
			},
		},
	}

	req, err := buildRequest(
		context.Background(),
		msg,
		"db-1",
		&credentials.DatabaseCredentials{
			DBMS:       "PostgreSQL",
			DBServer:   "localhost",
			DBName:     "testdb",
			DBUser:     "dbuser",
			DBPassword: "dbpass",
			IBUsername: "svc",
			IBPassword: "svcpwd",
		},
		nil,
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !strings.Contains(strings.Join(req.Args, " "), "--user=svc") {
		t.Fatalf("expected --user=svc in args, got %#v", req.Args)
	}
	if req.RuntimeBindings[6]["source_ref"] != "credentials.ib_service_mapping" {
		t.Fatalf("unexpected source_ref: %#v", req.RuntimeBindings[6])
	}
	if req.RuntimeBindings[7]["source_ref"] != "credentials.ib_service_mapping" {
		t.Fatalf("unexpected source_ref: %#v", req.RuntimeBindings[7])
	}
}

func TestBuildRequestIbcmdCliServiceStrategyInjectsInfobaseAuthArgsForExtensionUpdate(t *testing.T) {
	msg := &models.OperationMessage{
		OperationID:   "op-1",
		OperationType: "ibcmd_cli",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"command_id": "infobase.extension.update",
				"argv": []string{
					"infobase",
					"extension",
					"update",
					"--active=no",
					"--name=DemoExtension",
				},
				"ib_auth": map[string]interface{}{"strategy": "service"},
			},
		},
	}

	req, err := buildRequest(
		context.Background(),
		msg,
		"db-1",
		&credentials.DatabaseCredentials{
			DBMS:       "PostgreSQL",
			DBServer:   "localhost",
			DBName:     "testdb",
			DBUser:     "dbuser",
			DBPassword: "dbpass",
			IBUsername: "svc",
			IBPassword: "svcpwd",
		},
		nil,
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !strings.Contains(strings.Join(req.Args, " "), "--user=svc") {
		t.Fatalf("expected --user=svc in args, got %#v", req.Args)
	}
	if !strings.Contains(strings.Join(req.Args, " "), "--password=svcpwd") {
		t.Fatalf("expected --password=svcpwd in args, got %#v", req.Args)
	}

	findBinding := func(targetRef string) map[string]interface{} {
		for _, raw := range req.RuntimeBindings {
			if raw == nil {
				continue
			}
			if v, ok := raw["target_ref"]; ok && v == targetRef {
				return raw
			}
		}
		return nil
	}

	ibUser := findBinding("flag:--user")
	if ibUser == nil || ibUser["source_ref"] != "credentials.ib_service_mapping" || ibUser["status"] != "applied" {
		t.Fatalf("unexpected IB user binding: %#v", ibUser)
	}
	ibPwd := findBinding("flag:--password")
	if ibPwd == nil || ibPwd["source_ref"] != "credentials.ib_service_mapping" || ibPwd["status"] != "applied" {
		t.Fatalf("unexpected IB password binding: %#v", ibPwd)
	}
}

func TestBuildRequestIbcmdCliDbmsServiceStrategyUsesServiceMappingSourceRefForExtensionsList(t *testing.T) {
	msg := &models.OperationMessage{
		OperationID:   "op-1",
		OperationType: "ibcmd_cli",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"command_id": "infobase.extension.list",
				"argv":       []string{"infobase", "extension", "list"},
				"dbms_auth":  map[string]interface{}{"strategy": "service"},
			},
		},
	}

	req, err := buildRequest(
		context.Background(),
		msg,
		"db-1",
		&credentials.DatabaseCredentials{
			DBMS:       "PostgreSQL",
			DBServer:   "localhost",
			DBName:     "testdb",
			DBUser:     "svc_db",
			DBPassword: "svcpwd",
			IBUsername: "ibuser",
			IBPassword: "ibpass",
		},
		nil,
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if req == nil {
		t.Fatalf("expected request")
	}

	findBinding := func(targetRef string) map[string]interface{} {
		for _, raw := range req.RuntimeBindings {
			if raw == nil {
				continue
			}
			if v, ok := raw["target_ref"]; ok && v == targetRef {
				return raw
			}
		}
		return nil
	}

	dbUser := findBinding("flag:--db-user")
	if dbUser == nil {
		t.Fatalf("expected flag:--db-user binding, got %#v", req.RuntimeBindings)
	}
	if dbUser["source_ref"] != "credentials.db_service_mapping" {
		t.Fatalf("unexpected db user source_ref: %#v", dbUser)
	}

	dbPwd := findBinding("flag:--db-pwd")
	if dbPwd == nil {
		t.Fatalf("expected flag:--db-pwd binding, got %#v", req.RuntimeBindings)
	}
	if dbPwd["source_ref"] != "credentials.db_service_mapping" {
		t.Fatalf("unexpected db password source_ref: %#v", dbPwd)
	}
}

func TestBuildRequestIbcmdCliDbmsServiceStrategyUsesServiceMappingSourceRefForConfigGenerationID(t *testing.T) {
	msg := &models.OperationMessage{
		OperationID:   "op-1",
		OperationType: "ibcmd_cli",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"command_id": "infobase.config.generation-id",
				"argv":       []string{"infobase", "config", "generation-id"},
				"dbms_auth":  map[string]interface{}{"strategy": "service"},
			},
		},
	}

	req, err := buildRequest(
		context.Background(),
		msg,
		"db-1",
		&credentials.DatabaseCredentials{
			DBMS:       "PostgreSQL",
			DBServer:   "localhost",
			DBName:     "testdb",
			DBUser:     "svc_db",
			DBPassword: "svcpwd",
			IBUsername: "ibuser",
			IBPassword: "ibpass",
		},
		nil,
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if req == nil {
		t.Fatalf("expected request")
	}

	findBinding := func(targetRef string) map[string]interface{} {
		for _, raw := range req.RuntimeBindings {
			if raw == nil {
				continue
			}
			if v, ok := raw["target_ref"]; ok && v == targetRef {
				return raw
			}
		}
		return nil
	}

	dbUser := findBinding("flag:--db-user")
	if dbUser == nil {
		t.Fatalf("expected flag:--db-user binding, got %#v", req.RuntimeBindings)
	}
	if dbUser["source_ref"] != "credentials.db_service_mapping" {
		t.Fatalf("unexpected db user source_ref: %#v", dbUser)
	}

	dbPwd := findBinding("flag:--db-pwd")
	if dbPwd == nil {
		t.Fatalf("expected flag:--db-pwd binding, got %#v", req.RuntimeBindings)
	}
	if dbPwd["source_ref"] != "credentials.db_service_mapping" {
		t.Fatalf("unexpected db password source_ref: %#v", dbPwd)
	}
}

func TestBuildRequestIbcmdCliDbmsServiceStrategyFailsClosedOutsideAllowlist(t *testing.T) {
	msg := &models.OperationMessage{
		OperationID:   "op-1",
		OperationType: "ibcmd_cli",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"command_id": "infobase.dump",
				"argv":       []string{"infobase", "dump"},
				"dbms_auth":  map[string]interface{}{"strategy": "service"},
			},
		},
	}

	_, err := buildRequest(
		context.Background(),
		msg,
		"db-1",
		&credentials.DatabaseCredentials{
			DBMS:       "PostgreSQL",
			DBServer:   "localhost",
			DBName:     "testdb",
			DBUser:     "svc_db",
			DBPassword: "svcpwd",
			IBUsername: "ibuser",
			IBPassword: "ibpass",
		},
		nil,
	)
	if err == nil {
		t.Fatalf("expected error")
	}
}

func TestBuildRequestIbcmdCliConfigGenerationIDAllowsServiceDbmsAuth(t *testing.T) {
	msg := &models.OperationMessage{
		OperationID:   "op-1",
		OperationType: "ibcmd_cli",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"command_id": "infobase.config.generation-id",
				"argv":       []string{"infobase", "config", "generation-id"},
				"ib_auth":    map[string]interface{}{"strategy": "service"},
				"dbms_auth":  map[string]interface{}{"strategy": "service"},
			},
		},
	}

	req, err := buildRequest(
		context.Background(),
		msg,
		"db-1",
		&credentials.DatabaseCredentials{
			DBMS:       "PostgreSQL",
			DBServer:   "localhost",
			DBName:     "testdb",
			DBUser:     "svc_db",
			DBPassword: "svcpwd",
			IBUsername: "svc",
			IBPassword: "svcpass",
		},
		nil,
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if req == nil {
		t.Fatalf("expected request")
	}
	if !strings.Contains(strings.Join(req.Args, " "), "--user=svc") {
		t.Fatalf("expected service IB auth in args, got %#v", req.Args)
	}
	if !strings.Contains(strings.Join(req.Args, " "), "--db-user=svc_db") {
		t.Fatalf("expected service DB auth in args, got %#v", req.Args)
	}
}

func TestBuildRequestIbcmdCliConfigExportObjectsAllowsServiceDbmsAuth(t *testing.T) {
	store := &fakeStorage{
		prepareOutputPath:   "/tmp/configuration.zip",
		prepareArtifactPath: "s3://bucket/configuration.zip",
	}

	msg := &models.OperationMessage{
		OperationID:   "op-1",
		OperationType: "ibcmd_cli",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"command_id": "infobase.config.export.objects",
				"argv": []string{
					"infobase",
					"config",
					"export",
					"objects",
					"Configuration",
					"--archive",
					"--out",
					"business-configuration-profile/db-1/Configuration.zip",
				},
				"ib_auth":   map[string]interface{}{"strategy": "service"},
				"dbms_auth": map[string]interface{}{"strategy": "service"},
			},
		},
	}

	req, err := buildRequest(
		context.Background(),
		msg,
		"db-1",
		&credentials.DatabaseCredentials{
			DBMS:       "PostgreSQL",
			DBServer:   "localhost",
			DBName:     "testdb",
			DBUser:     "svc_db",
			DBPassword: "svcpwd",
			IBUsername: "svc",
			IBPassword: "svcpass",
		},
		store,
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if req == nil {
		t.Fatalf("expected request")
	}
	if req.ArtifactPath != "s3://bucket/configuration.zip" {
		t.Fatalf("expected artifact path, got %q", req.ArtifactPath)
	}
	if !strings.Contains(strings.Join(req.Args, " "), "--db-user=svc_db") {
		t.Fatalf("expected service DB auth in args, got %#v", req.Args)
	}
}

func TestBuildRequestIbcmdCliNoneStrategySkipsInfobaseAuth(t *testing.T) {
	msg := &models.OperationMessage{
		OperationID:   "op-1",
		OperationType: "ibcmd_cli",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"command_id": "infobase.extension.list",
				"argv":       []string{"infobase", "extension", "list"},
				"ib_auth":    map[string]interface{}{"strategy": "none"},
			},
		},
	}

	req, err := buildRequest(
		context.Background(),
		msg,
		"db-1",
		&credentials.DatabaseCredentials{
			DBMS:       "PostgreSQL",
			DBServer:   "localhost",
			DBName:     "testdb",
			DBUser:     "dbuser",
			DBPassword: "dbpass",
			IBUsername: "ibuser",
			IBPassword: "ibpass",
		},
		nil,
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if strings.Contains(strings.Join(req.Args, " "), "--user=") || strings.Contains(strings.Join(req.Args, " "), "--password=") {
		t.Fatalf("did not expect infobase auth flags in args: %#v", req.Args)
	}
	if len(req.RuntimeBindings) == 0 || req.RuntimeBindings[len(req.RuntimeBindings)-1]["reason"] != "strategy_none" {
		t.Fatalf("expected skipped binding with reason=strategy_none, got %#v", req.RuntimeBindings)
	}
}

func TestBuildRequestIbcmdCliRejectsEmptyArgv(t *testing.T) {
	msg := &models.OperationMessage{
		OperationID:   "op-1",
		OperationType: "ibcmd_cli",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"argv": []string{},
			},
		},
	}

	_, err := buildRequest(
		context.Background(),
		msg,
		"db-1",
		&credentials.DatabaseCredentials{IBUsername: "ibuser", IBPassword: "ibpass"},
		nil,
	)
	if err == nil {
		t.Fatalf("expected error")
	}
}

func TestBuildRequestIbcmdCliInfobaseDumpUsesStoragePrepareOutput(t *testing.T) {
	store := &fakeStorage{
		prepareOutputPath:   "/tmp/out.dt",
		prepareArtifactPath: "s3://bucket/out.dt",
	}

	msg := &models.OperationMessage{
		OperationID:   "op-1",
		OperationType: "ibcmd_cli",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"command_id": "infobase.dump",
				"argv": []string{
					"infobase",
					"dump",
					"--dbms=PostgreSQL",
					"--db-pwd=secret",
					"db-1/backup.dt",
				},
			},
		},
	}

	req, err := buildRequest(
		context.Background(),
		msg,
		"db-1",
		&credentials.DatabaseCredentials{
			DBServer:   "localhost",
			DBName:     "testdb",
			DBUser:     "dbuser",
			IBUsername: "ibuser",
			IBPassword: "ibpass",
		},
		store,
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if req == nil {
		t.Fatalf("expected request")
	}
	if req.ArtifactPath != "s3://bucket/out.dt" {
		t.Fatalf("expected artifact path, got %q", req.ArtifactPath)
	}
	if store.prepareRequestedPath != "db-1/backup.dt" {
		t.Fatalf("expected PrepareOutput requested path to match argv positional, got %q", store.prepareRequestedPath)
	}
	expected := []string{
		"infobase",
		"dump",
		"--db-server=localhost",
		"--db-name=testdb",
		"--db-user=dbuser",
		"--dbms=PostgreSQL",
		"--db-pwd=secret",
		"/tmp/out.dt",
		"--user=ibuser",
		"--password=ibpass",
	}
	if !reflect.DeepEqual(req.Args, expected) {
		t.Fatalf("unexpected args: %#v", req.Args)
	}
}

func TestBuildRequestIbcmdCliConfigExportObjectsUsesStoragePrepareOutput(t *testing.T) {
	store := &fakeStorage{
		prepareOutputPath:   "/tmp/configuration.zip",
		prepareArtifactPath: "s3://bucket/configuration.zip",
	}

	msg := &models.OperationMessage{
		OperationID:   "op-1",
		OperationType: "ibcmd_cli",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"command_id": "infobase.config.export.objects",
				"argv": []string{
					"infobase",
					"config",
					"export",
					"objects",
					"Configuration",
					"--archive",
					"--out",
					"business-configuration-profile/db-1/Configuration.zip",
				},
			},
		},
	}

	req, err := buildRequest(
		context.Background(),
		msg,
		"db-1",
		&credentials.DatabaseCredentials{
			DBMS:       "PostgreSQL",
			DBServer:   "localhost",
			DBName:     "testdb",
			DBUser:     "dbuser",
			DBPassword: "dbpass",
			IBUsername: "ibuser",
			IBPassword: "ibpass",
		},
		store,
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if req == nil {
		t.Fatalf("expected request")
	}
	if req.ArtifactPath != "s3://bucket/configuration.zip" {
		t.Fatalf("expected artifact path, got %q", req.ArtifactPath)
	}
	if req.OutputPath != "/tmp/configuration.zip" {
		t.Fatalf("expected output path, got %q", req.OutputPath)
	}
	if store.prepareRequestedPath != "business-configuration-profile/db-1/Configuration.zip" {
		t.Fatalf("expected PrepareOutput requested path, got %q", store.prepareRequestedPath)
	}
	if !reflect.DeepEqual(req.Args[:5], []string{
		"infobase",
		"config",
		"export",
		"objects",
		"Configuration",
	}) {
		t.Fatalf("unexpected command prefix: %#v", req.Args)
	}
	if !containsToken(req.Args, "--archive") {
		t.Fatalf("expected --archive in args: %#v", req.Args)
	}
	if !containsAdjacentTokens(req.Args, "--out", "/tmp/configuration.zip") {
		t.Fatalf("expected --out /tmp/configuration.zip in args: %#v", req.Args)
	}
}

func TestBuildRequestIbcmdCliInjectsOfflineDbmsArgsFromCredentials(t *testing.T) {
	msg := &models.OperationMessage{
		OperationID:   "op-1",
		OperationType: "ibcmd_cli",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"command_id": "infobase.extension.list",
				"argv": []string{
					"infobase",
					"extension",
					"list",
				},
			},
		},
	}

	req, err := buildRequest(
		context.Background(),
		msg,
		"db-1",
		&credentials.DatabaseCredentials{
			DBMS:       "PostgreSQL",
			DBServer:   "localhost",
			DBName:     "testdb",
			DBUser:     "dbuser",
			DBPassword: "dbpass",
			IBUsername: "ibuser",
			IBPassword: "ibpass",
		},
		nil,
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if req == nil {
		t.Fatalf("expected request")
	}

	expected := []string{
		"infobase",
		"config",
		"extension",
		"list",
		"--dbms=PostgreSQL",
		"--db-server=localhost",
		"--db-name=testdb",
		"--db-user=dbuser",
		"--db-pwd=dbpass",
		"--user=ibuser",
		"--password=ibpass",
	}
	if !reflect.DeepEqual(req.Args, expected) {
		t.Fatalf("unexpected args: %#v", req.Args)
	}
}

func TestBuildRequestIbcmdCliInfobaseRestoreUsesStorageResolveInput(t *testing.T) {
	cleanupCalled := false
	store := &fakeStorage{
		resolveInputCleanup:  func() { cleanupCalled = true },
		resolveInputResolved: "/tmp/input.dt",
	}

	msg := &models.OperationMessage{
		OperationID:   "op-1",
		OperationType: "ibcmd_cli",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"command_id": "infobase.restore",
				"argv": []string{
					"infobase",
					"restore",
					"--dbms=PostgreSQL",
					"--db-pwd=secret",
					"s3://bucket/db-1/input.dt",
				},
			},
		},
	}

	req, err := buildRequest(
		context.Background(),
		msg,
		"db-1",
		&credentials.DatabaseCredentials{
			DBServer:   "localhost",
			DBName:     "testdb",
			DBUser:     "dbuser",
			IBUsername: "ibuser",
			IBPassword: "ibpass",
		},
		store,
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if req == nil {
		t.Fatalf("expected request")
	}
	if store.resolveInputRequested != "s3://bucket/db-1/input.dt" {
		t.Fatalf("expected ResolveInput requested path, got %q", store.resolveInputRequested)
	}
	expected := []string{
		"infobase",
		"restore",
		"--db-server=localhost",
		"--db-name=testdb",
		"--db-user=dbuser",
		"--dbms=PostgreSQL",
		"--db-pwd=secret",
		"/tmp/input.dt",
		"--user=ibuser",
		"--password=ibpass",
	}
	if !reflect.DeepEqual(req.Args, expected) {
		t.Fatalf("unexpected args: %#v", req.Args)
	}

	if req.inputCleanup == nil {
		t.Fatalf("expected input cleanup")
	}
	req.inputCleanup()
	if !cleanupCalled {
		t.Fatalf("expected cleanup to be called")
	}
}

func TestBuildRequestIbcmdCliInfobaseDumpRejectsArtifactOutput(t *testing.T) {
	store := &fakeStorage{prepareOutputPath: "/tmp/out.dt", prepareArtifactPath: "s3://bucket/out.dt"}

	msg := &models.OperationMessage{
		OperationID:   "op-1",
		OperationType: "ibcmd_cli",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"command_id": "infobase.dump",
				"argv": []string{
					"infobase",
					"dump",
					"artifact://out.dt",
				},
			},
		},
	}

	_, err := buildRequest(
		context.Background(),
		msg,
		"db-1",
		&credentials.DatabaseCredentials{IBUsername: "ibuser", IBPassword: "ibpass"},
		store,
	)
	if err == nil {
		t.Fatalf("expected error")
	}
	if !strings.Contains(err.Error(), "artifact:// output is not supported") {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestResolveStoragePathRejectsTraversal(t *testing.T) {
	base := t.TempDir()
	_, err := resolveLocalPath(base, "../secret.txt")
	if err == nil {
		t.Fatalf("expected error for traversal path")
	}
}

func TestResolveOutputPathUsesStorageBase(t *testing.T) {
	base := t.TempDir()
	path, err := resolveLocalOutputPath("", base, "db-123", ".dt")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if filepath.Ext(path) != ".dt" {
		t.Fatalf("expected .dt extension, got %s", filepath.Ext(path))
	}

	if _, err := os.Stat(filepath.Dir(path)); err != nil {
		t.Fatalf("expected directory to exist: %v", err)
	}

	if path == base {
		t.Fatalf("expected output path to include filename")
	}
}

func containsToken(args []string, token string) bool {
	for _, item := range args {
		if item == token {
			return true
		}
	}
	return false
}

func containsAdjacentTokens(args []string, left string, right string) bool {
	for idx := 0; idx+1 < len(args); idx++ {
		if args[idx] == left && args[idx+1] == right {
			return true
		}
	}
	return false
}

// go-services/worker/internal/drivers/ibcmdops/driver.go
package ibcmdops

import (
	"context"
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"

	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/shared/credentials"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/shared/tracing"
	runnerartifacts "github.com/commandcenter1c/commandcenter/worker/internal/commandrunner/artifacts"
	cliutil "github.com/commandcenter1c/commandcenter/worker/internal/drivers/cli"
	"github.com/commandcenter1c/commandcenter/worker/internal/drivers/ibcmd"
	"github.com/commandcenter1c/commandcenter/worker/internal/drivers/ibsrv"
	"github.com/commandcenter1c/commandcenter/worker/internal/events"
)

const (
	defaultStoragePath = "./storage/ibcmd"
)

// Driver executes ibcmd operations via direct CLI.
type Driver struct {
	credsClient credentials.Fetcher
	timeline    tracing.TimelineRecorder
}

// NewDriver creates a new ibcmd driver.
func NewDriver(credsClient credentials.Fetcher, timeline tracing.TimelineRecorder) *Driver {
	if timeline == nil {
		timeline = tracing.NewNoopTimeline()
	}
	return &Driver{credsClient: credsClient, timeline: timeline}
}

func (d *Driver) Name() string { return "ibcmd" }

func (d *Driver) OperationTypes() []string {
	return []string{
		"ibcmd_backup",
		"ibcmd_restore",
		"ibcmd_replicate",
		"ibcmd_create",
		"ibcmd_load_cfg",
		"ibcmd_extension_update",
		"ibcmd_cli",
	}
}

func (d *Driver) Execute(ctx context.Context, msg *models.OperationMessage, databaseID string) (models.DatabaseResultV2, error) {
	start := time.Now()
	log := logger.GetLogger()
	workflowMetadata := events.WorkflowMetadataFromMessage(msg)

	eventBase := fmt.Sprintf("ibcmd.%s", msg.OperationType)
	d.timeline.Record(ctx, msg.OperationID, eventBase+".started", events.MergeMetadata(map[string]interface{}{
		"database_id": databaseID,
	}, workflowMetadata))

	if os.Getenv("USE_DIRECT_IBCMD") == "false" {
		return d.failResult(msg, databaseID, start, "direct ibcmd disabled (USE_DIRECT_IBCMD=false)", "IBCMD_DISABLED"), nil
	}

	if useIbsrv := extractBool(msg.Payload.Data, "use_ibsrv"); useIbsrv {
		if err := validateIbsrvAllowed(); err != nil {
			return d.failResult(msg, databaseID, start, err.Error(), "IBSRV_DISABLED"), nil
		}
	}

	exec, err := ibcmd.NewExecutorFromEnv()
	if err != nil {
		return d.failResult(msg, databaseID, start, fmt.Sprintf("ibcmd executor not configured: %v", err), "IBCMD_NOT_CONFIGURED"), nil
	}

	credsCtx := credentials.WithRequestedBy(ctx, strings.TrimSpace(msg.Metadata.CreatedBy))
	creds, err := d.fetchCredentials(credsCtx, databaseID)
	if err != nil {
		return d.failResult(msg, databaseID, start, fmt.Sprintf("failed to fetch credentials: %v", err), "CREDENTIALS_ERROR"), nil
	}
	if msg.OperationType == "ibcmd_cli" {
		username := strings.TrimSpace(creds.IBUsername)
		if username == "" {
			createdBy := strings.TrimSpace(msg.Metadata.CreatedBy)
			if createdBy == "" {
				createdBy = "unknown"
			}
			return d.failResult(
				msg,
				databaseID,
				start,
				fmt.Sprintf("infobase user mapping not configured for created_by=%s", createdBy),
				"CREDENTIALS_ERROR",
			), nil
		}
	}

	var agent *ibsrv.AgentProcess
	if extractBool(msg.Payload.Data, "use_ibsrv") {
		agentCfg, err := buildAgentConfig(msg.Payload.Data, creds)
		if err != nil {
			return d.failResult(msg, databaseID, start, err.Error(), "IBSRV_CONFIG_ERROR"), nil
		}
		agent, err = ibsrv.StartAgent(ctx, agentCfg)
		if err != nil {
			return d.failResult(msg, databaseID, start, err.Error(), "IBSRV_START_ERROR"), nil
		}
		defer agent.Stop(ctx, agentCfg.ShutdownTimeout)
	}

	store, err := newStorageFromEnv()
	if err != nil {
		return d.failResult(msg, databaseID, start, err.Error(), "STORAGE_ERROR"), nil
	}

	request, err := buildRequest(ctx, msg, databaseID, creds, store)
	if err != nil {
		return d.failResult(msg, databaseID, start, err.Error(), "VALIDATION_ERROR"), nil
	}

	cmdCtx := ctx
	if msg.ExecConfig.TimeoutSeconds > 0 {
		var cancel context.CancelFunc
		cmdCtx, cancel = context.WithTimeout(ctx, time.Duration(msg.ExecConfig.TimeoutSeconds)*time.Second)
		defer cancel()
	}

	externalStart := time.Now()
	d.timeline.Record(ctx, msg.OperationID, "external.ibcmd.started", events.MergeMetadata(map[string]interface{}{
		"database_id":    databaseID,
		"operation_type": msg.OperationType,
	}, workflowMetadata))

	if request.inputCleanup != nil {
		defer request.inputCleanup()
	}
	if request.outputCleanup != nil {
		defer request.outputCleanup()
	}

	res, err := exec.Execute(cmdCtx, request.Args, request.Stdin)
	if err == nil && request.outputFinalize != nil {
		if finalizeErr := request.outputFinalize(cmdCtx); finalizeErr != nil {
			err = finalizeErr
		}
	}

	externalDuration := time.Since(externalStart)
	if err != nil {
		log.Warn("ibcmd operation failed",
			zap.String("operation_id", msg.OperationID),
			zap.String("operation_type", msg.OperationType),
			zap.String("database_id", databaseID),
			zap.Error(err),
		)
		d.timeline.Record(ctx, msg.OperationID, "external.ibcmd.failed", events.MergeMetadata(map[string]interface{}{
			"database_id":    databaseID,
			"operation_type": msg.OperationType,
			"duration_ms":    externalDuration.Milliseconds(),
			"error":          err.Error(),
		}, workflowMetadata))
		return d.failResult(msg, databaseID, start, err.Error(), "IBCMD_ERROR"), nil
	}

	result := d.buildResult(msg, databaseID, start, res, request.ArtifactPath)

	d.timeline.Record(ctx, msg.OperationID, "external.ibcmd.finished", events.MergeMetadata(map[string]interface{}{
		"database_id":    databaseID,
		"operation_type": msg.OperationType,
		"duration_ms":    externalDuration.Milliseconds(),
		"exit_code":      result.Data["exit_code"],
	}, workflowMetadata))

	return result, nil
}

func (d *Driver) buildResult(msg *models.OperationMessage, databaseID string, start time.Time, res *ibcmd.ExecutionResult, artifactPath string) models.DatabaseResultV2 {
	duration := time.Since(start)
	eventBase := fmt.Sprintf("ibcmd.%s", msg.OperationType)

	data := map[string]interface{}{
		"duration_ms": duration.Milliseconds(),
	}
	if res != nil {
		data["exit_code"] = res.ExitCode
		data["stdout"] = res.Stdout
		data["stderr"] = res.Stderr
		data["stdout_truncated"] = res.StdoutTruncated
		data["stderr_truncated"] = res.StderrTruncated
		data["wait_delay_hit"] = res.WaitDelayHit
	}
	if artifactPath != "" {
		data["artifact_path"] = artifactPath
	}

	d.timeline.Record(context.Background(), msg.OperationID, eventBase+".completed", events.MergeMetadata(map[string]interface{}{
		"database_id": databaseID,
		"duration_ms": duration.Milliseconds(),
	}, events.WorkflowMetadataFromMessage(msg)))

	return models.DatabaseResultV2{
		DatabaseID: databaseID,
		Success:    true,
		Duration:   duration.Seconds(),
		Data:       data,
	}
}

func (d *Driver) failResult(msg *models.OperationMessage, databaseID string, start time.Time, message, code string) models.DatabaseResultV2 {
	duration := time.Since(start)
	eventBase := fmt.Sprintf("ibcmd.%s", msg.OperationType)
	d.timeline.Record(context.Background(), msg.OperationID, eventBase+".failed", events.MergeMetadata(map[string]interface{}{
		"database_id": databaseID,
		"error":       message,
		"duration_ms": duration.Milliseconds(),
	}, events.WorkflowMetadataFromMessage(msg)))
	return models.DatabaseResultV2{
		DatabaseID: databaseID,
		Success:    false,
		Error:      message,
		ErrorCode:  code,
		Duration:   duration.Seconds(),
	}
}

func (d *Driver) fetchCredentials(ctx context.Context, databaseID string) (*credentials.DatabaseCredentials, error) {
	if d.credsClient == nil {
		return nil, fmt.Errorf("credentials client not configured")
	}
	return d.credsClient.Fetch(ctx, databaseID)
}

func validateIbsrvAllowed() error {
	if os.Getenv("IBSRV_ENABLED") != "true" {
		return fmt.Errorf("ibsrv disabled (IBSRV_ENABLED != true)")
	}

	env := strings.ToLower(os.Getenv("APP_ENV"))
	if env == "" {
		env = strings.ToLower(os.Getenv("ENVIRONMENT"))
	}
	if env == "production" || env == "prod" {
		return fmt.Errorf("ibsrv is not allowed in production")
	}
	return nil
}

func buildAgentConfig(data map[string]interface{}, creds *credentials.DatabaseCredentials) (ibsrv.AgentConfig, error) {
	exePath, err := cliutil.Resolve1cv8PathFromEnv()
	if err != nil {
		return ibsrv.AgentConfig{}, err
	}

	server := ""
	if creds != nil {
		server = strings.TrimSpace(creds.ServerAddress)
		if creds.ServerPort > 0 {
			server = fmt.Sprintf("%s:%d", server, creds.ServerPort)
		}
	}
	if server == "" {
		return ibsrv.AgentConfig{}, fmt.Errorf("server address is required for agent mode")
	}

	infobase := ""
	if creds != nil {
		infobase = strings.TrimSpace(creds.InfobaseName)
		if infobase == "" {
			infobase = strings.TrimSpace(creds.BaseName)
		}
	}
	if infobase == "" {
		return ibsrv.AgentConfig{}, fmt.Errorf("infobase name is required for agent mode")
	}

	port := extractInt(data, "agent_port")
	listen := extractString(data, "agent_listen_address")
	baseDir := extractString(data, "agent_base_dir")
	hostKey := extractString(data, "agent_ssh_host_key")
	hostKeyAuto := extractBool(data, "agent_ssh_host_key_auto")
	if hostKey == "" && !hostKeyAuto {
		hostKeyAuto = true
	}

	startupTimeout := time.Duration(extractInt(data, "agent_startup_timeout_seconds")) * time.Second
	shutdownTimeout := time.Duration(extractInt(data, "agent_shutdown_timeout_seconds")) * time.Second

	return ibsrv.AgentConfig{
		ExecPath:        exePath,
		Server:          server,
		Infobase:        infobase,
		Username:        pickIBUsername(creds),
		Password:        pickIBPassword(creds),
		Port:            port,
		ListenAddress:   listen,
		SSHHostKeyPath:  hostKey,
		SSHHostKeyAuto:  hostKeyAuto,
		BaseDir:         baseDir,
		Visible:         extractBool(data, "agent_visible"),
		StartupTimeout:  startupTimeout,
		ShutdownTimeout: shutdownTimeout,
	}, nil
}

type ibcmdRequest struct {
	Args           []string
	Stdin          string
	ArtifactPath   string
	inputCleanup   func()
	outputCleanup  func()
	outputFinalize func(ctx context.Context) error
}

type dbConfig struct {
	DBMS       string
	DBServer   string
	DBName     string
	DBUser     string
	DBPassword string
	User       string
	Password   string
}

type replicateTargetConfig struct {
	DBMS       string
	DBServer   string
	DBName     string
	DBUser     string
	DBPassword string
}

func buildRequest(ctx context.Context, msg *models.OperationMessage, databaseID string, creds *credentials.DatabaseCredentials, store storage) (*ibcmdRequest, error) {
	data := msg.Payload.Data
	meta := runnerartifacts.Meta{
		Driver:      runnerartifacts.DriverIBCMD,
		OperationID: msg.OperationID,
		DatabaseID:  databaseID,
	}

	if msg.OperationType == "ibcmd_cli" {
		argv := extractStringSlice(data, "argv")
		if len(argv) == 0 {
			return nil, fmt.Errorf("argv is required")
		}

		resolvedArgs, cleanup, err := runnerartifacts.ResolveArgs(ctx, argv, meta)
		if err != nil {
			return nil, err
		}

		credsArgs := injectInfobaseAuthArgs(resolvedArgs, creds)
		return &ibcmdRequest{
			Args:         credsArgs,
			Stdin:        extractString(data, "stdin"),
			inputCleanup: cleanup,
		}, nil
	}

	if args := extractStringSlice(data, "args"); len(args) > 0 {
		resolvedArgs, cleanup, err := runnerartifacts.ResolveArgs(ctx, args, meta)
		if err != nil {
			return nil, err
		}
		return &ibcmdRequest{
			Args:         resolvedArgs,
			Stdin:        extractString(data, "stdin"),
			inputCleanup: cleanup,
		}, nil
	}

	cfg, err := extractDBConfig(data, creds)
	if err != nil {
		return nil, err
	}

	additionalArgs := extractStringSlice(data, "additional_args")

	switch msg.OperationType {
	case "ibcmd_load_cfg":
		filePath := extractString(data, "file")
		if filePath == "" {
			filePath = extractString(data, "file_path")
		}
		if strings.TrimSpace(filePath) == "" {
			return nil, fmt.Errorf("file is required")
		}

		resolvedFile, cleanup, err := runnerartifacts.ResolvePath(ctx, filePath, meta)
		if err != nil {
			return nil, err
		}

		args := append([]string{"infobase", "config", "load-cfg"}, buildDBArgs(cfg)...)
		args = append(args, fmt.Sprintf("--file=%s", resolvedFile))
		if ext := strings.TrimSpace(extractString(data, "extension")); ext != "" {
			args = append(args, fmt.Sprintf("--extension=%s", ext))
		}
		args = append(args, additionalArgs...)
		return &ibcmdRequest{
			Args:         args,
			Stdin:        extractString(data, "stdin"),
			inputCleanup: cleanup,
		}, nil
	case "ibcmd_extension_update":
		extName := strings.TrimSpace(extractString(data, "name"))
		if extName == "" {
			extName = strings.TrimSpace(extractString(data, "extension"))
		}
		if extName == "" {
			return nil, fmt.Errorf("name is required")
		}

		args := append([]string{"infobase", "extension", "update"}, buildDBArgs(cfg)...)
		args = append(args, fmt.Sprintf("--name=%s", extName))

		if flag, ok, err := extractYesNoOption(data, "active"); err != nil {
			return nil, err
		} else if ok {
			args = append(args, fmt.Sprintf("--active=%s", flag))
		}
		if flag, ok, err := extractYesNoOption(data, "safe_mode"); err != nil {
			return nil, err
		} else if ok {
			args = append(args, fmt.Sprintf("--safe-mode=%s", flag))
		}
		if scopeRaw, ok, err := extractEnumOption(data, "scope", []string{"infobase", "data-separation"}); err != nil {
			return nil, err
		} else if ok {
			args = append(args, fmt.Sprintf("--scope=%s", scopeRaw))
		}

		if profile := strings.TrimSpace(extractString(data, "security_profile_name")); profile != "" {
			args = append(args, fmt.Sprintf("--security-profile-name=%s", profile))
		}

		if flag, ok, err := extractYesNoOption(data, "unsafe_action_protection"); err != nil {
			return nil, err
		} else if ok {
			args = append(args, fmt.Sprintf("--unsafe-action-protection=%s", flag))
		}
		if flag, ok, err := extractYesNoOption(data, "used_in_distributed_infobase"); err != nil {
			return nil, err
		} else if ok {
			args = append(args, fmt.Sprintf("--used-in-distributed-infobase=%s", flag))
		}

		args = append(args, additionalArgs...)
		return &ibcmdRequest{
			Args:  args,
			Stdin: extractString(data, "stdin"),
		}, nil
	case "ibcmd_backup":
		requestedPath := extractString(data, "output_path")
		outputPath, artifactPath, finalize, cleanup, err := store.PrepareOutput(ctx, requestedPath, databaseID, ".dt")
		if err != nil {
			return nil, err
		}
		args := append([]string{"infobase", "dump"}, buildDBArgs(cfg)...)
		args = append(args, outputPath)
		args = append(args, additionalArgs...)
		return &ibcmdRequest{
			Args:           args,
			Stdin:          extractString(data, "stdin"),
			ArtifactPath:   artifactPath,
			outputCleanup:  cleanup,
			outputFinalize: finalize,
		}, nil
	case "ibcmd_restore":
		inputPath := extractString(data, "input_path")
		if inputPath == "" {
			inputPath = extractString(data, "backup_path")
		}
		if inputPath == "" {
			return nil, fmt.Errorf("input_path is required")
		}
		resolvedInput, cleanup, err := store.ResolveInput(ctx, inputPath)
		if err != nil {
			return nil, err
		}
		args := append([]string{"infobase", "restore"}, buildDBArgs(cfg)...)
		if extractBool(data, "create_database") {
			args = append(args, "--create-database")
		}
		if extractBool(data, "force") {
			args = append(args, "--force")
		}
		args = append(args, resolvedInput)
		args = append(args, additionalArgs...)
		return &ibcmdRequest{
			Args:         args,
			Stdin:        extractString(data, "stdin"),
			inputCleanup: cleanup,
		}, nil
	case "ibcmd_replicate":
		targetCfg, err := extractReplicateTargetConfig(data)
		if err != nil {
			return nil, err
		}
		args := append([]string{"infobase", "replicate"}, buildDBArgs(cfg)...)
		args = append(args, buildTargetArgs(targetCfg)...)
		if jobs := extractInt(data, "jobs_count"); jobs > 0 {
			args = append(args, fmt.Sprintf("--jobs-count=%d", jobs))
		}
		if jobs := extractInt(data, "target_jobs_count"); jobs > 0 {
			args = append(args, fmt.Sprintf("--target-jobs-count=%d", jobs))
		}
		args = append(args, additionalArgs...)
		return &ibcmdRequest{Args: args, Stdin: extractString(data, "stdin")}, nil
	case "ibcmd_create":
		args := append([]string{"infobase", "create"}, buildDBArgs(cfg)...)
		args = append(args, additionalArgs...)
		return &ibcmdRequest{Args: args, Stdin: extractString(data, "stdin")}, nil
	default:
		return nil, fmt.Errorf("unsupported operation type: %s", msg.OperationType)
	}
}

func buildDBArgs(cfg dbConfig) []string {
	args := []string{
		fmt.Sprintf("--dbms=%s", cfg.DBMS),
		fmt.Sprintf("--db-server=%s", cfg.DBServer),
		fmt.Sprintf("--db-name=%s", cfg.DBName),
		fmt.Sprintf("--db-user=%s", cfg.DBUser),
		fmt.Sprintf("--db-pwd=%s", cfg.DBPassword),
	}
	if cfg.User != "" {
		args = append(args, fmt.Sprintf("--user=%s", cfg.User))
	}
	if cfg.Password != "" {
		args = append(args, fmt.Sprintf("--password=%s", cfg.Password))
	}
	return args
}

func buildTargetArgs(cfg replicateTargetConfig) []string {
	return []string{
		fmt.Sprintf("--target-dbms=%s", cfg.DBMS),
		fmt.Sprintf("--target-database-server=%s", cfg.DBServer),
		fmt.Sprintf("--target-database-name=%s", cfg.DBName),
		fmt.Sprintf("--target-database-user=%s", cfg.DBUser),
		fmt.Sprintf("--target-database-password=%s", cfg.DBPassword),
	}
}

func extractDBConfig(data map[string]interface{}, creds *credentials.DatabaseCredentials) (dbConfig, error) {
	cfg := dbConfig{
		DBMS:       extractString(data, "dbms"),
		DBServer:   extractString(data, "db_server"),
		DBName:     extractString(data, "db_name"),
		DBUser:     extractString(data, "db_user"),
		DBPassword: extractString(data, "db_password"),
		User:       extractString(data, "user"),
		Password:   extractString(data, "password"),
	}

	if cfg.User == "" && creds != nil {
		cfg.User = pickIBUsername(creds)
	}
	if cfg.Password == "" && creds != nil {
		cfg.Password = pickIBPassword(creds)
	}

	missing := []string{}
	if cfg.DBMS == "" {
		missing = append(missing, "dbms")
	}
	if cfg.DBServer == "" {
		missing = append(missing, "db_server")
	}
	if cfg.DBName == "" {
		missing = append(missing, "db_name")
	}
	if cfg.DBUser == "" {
		missing = append(missing, "db_user")
	}
	if cfg.DBPassword == "" {
		missing = append(missing, "db_password")
	}
	if len(missing) > 0 {
		return dbConfig{}, fmt.Errorf("missing required fields: %s", strings.Join(missing, ", "))
	}

	return cfg, nil
}

func pickIBUsername(creds *credentials.DatabaseCredentials) string {
	if creds == nil {
		return ""
	}
	return strings.TrimSpace(creds.IBUsername)
}

func pickIBPassword(creds *credentials.DatabaseCredentials) string {
	if creds == nil {
		return ""
	}
	return strings.TrimSpace(creds.IBPassword)
}

func injectInfobaseAuthArgs(args []string, creds *credentials.DatabaseCredentials) []string {
	if len(args) == 0 {
		return args
	}

	cleaned := stripInfobaseAuthArgs(args)
	if creds == nil {
		return cleaned
	}

	username := strings.TrimSpace(creds.IBUsername)
	if username == "" {
		return cleaned
	}
	password := strings.TrimSpace(creds.IBPassword)

	cleaned = append(cleaned, fmt.Sprintf("--user=%s", username))
	cleaned = append(cleaned, fmt.Sprintf("--password=%s", password))
	return cleaned
}

func stripInfobaseAuthArgs(args []string) []string {
	if len(args) == 0 {
		return args
	}

	result := make([]string, 0, len(args))
	skipNext := false
	for _, raw := range args {
		token := strings.TrimSpace(raw)
		if token == "" {
			continue
		}
		if skipNext {
			skipNext = false
			continue
		}

		lowered := strings.ToLower(token)
		if strings.HasPrefix(lowered, "--user") || strings.HasPrefix(lowered, "--password") {
			if strings.Contains(token, "=") {
				continue
			}
			skipNext = true
			continue
		}
		result = append(result, token)
	}

	return result
}

func extractReplicateTargetConfig(data map[string]interface{}) (replicateTargetConfig, error) {
	cfg := replicateTargetConfig{
		DBMS:       extractString(data, "target_dbms"),
		DBServer:   extractString(data, "target_db_server"),
		DBName:     extractString(data, "target_db_name"),
		DBUser:     extractString(data, "target_db_user"),
		DBPassword: extractString(data, "target_db_password"),
	}

	missing := []string{}
	if cfg.DBMS == "" {
		missing = append(missing, "target_dbms")
	}
	if cfg.DBServer == "" {
		missing = append(missing, "target_db_server")
	}
	if cfg.DBName == "" {
		missing = append(missing, "target_db_name")
	}
	if cfg.DBUser == "" {
		missing = append(missing, "target_db_user")
	}
	if cfg.DBPassword == "" {
		missing = append(missing, "target_db_password")
	}
	if len(missing) > 0 {
		return replicateTargetConfig{}, fmt.Errorf("missing required fields: %s", strings.Join(missing, ", "))
	}

	return cfg, nil
}

func extractString(data map[string]interface{}, key string) string {
	if data == nil {
		return ""
	}
	value, ok := data[key]
	if !ok || value == nil {
		return ""
	}
	switch v := value.(type) {
	case string:
		return v
	case fmt.Stringer:
		return v.String()
	default:
		return fmt.Sprintf("%v", v)
	}
}

func extractBool(data map[string]interface{}, key string) bool {
	if data == nil {
		return false
	}
	value, ok := data[key]
	if !ok || value == nil {
		return false
	}
	switch v := value.(type) {
	case bool:
		return v
	case string:
		parsed, _ := strconv.ParseBool(v)
		return parsed
	case int:
		return v != 0
	case int64:
		return v != 0
	case float64:
		return v != 0
	default:
		return false
	}
}

func extractInt(data map[string]interface{}, key string) int {
	if data == nil {
		return 0
	}
	value, ok := data[key]
	if !ok || value == nil {
		return 0
	}
	switch v := value.(type) {
	case int:
		return v
	case int64:
		return int(v)
	case float64:
		return int(v)
	case string:
		parsed, _ := strconv.Atoi(v)
		return parsed
	default:
		return 0
	}
}

func extractStringSlice(data map[string]interface{}, key string) []string {
	if data == nil {
		return nil
	}
	value, ok := data[key]
	if !ok || value == nil {
		return nil
	}
	switch v := value.(type) {
	case []string:
		return append([]string(nil), v...)
	case []interface{}:
		result := make([]string, 0, len(v))
		for _, item := range v {
			result = append(result, fmt.Sprintf("%v", item))
		}
		return result
	default:
		return nil
	}
}

func extractYesNoOption(data map[string]interface{}, key string) (string, bool, error) {
	if data == nil {
		return "", false, nil
	}
	raw, ok := data[key]
	if !ok || raw == nil {
		return "", false, nil
	}

	switch value := raw.(type) {
	case bool:
		if value {
			return "yes", true, nil
		}
		return "no", true, nil
	case string:
		v := strings.TrimSpace(strings.ToLower(value))
		if v == "" {
			return "", false, nil
		}
		switch v {
		case "yes", "true", "1":
			return "yes", true, nil
		case "no", "false", "0":
			return "no", true, nil
		default:
			return "", false, fmt.Errorf("invalid %s: %q (expected yes/no)", key, value)
		}
	case int:
		if value != 0 {
			return "yes", true, nil
		}
		return "no", true, nil
	case int64:
		if value != 0 {
			return "yes", true, nil
		}
		return "no", true, nil
	case float64:
		if value != 0 {
			return "yes", true, nil
		}
		return "no", true, nil
	default:
		return "", false, fmt.Errorf("invalid %s type: %T", key, raw)
	}
}

func extractEnumOption(data map[string]interface{}, key string, allowed []string) (string, bool, error) {
	raw := strings.TrimSpace(extractString(data, key))
	if raw == "" {
		return "", false, nil
	}
	for _, a := range allowed {
		if raw == a {
			return raw, true, nil
		}
	}
	return "", false, fmt.Errorf("invalid %s: %q (allowed: %s)", key, raw, strings.Join(allowed, ", "))
}

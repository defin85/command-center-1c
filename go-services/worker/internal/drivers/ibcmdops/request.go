package ibcmdops

import (
	"context"
	"fmt"
	"strings"

	"github.com/commandcenter1c/commandcenter/shared/credentials"
	"github.com/commandcenter1c/commandcenter/shared/models"
	runnerartifacts "github.com/commandcenter1c/commandcenter/worker/internal/commandrunner/artifacts"
)

type ibcmdRequest struct {
	Args            []string
	Stdin           string
	ArtifactPath    string
	RuntimeBindings []map[string]interface{}
	inputCleanup    func()
	outputCleanup   func()
	outputFinalize  func(ctx context.Context) error
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

		commandID := strings.TrimSpace(extractString(data, "command_id"))
		commandTokens := []string{}
		if commandID != "" {
			commandTokens = strings.Split(commandID, ".")
		}

		findFirstPositional := func(args []string) (int, string) {
			start := 0
			if len(commandTokens) > 0 && len(args) >= len(commandTokens) {
				match := true
				for idx, tok := range commandTokens {
					if strings.TrimSpace(args[idx]) != tok {
						match = false
						break
					}
				}
				if match {
					start = len(commandTokens)
				}
			}
			for idx := start; idx < len(args); idx++ {
				token := strings.TrimSpace(args[idx])
				if token == "" {
					continue
				}
				if strings.HasPrefix(token, "-") {
					continue
				}
				return idx, token
			}
			return -1, ""
		}

		var inputCleanup func()
		var outputCleanup func()
		var outputFinalize func(ctx context.Context) error
		artifactPath := ""
		var err error

		if commandID == "infobase.dump" {
			if store == nil {
				return nil, fmt.Errorf("storage is not configured")
			}

			posIdx, requested := findFirstPositional(argv)
			if strings.HasPrefix(strings.TrimSpace(requested), runnerartifacts.ArtifactPrefix) {
				return nil, fmt.Errorf("artifact:// output is not supported for infobase.dump")
			}

			outputPath, outArtifactPath, finalize, cleanup, err := store.PrepareOutput(ctx, requested, databaseID, ".dt")
			if err != nil {
				return nil, err
			}
			if finalize != nil {
				outputFinalize = finalize
			}
			if cleanup != nil {
				outputCleanup = cleanup
			}
			artifactPath = outArtifactPath

			if posIdx >= 0 {
				argv[posIdx] = outputPath
			} else {
				argv = append(argv, outputPath)
			}
		}

		if commandID == "infobase.restore" {
			posIdx, requested := findFirstPositional(argv)
			if posIdx < 0 || strings.TrimSpace(requested) == "" {
				return nil, fmt.Errorf("input path is required")
			}

			var resolvedInput string
			var cleanup func()
			if strings.HasPrefix(strings.TrimSpace(requested), runnerartifacts.ArtifactPrefix) {
				resolvedInput, cleanup, err = runnerartifacts.ResolvePath(ctx, requested, meta)
				if err != nil {
					return nil, err
				}
			} else {
				if store == nil {
					return nil, fmt.Errorf("storage is not configured")
				}
				resolvedInput, cleanup, err = store.ResolveInput(ctx, requested)
				if err != nil {
					return nil, err
				}
			}

			argv[posIdx] = resolvedInput
			if cleanup != nil {
				inputCleanup = cleanup
			}
		}

		resolvedArgs, argvCleanup, err := runnerartifacts.ResolveArgs(ctx, argv, meta)
		if err != nil {
			if inputCleanup != nil {
				inputCleanup()
			}
			if outputCleanup != nil {
				outputCleanup()
			}
			return nil, err
		}

		combinedInputCleanup := func() {
			if inputCleanup != nil {
				inputCleanup()
			}
			if argvCleanup != nil {
				argvCleanup()
			}
		}

		runtimeBindings := make([]map[string]interface{}, 0)

		beforeNormalize := append([]string(nil), resolvedArgs...)
		resolvedArgs = normalizeIbcmdArgv(resolvedArgs)
		if !stringSliceEqual(beforeNormalize, resolvedArgs) {
			runtimeBindings = append(runtimeBindings, map[string]interface{}{
				"target_ref": "argv",
				"source_ref": "worker.normalizeIbcmdArgv",
				"resolve_at": "worker",
				"sensitive":  false,
				"status":     "applied",
			})
		}

		dbmsAuthStrategy := extractIbcmdDbmsAuthStrategy(data)
		if dbmsAuthStrategy == "service" && commandID != "" && !isServiceDbmsAuthAllowed(commandID) {
			return nil, fmt.Errorf("dbms_auth.strategy=service is not allowed for command_id=%s", commandID)
		}
		dbSourceRef := "credentials.db_user_mapping"
		if dbmsAuthStrategy == "service" {
			dbSourceRef = "credentials.db_service_mapping"
		}

		withDBArgs, dbBindings, err := injectDbmsOfflineArgs(resolvedArgs, creds, dbSourceRef)
		if err != nil {
			combinedInputCleanup()
			if outputCleanup != nil {
				outputCleanup()
			}
			return nil, err
		}
		if len(dbBindings) > 0 {
			runtimeBindings = append(runtimeBindings, dbBindings...)
		}
		resolvedArgs = withDBArgs

		credsArgs := resolvedArgs
		stdin := extractString(data, "stdin")
		ibAuthStrategy := extractIbcmdIbAuthStrategy(data)
		needsAuthArgs := shouldInjectInfobaseAuthArgs(commandID, resolvedArgs)

		if ibAuthStrategy == "service" && commandID != "" && !isServiceIbAuthAllowed(commandID) {
			return nil, fmt.Errorf("ib_auth.strategy=service is not allowed for command_id=%s", commandID)
		}

		sourceRef := "credentials.ib_user_mapping"
		if ibAuthStrategy == "service" {
			sourceRef = "credentials.ib_service_mapping"
		}

		if needsAuthArgs && ibAuthStrategy != "none" {
			username := pickIBUsername(creds)
			if username == "" {
				if ibAuthStrategy == "service" {
					return nil, fmt.Errorf("service infobase user mapping is not configured for database_id=%s", databaseID)
				}
				createdBy := strings.TrimSpace(msg.Metadata.CreatedBy)
				if createdBy == "" {
					createdBy = "unknown"
				}
				return nil, fmt.Errorf("infobase user mapping not configured for created_by=%s", createdBy)
			}

			runtimeBindings = append(runtimeBindings,
				map[string]interface{}{
					"target_ref": "flag:--user",
					"source_ref": sourceRef,
					"resolve_at": "worker",
					"sensitive":  false,
					"status":     "applied",
				},
				map[string]interface{}{
					"target_ref": "flag:--password",
					"source_ref": sourceRef,
					"resolve_at": "worker",
					"sensitive":  true,
					"status":     "applied",
				},
			)
			credsArgs = injectInfobaseAuthArgs(resolvedArgs, creds)
		} else if commandID != "" {
			reason := "unsupported_for_command"
			if ibAuthStrategy == "none" {
				reason = "strategy_none"
			}
			runtimeBindings = append(runtimeBindings, map[string]interface{}{
				"target_ref": "infobase_auth",
				"source_ref": sourceRef,
				"resolve_at": "worker",
				"sensitive":  true,
				"status":     "skipped",
				"reason":     reason,
			})
		}
		return &ibcmdRequest{
			Args:            credsArgs,
			Stdin:           stdin,
			ArtifactPath:    artifactPath,
			RuntimeBindings: runtimeBindings,
			inputCleanup:    combinedInputCleanup,
			outputCleanup:   outputCleanup,
			outputFinalize:  outputFinalize,
		}, nil
	}

	return nil, fmt.Errorf("unsupported operation type: %s", msg.OperationType)
}

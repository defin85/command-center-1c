"""
Centralized Django permission code strings used by RBAC/governance.

Keep these in sync with:
- Model Meta.permissions (custom permissions)
- Django default permissions (view/add/change/delete)
"""

from typing import Final

# =============================================================================
# Databases / Clusters (app: databases)
# =============================================================================

PERM_DATABASES_VIEW_CLUSTER: Final[str] = "databases.view_cluster"
PERM_DATABASES_OPERATE_CLUSTER: Final[str] = "databases.operate_cluster"
PERM_DATABASES_MANAGE_CLUSTER: Final[str] = "databases.manage_cluster"
PERM_DATABASES_ADMIN_CLUSTER: Final[str] = "databases.admin_cluster"

PERM_DATABASES_VIEW_DATABASE: Final[str] = "databases.view_database"
PERM_DATABASES_OPERATE_DATABASE: Final[str] = "databases.operate_database"
PERM_DATABASES_MANAGE_DATABASE: Final[str] = "databases.manage_database"
PERM_DATABASES_ADMIN_DATABASE: Final[str] = "databases.admin_database"

PERM_DATABASES_MANAGE_RBAC: Final[str] = "databases.manage_rbac"

# =============================================================================
# Templates / Workflows (app: templates)
# =============================================================================

PERM_TEMPLATES_VIEW_OPERATION_TEMPLATE: Final[str] = "templates.view_operationtemplate"
PERM_TEMPLATES_MANAGE_OPERATION_TEMPLATE: Final[str] = "templates.manage_operation_template"

PERM_TEMPLATES_VIEW_WORKFLOW_TEMPLATE: Final[str] = "templates.view_workflowtemplate"
PERM_TEMPLATES_MANAGE_WORKFLOW_TEMPLATE: Final[str] = "templates.manage_workflow_template"
PERM_TEMPLATES_EXECUTE_WORKFLOW_TEMPLATE: Final[str] = "templates.execute_workflow_template"

# =============================================================================
# Artifacts (app: artifacts)
# =============================================================================

PERM_ARTIFACTS_VIEW_ARTIFACT: Final[str] = "artifacts.view_artifact"
PERM_ARTIFACTS_MANAGE_ARTIFACT: Final[str] = "artifacts.manage_artifact"
PERM_ARTIFACTS_PURGE_ARTIFACT: Final[str] = "artifacts.purge_artifact"

PERM_ARTIFACTS_VIEW_ARTIFACT_VERSION: Final[str] = "artifacts.view_artifactversion"
PERM_ARTIFACTS_UPLOAD_ARTIFACT_VERSION: Final[str] = "artifacts.upload_artifact_version"
PERM_ARTIFACTS_DOWNLOAD_ARTIFACT_VERSION: Final[str] = "artifacts.download_artifact_version"

# =============================================================================
# Operations / Driver catalogs (app: operations)
# =============================================================================

PERM_OPERATIONS_VIEW_BATCH_OPERATION: Final[str] = "operations.view_batchoperation"
PERM_OPERATIONS_EXECUTE_SAFE_OPERATION: Final[str] = "operations.execute_safe_operation"
PERM_OPERATIONS_EXECUTE_DANGEROUS_OPERATION: Final[str] = "operations.execute_dangerous_operation"
PERM_OPERATIONS_CANCEL_OPERATION: Final[str] = "operations.cancel_operation"
PERM_OPERATIONS_VIEW_OPERATION_LOGS: Final[str] = "operations.view_operation_logs"
PERM_OPERATIONS_MANAGE_DRIVER_CATALOGS: Final[str] = "operations.manage_driver_catalogs"

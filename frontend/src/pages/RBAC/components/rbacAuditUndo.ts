import { apiClient } from '../../../api/client'
import type { AdminAuditLogItem } from '../../../api/queries/rbac'

export type UndoCommand = {
  title: string
  code: string
  meta?: Record<string, unknown>
  run: (reason: string) => Promise<void>
}

function getNumber(meta: Record<string, unknown>, key: string): number | null {
  const value = meta[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function getString(meta: Record<string, unknown>, key: string): string | null {
  const value = meta[key]
  return typeof value === 'string' ? value : null
}

function getBoolean(meta: Record<string, unknown>, key: string): boolean | null {
  const value = meta[key]
  return typeof value === 'boolean' ? value : null
}

function parseIntStrict(value: string): number | null {
  const parsed = Number.parseInt(value, 10)
  return Number.isFinite(parsed) ? parsed : null
}

export function getUndoCommand(item: AdminAuditLogItem): UndoCommand | null {
  if (item.outcome !== 'success') return null
  const meta = item.metadata ?? {}

  if (item.action === 'rbac.create_role') {
    const groupId = parseIntStrict(String(item.target_id))
    if (!groupId) return null
    return {
      title: `Undo: delete role #${groupId}`,
      code: 'delete_role',
      meta: { groupId },
      run: async (reason) => {
        await apiClient.post('/api/v2/rbac/delete-role/', { group_id: groupId, reason })
      },
    }
  }

  if (item.action === 'rbac.update_role') {
    const groupId = parseIntStrict(String(item.target_id))
    const oldName = getString(meta, 'old_name')
    if (!groupId || !oldName) return null
    return {
      title: `Undo: rename role #${groupId}`,
      code: 'rename_role',
      meta: { groupId, oldName },
      run: async (reason) => {
        await apiClient.post('/api/v2/rbac/update-role/', { group_id: groupId, name: oldName, reason })
      },
    }
  }

  if (item.action === 'rbac.set_user_roles') {
    const userId = parseIntStrict(String(item.target_id))
    const oldGroupIdsRaw = meta['old_group_ids']
    const oldGroupIds = Array.isArray(oldGroupIdsRaw)
      ? oldGroupIdsRaw.filter((v) => typeof v === 'number' && Number.isFinite(v)) as number[]
      : null
    if (!userId || !oldGroupIds) return null
    return {
      title: `Undo: restore user roles #${userId}`,
      code: 'restore_user_roles',
      meta: { userId, oldGroupIdsCount: oldGroupIds.length },
      run: async (reason) => {
        await apiClient.post('/api/v2/rbac/set-user-roles/', {
          user_id: userId,
          group_ids: oldGroupIds,
          mode: 'replace',
          reason,
        })
      },
    }
  }

  if (item.action === 'rbac.set_role_capabilities') {
    const groupId = parseIntStrict(String(item.target_id))
    const oldCodesRaw = meta['old_permission_codes']
    const oldCodes = Array.isArray(oldCodesRaw)
      ? oldCodesRaw.filter((v) => typeof v === 'string') as string[]
      : null
    if (!groupId || !oldCodes) return null
    return {
      title: `Undo: restore role capabilities #${groupId}`,
      code: 'restore_role_capabilities',
      meta: { groupId, oldCodesCount: oldCodes.length },
      run: async (reason) => {
        await apiClient.post('/api/v2/rbac/set-role-capabilities/', {
          group_id: groupId,
          permission_codes: oldCodes,
          mode: 'replace',
          reason,
        })
      },
    }
  }

  const created = getBoolean(meta, 'created')
  const deleted = getBoolean(meta, 'deleted')
  const oldLevel = getString(meta, 'old_level')
  const oldNotes = getString(meta, 'old_notes') ?? ''

  const userId = getNumber(meta, 'user_id')
  const groupId = getNumber(meta, 'group_id')
  const targetId = String(item.target_id)

  const grantOrRestore = async (path: string, payload: Record<string, unknown>, reason: string) => {
    await apiClient.post(path, { ...payload, reason })
  }

  if (item.action === 'rbac.grant_cluster_permission') {
    if (!userId) return null
    if (created === true) {
      return {
        title: 'Undo: revoke cluster permission',
        code: 'revoke_cluster_permission',
        meta: { userId, clusterId: targetId },
        run: async (reason) => {
          await apiClient.post('/api/v2/rbac/revoke-cluster-permission/', { user_id: userId, cluster_id: targetId, reason })
        },
      }
    }
    if (created === false && oldLevel) {
      return {
        title: 'Undo: restore cluster permission level',
        code: 'restore_cluster_permission_level',
        meta: { userId, clusterId: targetId, oldLevel },
        run: async (reason) => {
          await grantOrRestore('/api/v2/rbac/grant-cluster-permission/', { user_id: userId, cluster_id: targetId, level: oldLevel, notes: oldNotes }, reason)
        },
      }
    }
  }

  if (item.action === 'rbac.revoke_cluster_permission') {
    if (!userId || deleted !== true || !oldLevel) return null
    return {
      title: 'Undo: restore cluster permission',
      code: 'restore_cluster_permission',
      meta: { userId, clusterId: targetId, oldLevel },
      run: async (reason) => {
        await grantOrRestore('/api/v2/rbac/grant-cluster-permission/', { user_id: userId, cluster_id: targetId, level: oldLevel, notes: oldNotes }, reason)
      },
    }
  }

  if (item.action === 'rbac.grant_database_permission') {
    if (!userId) return null
    if (created === true) {
      return {
        title: 'Undo: revoke database permission',
        code: 'revoke_database_permission',
        meta: { userId, databaseId: targetId },
        run: async (reason) => {
          await apiClient.post('/api/v2/rbac/revoke-database-permission/', { user_id: userId, database_id: targetId, reason })
        },
      }
    }
    if (created === false && oldLevel) {
      return {
        title: 'Undo: restore database permission level',
        code: 'restore_database_permission_level',
        meta: { userId, databaseId: targetId, oldLevel },
        run: async (reason) => {
          await grantOrRestore('/api/v2/rbac/grant-database-permission/', { user_id: userId, database_id: targetId, level: oldLevel, notes: oldNotes }, reason)
        },
      }
    }
  }

  if (item.action === 'rbac.revoke_database_permission') {
    if (!userId || deleted !== true || !oldLevel) return null
    return {
      title: 'Undo: restore database permission',
      code: 'restore_database_permission',
      meta: { userId, databaseId: targetId, oldLevel },
      run: async (reason) => {
        await grantOrRestore('/api/v2/rbac/grant-database-permission/', { user_id: userId, database_id: targetId, level: oldLevel, notes: oldNotes }, reason)
      },
    }
  }

  if (item.action === 'rbac.grant_cluster_group_permission') {
    if (!groupId) return null
    if (created === true) {
      return {
        title: 'Undo: revoke cluster group permission',
        code: 'revoke_cluster_group_permission',
        meta: { groupId, clusterId: targetId },
        run: async (reason) => {
          await apiClient.post('/api/v2/rbac/revoke-cluster-group-permission/', { group_id: groupId, cluster_id: targetId, reason })
        },
      }
    }
    if (created === false && oldLevel) {
      return {
        title: 'Undo: restore cluster group permission level',
        code: 'restore_cluster_group_permission_level',
        meta: { groupId, clusterId: targetId, oldLevel },
        run: async (reason) => {
          await grantOrRestore('/api/v2/rbac/grant-cluster-group-permission/', { group_id: groupId, cluster_id: targetId, level: oldLevel, notes: oldNotes }, reason)
        },
      }
    }
  }

  if (item.action === 'rbac.revoke_cluster_group_permission') {
    if (!groupId || deleted !== true || !oldLevel) return null
    return {
      title: 'Undo: restore cluster group permission',
      code: 'restore_cluster_group_permission',
      meta: { groupId, clusterId: targetId, oldLevel },
      run: async (reason) => {
        await grantOrRestore('/api/v2/rbac/grant-cluster-group-permission/', { group_id: groupId, cluster_id: targetId, level: oldLevel, notes: oldNotes }, reason)
      },
    }
  }

  if (item.action === 'rbac.grant_database_group_permission') {
    if (!groupId) return null
    if (created === true) {
      return {
        title: 'Undo: revoke database group permission',
        code: 'revoke_database_group_permission',
        meta: { groupId, databaseId: targetId },
        run: async (reason) => {
          await apiClient.post('/api/v2/rbac/revoke-database-group-permission/', { group_id: groupId, database_id: targetId, reason })
        },
      }
    }
    if (created === false && oldLevel) {
      return {
        title: 'Undo: restore database group permission level',
        code: 'restore_database_group_permission_level',
        meta: { groupId, databaseId: targetId, oldLevel },
        run: async (reason) => {
          await grantOrRestore('/api/v2/rbac/grant-database-group-permission/', { group_id: groupId, database_id: targetId, level: oldLevel, notes: oldNotes }, reason)
        },
      }
    }
  }

  if (item.action === 'rbac.revoke_database_group_permission') {
    if (!groupId || deleted !== true || !oldLevel) return null
    return {
      title: 'Undo: restore database group permission',
      code: 'restore_database_group_permission',
      meta: { groupId, databaseId: targetId, oldLevel },
      run: async (reason) => {
        await grantOrRestore('/api/v2/rbac/grant-database-group-permission/', { group_id: groupId, database_id: targetId, level: oldLevel, notes: oldNotes }, reason)
      },
    }
  }

  if (item.action === 'rbac.grant_operation_template_permission') {
    if (!userId) return null
    if (created === true) {
      return {
        title: 'Undo: revoke operation template permission',
        code: 'revoke_operation_template_permission',
        meta: { userId, templateId: targetId },
        run: async (reason) => {
          await apiClient.post('/api/v2/rbac/revoke-operation-template-permission/', { user_id: userId, template_id: targetId, reason })
        },
      }
    }
    if (created === false && oldLevel) {
      return {
        title: 'Undo: restore operation template permission level',
        code: 'restore_operation_template_permission_level',
        meta: { userId, templateId: targetId, oldLevel },
        run: async (reason) => {
          await grantOrRestore('/api/v2/rbac/grant-operation-template-permission/', { user_id: userId, template_id: targetId, level: oldLevel, notes: oldNotes }, reason)
        },
      }
    }
  }

  if (item.action === 'rbac.revoke_operation_template_permission') {
    if (!userId || deleted !== true || !oldLevel) return null
    return {
      title: 'Undo: restore operation template permission',
      code: 'restore_operation_template_permission',
      meta: { userId, templateId: targetId, oldLevel },
      run: async (reason) => {
        await grantOrRestore('/api/v2/rbac/grant-operation-template-permission/', { user_id: userId, template_id: targetId, level: oldLevel, notes: oldNotes }, reason)
      },
    }
  }

  if (item.action === 'rbac.grant_operation_template_group_permission') {
    if (!groupId) return null
    if (created === true) {
      return {
        title: 'Undo: revoke operation template group permission',
        code: 'revoke_operation_template_group_permission',
        meta: { groupId, templateId: targetId },
        run: async (reason) => {
          await apiClient.post('/api/v2/rbac/revoke-operation-template-group-permission/', { group_id: groupId, template_id: targetId, reason })
        },
      }
    }
    if (created === false && oldLevel) {
      return {
        title: 'Undo: restore operation template group permission level',
        code: 'restore_operation_template_group_permission_level',
        meta: { groupId, templateId: targetId, oldLevel },
        run: async (reason) => {
          await grantOrRestore('/api/v2/rbac/grant-operation-template-group-permission/', { group_id: groupId, template_id: targetId, level: oldLevel, notes: oldNotes }, reason)
        },
      }
    }
  }

  if (item.action === 'rbac.revoke_operation_template_group_permission') {
    if (!groupId || deleted !== true || !oldLevel) return null
    return {
      title: 'Undo: restore operation template group permission',
      code: 'restore_operation_template_group_permission',
      meta: { groupId, templateId: targetId, oldLevel },
      run: async (reason) => {
        await grantOrRestore('/api/v2/rbac/grant-operation-template-group-permission/', { group_id: groupId, template_id: targetId, level: oldLevel, notes: oldNotes }, reason)
      },
    }
  }

  if (item.action === 'rbac.grant_workflow_template_permission') {
    if (!userId) return null
    if (created === true) {
      return {
        title: 'Undo: revoke workflow template permission',
        code: 'revoke_workflow_template_permission',
        meta: { userId, templateId: targetId },
        run: async (reason) => {
          await apiClient.post('/api/v2/rbac/revoke-workflow-template-permission/', { user_id: userId, template_id: targetId, reason })
        },
      }
    }
    if (created === false && oldLevel) {
      return {
        title: 'Undo: restore workflow template permission level',
        code: 'restore_workflow_template_permission_level',
        meta: { userId, templateId: targetId, oldLevel },
        run: async (reason) => {
          await grantOrRestore('/api/v2/rbac/grant-workflow-template-permission/', { user_id: userId, template_id: targetId, level: oldLevel, notes: oldNotes }, reason)
        },
      }
    }
  }

  if (item.action === 'rbac.revoke_workflow_template_permission') {
    if (!userId || deleted !== true || !oldLevel) return null
    return {
      title: 'Undo: restore workflow template permission',
      code: 'restore_workflow_template_permission',
      meta: { userId, templateId: targetId, oldLevel },
      run: async (reason) => {
        await grantOrRestore('/api/v2/rbac/grant-workflow-template-permission/', { user_id: userId, template_id: targetId, level: oldLevel, notes: oldNotes }, reason)
      },
    }
  }

  if (item.action === 'rbac.grant_workflow_template_group_permission') {
    if (!groupId) return null
    if (created === true) {
      return {
        title: 'Undo: revoke workflow template group permission',
        code: 'revoke_workflow_template_group_permission',
        meta: { groupId, templateId: targetId },
        run: async (reason) => {
          await apiClient.post('/api/v2/rbac/revoke-workflow-template-group-permission/', { group_id: groupId, template_id: targetId, reason })
        },
      }
    }
    if (created === false && oldLevel) {
      return {
        title: 'Undo: restore workflow template group permission level',
        code: 'restore_workflow_template_group_permission_level',
        meta: { groupId, templateId: targetId, oldLevel },
        run: async (reason) => {
          await grantOrRestore('/api/v2/rbac/grant-workflow-template-group-permission/', { group_id: groupId, template_id: targetId, level: oldLevel, notes: oldNotes }, reason)
        },
      }
    }
  }

  if (item.action === 'rbac.revoke_workflow_template_group_permission') {
    if (!groupId || deleted !== true || !oldLevel) return null
    return {
      title: 'Undo: restore workflow template group permission',
      code: 'restore_workflow_template_group_permission',
      meta: { groupId, templateId: targetId, oldLevel },
      run: async (reason) => {
        await grantOrRestore('/api/v2/rbac/grant-workflow-template-group-permission/', { group_id: groupId, template_id: targetId, level: oldLevel, notes: oldNotes }, reason)
      },
    }
  }

  if (item.action === 'rbac.grant_artifact_permission') {
    if (!userId) return null
    if (created === true) {
      return {
        title: 'Undo: revoke artifact permission',
        code: 'revoke_artifact_permission',
        meta: { userId, artifactId: targetId },
        run: async (reason) => {
          await apiClient.post('/api/v2/rbac/revoke-artifact-permission/', { user_id: userId, artifact_id: targetId, reason })
        },
      }
    }
    if (created === false && oldLevel) {
      return {
        title: 'Undo: restore artifact permission level',
        code: 'restore_artifact_permission_level',
        meta: { userId, artifactId: targetId, oldLevel },
        run: async (reason) => {
          await grantOrRestore('/api/v2/rbac/grant-artifact-permission/', { user_id: userId, artifact_id: targetId, level: oldLevel, notes: oldNotes }, reason)
        },
      }
    }
  }

  if (item.action === 'rbac.revoke_artifact_permission') {
    if (!userId || deleted !== true || !oldLevel) return null
    return {
      title: 'Undo: restore artifact permission',
      code: 'restore_artifact_permission',
      meta: { userId, artifactId: targetId, oldLevel },
      run: async (reason) => {
        await grantOrRestore('/api/v2/rbac/grant-artifact-permission/', { user_id: userId, artifact_id: targetId, level: oldLevel, notes: oldNotes }, reason)
      },
    }
  }

  if (item.action === 'rbac.grant_artifact_group_permission') {
    if (!groupId) return null
    if (created === true) {
      return {
        title: 'Undo: revoke artifact group permission',
        code: 'revoke_artifact_group_permission',
        meta: { groupId, artifactId: targetId },
        run: async (reason) => {
          await apiClient.post('/api/v2/rbac/revoke-artifact-group-permission/', { group_id: groupId, artifact_id: targetId, reason })
        },
      }
    }
    if (created === false && oldLevel) {
      return {
        title: 'Undo: restore artifact group permission level',
        code: 'restore_artifact_group_permission_level',
        meta: { groupId, artifactId: targetId, oldLevel },
        run: async (reason) => {
          await grantOrRestore('/api/v2/rbac/grant-artifact-group-permission/', { group_id: groupId, artifact_id: targetId, level: oldLevel, notes: oldNotes }, reason)
        },
      }
    }
  }

  if (item.action === 'rbac.revoke_artifact_group_permission') {
    if (!groupId || deleted !== true || !oldLevel) return null
    return {
      title: 'Undo: restore artifact group permission',
      code: 'restore_artifact_group_permission',
      meta: { groupId, artifactId: targetId, oldLevel },
      run: async (reason) => {
        await grantOrRestore('/api/v2/rbac/grant-artifact-group-permission/', { group_id: groupId, artifact_id: targetId, level: oldLevel, notes: oldNotes }, reason)
      },
    }
  }

  return null
}


import { getV2 } from '../../api/generated'
import { StatusBadge } from '../../components/platform'
import type {
  DatabaseMetadataManagementResponse,
  DecisionMetadataCompatibility,
  DecisionRevisionMetadataContext,
  DecisionTable,
  PoolODataMetadataCatalogResponse,
} from '../../api/generated/model'
import type {
  OrganizationPool,
} from '../../api/intercompanyPools'
import {
  buildDocumentPolicyFromBuilder,
  documentPolicyToBuilderChains,
  extractDocumentPolicyOutput,
  type DocumentPolicyBuilderChainFormValue,
} from './documentPolicyBuilder'
import {
  buildDecisionBindingRefKey,
  type PinnedDecisionRefs,
} from './decisionSnapshotFilter'
import type {
  DecisionEditorMode,
  DecisionEditorState,
  DecisionEditorSourceSummary,
  DecisionEditorTab,
  DecisionEditorTargetSummary,
} from './DecisionEditorPanel'
import type { DecisionLegacyImportState } from './DecisionLegacyImportPanel'

const api = getV2()

export type MetadataContextLike = PoolODataMetadataCatalogResponse | DecisionRevisionMetadataContext | null | undefined
export type DatabaseMetadataManagementLike = DatabaseMetadataManagementResponse | null | undefined
export type DecisionReadResponse = Awaited<ReturnType<typeof api.getDecisionsCollection>>
export type DecisionDetailReadResponse = Awaited<ReturnType<typeof api.getDecisionsDetail>>

export const DECISIONS_API_OPTIONS = { errorPolicy: 'page' } as const

const METADATA_CONTEXT_FALLBACK_CODES = new Set([
  'ODATA_MAPPING_AMBIGUOUS',
  'ODATA_MAPPING_NOT_CONFIGURED',
  'POOL_METADATA_SNAPSHOT_UNAVAILABLE',
  'POOL_METADATA_PROFILE_UNAVAILABLE',
  'POOL_METADATA_REFRESH_IN_PROGRESS',
  'POOL_METADATA_FETCH_FAILED',
  'POOL_METADATA_PARSE_FAILED',
])

export const formatJson = (value: unknown): string => JSON.stringify(value, null, 2)

export const readMetadataString = (metadata: MetadataContextLike, key: string): string => {
  if (!metadata || typeof metadata !== 'object') return ''
  const value = (metadata as Record<string, unknown>)[key]
  return typeof value === 'string' ? value.trim() : ''
}

export const readMetadataBoolean = (metadata: MetadataContextLike, key: string): boolean => {
  if (!metadata || typeof metadata !== 'object') return false
  return Boolean((metadata as Record<string, unknown>)[key])
}

export const getApiErrorInfo = (error: unknown) => {
  const candidate = error as {
    message?: string
    response?: {
      status?: number
      data?: {
        error?: { code?: string; message?: string }
        detail?: string
      }
    }
  } | null

  return {
    code: typeof candidate?.response?.data?.error?.code === 'string'
      ? candidate.response.data.error.code.trim()
      : '',
    message: typeof candidate?.response?.data?.error?.message === 'string'
      ? candidate.response.data.error.message
      : (
        typeof candidate?.response?.data?.detail === 'string'
          ? candidate.response.data.detail
          : (
            typeof candidate?.message === 'string'
              ? candidate.message
              : ''
          )
      ),
    status: typeof candidate?.response?.status === 'number' ? candidate.response.status : null,
  }
}

export const toErrorMessage = (error: unknown, fallback: string): string => {
  const apiError = getApiErrorInfo(error)
  if (apiError.message.trim()) {
    return apiError.message.trim()
  }
  return fallback
}

export const shouldFallbackToUnscopedDecisionRead = (error: unknown): boolean => {
  const { code, status } = getApiErrorInfo(error)
  if (METADATA_CONTEXT_FALLBACK_CODES.has(code)) {
    return true
  }
  return Boolean(status && status >= 500 && status < 600 && code.startsWith('POOL_METADATA_'))
}

export const loadDecisionsCollection = async (
  databaseId: string | undefined
): Promise<{ response: DecisionReadResponse; usedFallback: boolean }> => {
  try {
    const response = await api.getDecisionsCollection(
      databaseId ? { database_id: databaseId } : {},
      DECISIONS_API_OPTIONS,
    )
    return { response, usedFallback: false }
  } catch (error) {
    if (!databaseId || !shouldFallbackToUnscopedDecisionRead(error)) {
      throw error
    }

    const response = await api.getDecisionsCollection({}, DECISIONS_API_OPTIONS)
    return { response, usedFallback: true }
  }
}

export const loadDecisionDetail = async (
  decisionId: string,
  databaseId: string | undefined
): Promise<{ response: DecisionDetailReadResponse; usedFallback: boolean }> => {
  try {
    const response = await api.getDecisionsDetail(
      decisionId,
      databaseId ? { database_id: databaseId } : {},
      DECISIONS_API_OPTIONS,
    )
    return { response, usedFallback: false }
  } catch (error) {
    if (!databaseId || !shouldFallbackToUnscopedDecisionRead(error)) {
      throw error
    }

    const response = await api.getDecisionsDetail(decisionId, {}, DECISIONS_API_OPTIONS)
    return { response, usedFallback: true }
  }
}

export const buildEmptyDraft = (mode: DecisionEditorMode, activeTab: DecisionEditorTab): DecisionEditorState => ({
  mode,
  decisionTableId: '',
  name: '',
  description: '',
  chains: [],
  rawJson: '',
  activeTab,
  isActive: true,
})

export const buildEmptyLegacyImportDraft = (poolId = ''): DecisionLegacyImportState => ({
  poolId,
  edgeVersionId: '',
  decisionTableId: '',
  name: '',
  description: '',
})

export const formatDatabaseOptionLabel = (
  database: { id: string; name?: string | null; base_name?: string | null; version?: string | null }
): string => `${database.name} (${database.base_name ?? database.version ?? database.id})`

export const buildEditorSourceSummary = (decision: DecisionTable): DecisionEditorSourceSummary => ({
  decisionId: decision.id,
  decisionTableId: decision.decision_table_id,
  decisionRevision: decision.decision_revision,
  name: decision.name,
  compatibilityStatus: decision.metadata_compatibility?.status ?? undefined,
  compatibilityReason: decision.metadata_compatibility?.reason ?? undefined,
})

export const buildEditorTargetSummary = (
  metadata: MetadataContextLike,
  options: {
    databaseId: string
    databaseLabel: string
  },
): DecisionEditorTargetSummary | undefined => {
  const configName = readMetadataString(metadata, 'config_name')
  const configVersion = readMetadataString(metadata, 'config_version')
  if (!configName || !configVersion) {
    return undefined
  }

  return {
    databaseId: options.databaseId,
    databaseLabel: options.databaseLabel,
    configurationLabel: `${configName} ${configVersion}`,
    snapshotId: readMetadataString(metadata, 'snapshot_id') || undefined,
    resolutionMode: readMetadataString(metadata, 'resolution_mode') || undefined,
  }
}

const buildCloneDecisionTableId = (decisionTableId: string): string => {
  const normalized = decisionTableId.trim()
  if (!normalized) {
    return ''
  }
  return `${normalized}-copy`
}

export const buildDraftFromDecision = (
  decision: DecisionTable,
  options?: {
    mode?: DecisionEditorMode
    targetDatabaseId?: string
    targetSummary?: DecisionEditorTargetSummary
  },
): DecisionEditorState => {
  const policy = extractDocumentPolicyOutput(decision, { allowNonDefaultRuleId: true })
  const chains = documentPolicyToBuilderChains(policy)
  const mode = options?.mode ?? 'revise'
  const isClone = mode === 'clone'
  const isSourceBasedMode = mode === 'rollover' || mode === 'clone'
  return {
    mode,
    decisionTableId: isClone
      ? buildCloneDecisionTableId(decision.decision_table_id)
      : decision.decision_table_id,
    name: decision.name,
    description: decision.description ?? '',
    chains,
    rawJson: formatJson(buildDocumentPolicyFromBuilder(chains)),
    activeTab: 'builder',
    parentVersionId: isClone ? undefined : decision.id,
    isActive: decision.is_active,
    targetDatabaseId: options?.targetDatabaseId,
    sourceSummary: isSourceBasedMode ? buildEditorSourceSummary(decision) : undefined,
    targetSummary: isSourceBasedMode ? options?.targetSummary : undefined,
  }
}

export const normalizeMetadataItems = (
  metadata: MetadataContextLike,
  options?: {
    unavailableLabel?: string
    driftYesLabel?: string
    driftNoLabel?: string
  },
) => {
  const unavailableLabel = options?.unavailableLabel ?? '—'
  const driftYesLabel = options?.driftYesLabel ?? 'warning'
  const driftNoLabel = options?.driftNoLabel ?? 'no'

  return (
  metadata
    ? [
      { key: 'config', value: metadata.config_name || unavailableLabel },
      { key: 'version', value: metadata.config_version || unavailableLabel },
      { key: 'generation', value: readMetadataString(metadata, 'config_generation_id') || unavailableLabel },
      { key: 'snapshot', value: metadata.snapshot_id || unavailableLabel },
      { key: 'mode', value: metadata.resolution_mode || unavailableLabel },
      { key: 'hash', value: metadata.metadata_hash || unavailableLabel },
      { key: 'observed_hash', value: readMetadataString(metadata, 'observed_metadata_hash') || unavailableLabel },
      { key: 'drift', value: readMetadataBoolean(metadata, 'publication_drift') ? driftYesLabel : driftNoLabel },
      { key: 'provenance', value: metadata.provenance_database_id || unavailableLabel },
    ]
    : []
)
}

export const renderCompatibilityTag = (compatibility?: DecisionMetadataCompatibility | null) => {
  if (!compatibility) return <StatusBadge status="unknown" />
  return <StatusBadge status={compatibility.status} />
}

export const buildChainsFromDraft = (draft: DecisionEditorState): DocumentPolicyBuilderChainFormValue[] => {
  if (draft.activeTab === 'raw') {
    const parsed = JSON.parse(draft.rawJson || '{}')
    return documentPolicyToBuilderChains(parsed)
  }
  return draft.chains
}

export const hasLegacyDocumentPolicy = (metadata: Record<string, unknown> | null | undefined): boolean => (
  Boolean(metadata && typeof metadata === 'object' && metadata.document_policy !== undefined && metadata.document_policy !== null)
)

export const shouldPreferUnscopedReadFromMetadataManagement = (
  metadataManagement: DatabaseMetadataManagementLike
): boolean => {
  if (!metadataManagement) {
    return false
  }

  const profileStatus = String(metadataManagement.configuration_profile?.status ?? '').trim()
  const snapshotStatus = String(metadataManagement.metadata_snapshot?.status ?? '').trim()
  const missingReason = String(metadataManagement.metadata_snapshot?.missing_reason ?? '').trim()

  return (
    profileStatus === 'missing'
    || snapshotStatus === 'missing'
    || missingReason === 'configuration_profile_unavailable'
    || missingReason === 'current_snapshot_missing'
  )
}

export const collectPinnedDecisionRefs = (pools: OrganizationPool[]): PinnedDecisionRefs => {
  const decisionIds = new Set<string>()
  const decisionTableKeys = new Set<string>()

  for (const pool of pools) {
    for (const binding of pool.workflow_bindings ?? []) {
      for (const decisionRef of binding.decisions ?? []) {
        const decisionRefRecord = decisionRef as { decision_id?: string | null } | null
        const decisionId = typeof decisionRefRecord?.decision_id === 'string'
          ? decisionRefRecord.decision_id.trim()
          : ''
        if (decisionId) {
          decisionIds.add(decisionId)
        }

        const refKey = buildDecisionBindingRefKey(
          decisionRef.decision_key,
          decisionRef.decision_table_id,
        )
        if (refKey) {
          decisionTableKeys.add(refKey)
        }
      }
    }
  }

  return {
    decisionIds: [...decisionIds],
    decisionTableKeys: [...decisionTableKeys],
  }
}

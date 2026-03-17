import { Tag } from 'antd'

import { getV2 } from '../../api/generated'
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

export const DECISIONS_API_OPTIONS = { skipGlobalError: true } as const

export const METADATA_CONTEXT_FALLBACK_MESSAGE = 'Metadata context недоступен для выбранной базы. Показываем глобальный список revisions без compatibility context этой базы; управлять configuration profile и metadata snapshot нужно через /databases.'
export const METADATA_CONTEXT_ACTION_BLOCKED_MESSAGE = 'Metadata context недоступен для выбранной базы. Чтобы восстановить configuration profile и metadata snapshot, откройте /databases.'
export const METADATA_CONTEXT_ROLLOVER_BLOCKED_MESSAGE = 'Resolved target metadata context недоступен. Откройте /databases и обновите metadata snapshot перед guided rollover.'
export const LEGACY_BOUND_DECISION_READ_ONLY_MESSAGE = 'This revision is still pinned in workflow bindings, but /decisions editing supports only document_policy. Update the binding to a document_policy revision before editing here.'

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
  return {
    mode: options?.mode ?? 'revise',
    decisionTableId: decision.decision_table_id,
    name: decision.name,
    description: decision.description ?? '',
    chains,
    rawJson: formatJson(buildDocumentPolicyFromBuilder(chains)),
    activeTab: 'builder',
    parentVersionId: decision.id,
    isActive: decision.is_active,
    targetDatabaseId: options?.targetDatabaseId,
    sourceSummary: options?.mode === 'rollover' ? buildEditorSourceSummary(decision) : undefined,
    targetSummary: options?.mode === 'rollover' ? options?.targetSummary : undefined,
  }
}

export const normalizeMetadataItems = (metadata: MetadataContextLike) => (
  metadata
    ? [
      { key: 'config', label: 'Configuration profile', value: metadata.config_name || '—' },
      { key: 'version', label: 'Config version', value: metadata.config_version || '—' },
      { key: 'generation', label: 'Config generation ID', value: readMetadataString(metadata, 'config_generation_id') || '—' },
      { key: 'snapshot', label: 'Snapshot ID', value: metadata.snapshot_id || '—' },
      { key: 'mode', label: 'Resolution mode', value: metadata.resolution_mode || '—' },
      { key: 'hash', label: 'Metadata hash', value: metadata.metadata_hash || '—' },
      { key: 'observed_hash', label: 'Observed hash', value: readMetadataString(metadata, 'observed_metadata_hash') || '—' },
      { key: 'drift', label: 'Publication drift', value: readMetadataBoolean(metadata, 'publication_drift') ? 'warning' : 'no' },
      { key: 'provenance', label: 'Provenance database', value: metadata.provenance_database_id || '—' },
    ]
    : []
)

export const renderCompatibilityTag = (compatibility?: DecisionMetadataCompatibility | null) => {
  if (!compatibility) return <Tag>unknown</Tag>
  const color = compatibility.is_compatible ? 'green' : 'red'
  return <Tag color={color}>{compatibility.status}</Tag>
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

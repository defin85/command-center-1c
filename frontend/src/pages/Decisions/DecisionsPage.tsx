import { EditOutlined, ImportOutlined, MinusCircleOutlined, PlusOutlined } from '@ant-design/icons'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Alert,
  App,
  Button,
  Card,
  Descriptions,
  Empty,
  List,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
} from 'antd'

import { getV2 } from '../../api/generated'
import type {
  DatabaseMetadataManagementResponse,
  DecisionMetadataCompatibility,
  DecisionRevisionMetadataContext,
  DecisionTable,
  PoolODataMetadataCatalogResponse,
} from '../../api/generated/model'
import {
  getPoolGraph,
  listOrganizationPools,
  migratePoolEdgeDocumentPolicy,
  type OrganizationPool,
  type PoolGraph,
  type PoolDocumentPolicyMigrationResponse,
} from '../../api/intercompanyPools'
import { useDatabaseMetadataManagement, useDatabases } from '../../api/queries/databases'
import { LazyJsonCodeEditor } from '../../components/code/LazyJsonCodeEditor'
import {
  DecisionLegacyImportPanel,
  type DecisionLegacyImportState,
} from './DecisionLegacyImportPanel'
import {
  buildDocumentPolicyDecisionPayload,
  buildDocumentPolicyFromBuilder,
  documentPolicyToBuilderChains,
  extractDocumentPolicyOutput,
  type DocumentPolicyBuilderChainFormValue,
} from './documentPolicyBuilder'
import {
  filterDocumentPolicyDecisions,
  resolveDecisionSnapshotFilter,
  type DecisionSnapshotFilterMode,
} from './decisionSnapshotFilter'
import {
  DecisionEditorPanel,
  type DecisionEditorMode,
  type DecisionEditorState,
  type DecisionEditorSourceSummary,
  type DecisionEditorTab,
  type DecisionEditorTargetSummary,
} from './DecisionEditorPanel'
import { DocumentPolicyViewer } from './DocumentPolicyViewer'

const { Title, Text } = Typography

const api = getV2()

type MetadataContextLike = PoolODataMetadataCatalogResponse | DecisionRevisionMetadataContext | null | undefined
type DatabaseMetadataManagementLike = DatabaseMetadataManagementResponse | null | undefined
type DecisionReadResponse = Awaited<ReturnType<typeof api.getDecisionsCollection>>
type DecisionDetailReadResponse = Awaited<ReturnType<typeof api.getDecisionsDetail>>
const DECISIONS_API_OPTIONS = { skipGlobalError: true } as const

const formatJson = (value: unknown): string => JSON.stringify(value, null, 2)

const readMetadataString = (metadata: MetadataContextLike, key: string): string => {
  if (!metadata || typeof metadata !== 'object') return ''
  const value = (metadata as Record<string, unknown>)[key]
  return typeof value === 'string' ? value.trim() : ''
}

const readMetadataBoolean = (metadata: MetadataContextLike, key: string): boolean => {
  if (!metadata || typeof metadata !== 'object') return false
  return Boolean((metadata as Record<string, unknown>)[key])
}

const getApiErrorInfo = (error: unknown) => {
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

const toErrorMessage = (error: unknown, fallback: string): string => {
  const apiError = getApiErrorInfo(error)
  if (apiError.message.trim()) {
    return apiError.message.trim()
  }
  return fallback
}

const METADATA_CONTEXT_FALLBACK_CODES = new Set([
  'ODATA_MAPPING_AMBIGUOUS',
  'ODATA_MAPPING_NOT_CONFIGURED',
  'POOL_METADATA_SNAPSHOT_UNAVAILABLE',
  'POOL_METADATA_PROFILE_UNAVAILABLE',
  'POOL_METADATA_REFRESH_IN_PROGRESS',
  'POOL_METADATA_FETCH_FAILED',
  'POOL_METADATA_PARSE_FAILED',
])

const METADATA_CONTEXT_FALLBACK_MESSAGE = 'Metadata context недоступен для выбранной базы. Показываем глобальный список revisions без compatibility context этой базы; управлять configuration profile и metadata snapshot нужно через /databases.'
const METADATA_CONTEXT_ACTION_BLOCKED_MESSAGE = 'Metadata context недоступен для выбранной базы. Чтобы восстановить configuration profile и metadata snapshot, откройте /databases.'
const METADATA_CONTEXT_ROLLOVER_BLOCKED_MESSAGE = 'Resolved target metadata context недоступен. Откройте /databases и обновите metadata snapshot перед guided rollover.'

const shouldFallbackToUnscopedDecisionRead = (error: unknown): boolean => {
  const { code, status } = getApiErrorInfo(error)
  if (METADATA_CONTEXT_FALLBACK_CODES.has(code)) {
    return true
  }
  return Boolean(status && status >= 500 && status < 600 && code.startsWith('POOL_METADATA_'))
}

const loadDecisionsCollection = async (
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

const loadDecisionDetail = async (
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

const buildEmptyDraft = (mode: DecisionEditorMode, activeTab: DecisionEditorTab): DecisionEditorState => ({
  mode,
  decisionTableId: '',
  name: '',
  description: '',
  chains: [],
  rawJson: '',
  activeTab,
  isActive: true,
})

const buildEmptyLegacyImportDraft = (poolId = ''): DecisionLegacyImportState => ({
  poolId,
  edgeVersionId: '',
  decisionTableId: '',
  name: '',
  description: '',
})

const formatDatabaseOptionLabel = (
  database: { id: string; name?: string | null; base_name?: string | null; version?: string | null }
): string => `${database.name} (${database.base_name ?? database.version ?? database.id})`

const buildEditorSourceSummary = (decision: DecisionTable): DecisionEditorSourceSummary => ({
  decisionId: decision.id,
  decisionTableId: decision.decision_table_id,
  decisionRevision: decision.decision_revision,
  name: decision.name,
  compatibilityStatus: decision.metadata_compatibility?.status ?? undefined,
  compatibilityReason: decision.metadata_compatibility?.reason ?? undefined,
})

const buildEditorTargetSummary = (
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

const buildDraftFromDecision = (
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

const normalizeMetadataItems = (metadata: MetadataContextLike) => (
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

const renderCompatibilityTag = (compatibility?: DecisionMetadataCompatibility | null) => {
  if (!compatibility) return <Tag>unknown</Tag>
  const color = compatibility.is_compatible ? 'green' : 'red'
  return <Tag color={color}>{compatibility.status}</Tag>
}

const buildChainsFromDraft = (draft: DecisionEditorState): DocumentPolicyBuilderChainFormValue[] => {
  if (draft.activeTab === 'raw') {
    const parsed = JSON.parse(draft.rawJson || '{}')
    return documentPolicyToBuilderChains(parsed)
  }
  return draft.chains
}

const hasLegacyDocumentPolicy = (metadata: Record<string, unknown> | null | undefined): boolean => (
  Boolean(metadata && typeof metadata === 'object' && metadata.document_policy !== undefined && metadata.document_policy !== null)
)

const shouldPreferUnscopedReadFromMetadataManagement = (
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

export function DecisionsPage() {
  const navigate = useNavigate()
  const { message } = App.useApp()
  const databasesQuery = useDatabases({ filters: { limit: 500, offset: 0 } })

  const databases = useMemo(
    () => databasesQuery.data?.databases ?? [],
    [databasesQuery.data?.databases],
  )
  const [selectedDatabaseId, setSelectedDatabaseId] = useState<string | null | undefined>(undefined)
  const [decisions, setDecisions] = useState<DecisionTable[]>([])
  const [selectedDecisionId, setSelectedDecisionId] = useState<string | null>(null)
  const [selectedDecision, setSelectedDecision] = useState<DecisionTable | null>(null)
  const [metadataContext, setMetadataContext] = useState<PoolODataMetadataCatalogResponse | null>(null)
  const [detailContext, setDetailContext] = useState<PoolODataMetadataCatalogResponse | null>(null)
  const [listLoading, setListLoading] = useState(false)
  const [detailLoading, setDetailLoading] = useState(false)
  const [listError, setListError] = useState<string | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [pools, setPools] = useState<OrganizationPool[]>([])
  const [poolsLoading, setPoolsLoading] = useState(false)
  const [poolsError, setPoolsError] = useState<string | null>(null)
  const [editorDraft, setEditorDraft] = useState<DecisionEditorState | null>(null)
  const [editorError, setEditorError] = useState<string | null>(null)
  const [legacyImportDraft, setLegacyImportDraft] = useState<DecisionLegacyImportState | null>(null)
  const [legacyImportGraph, setLegacyImportGraph] = useState<PoolGraph | null>(null)
  const [legacyImportGraphLoading, setLegacyImportGraphLoading] = useState(false)
  const [legacyImportError, setLegacyImportError] = useState<string | null>(null)
  const [legacyImportResult, setLegacyImportResult] = useState<PoolDocumentPolicyMigrationResponse | null>(null)
  const [saving, setSaving] = useState(false)
  const [reloadTick, setReloadTick] = useState(0)
  const [listReadFallbackUsed, setListReadFallbackUsed] = useState(false)
  const [detailReadFallbackUsed, setDetailReadFallbackUsed] = useState(false)
  const [snapshotFilterMode, setSnapshotFilterMode] = useState<DecisionSnapshotFilterMode>('matching_snapshot')
  const effectiveSelectedDatabaseId = selectedDatabaseId ?? undefined
  const selectedDatabaseMetadataManagementQuery = useDatabaseMetadataManagement({
    id: effectiveSelectedDatabaseId ?? '',
    enabled: Boolean(effectiveSelectedDatabaseId),
  })
  const selectedDatabase = useMemo(
    () => databases.find((database) => database.id === effectiveSelectedDatabaseId) ?? null,
    [databases, effectiveSelectedDatabaseId],
  )
  const selectedDatabaseLabel = selectedDatabase ? formatDatabaseOptionLabel(selectedDatabase) : ''
  const selectedDatabaseMetadataManagement = selectedDatabaseMetadataManagementQuery.data
  const selectedDatabaseMetadataManagementPending = Boolean(
    effectiveSelectedDatabaseId
    && selectedDatabaseMetadataManagementQuery.isLoading
    && !selectedDatabaseMetadataManagement
  )
  const legacyImportOpen = Boolean(legacyImportDraft)
  const shouldPreferUnscopedDecisionRead = Boolean(
    effectiveSelectedDatabaseId
    && shouldPreferUnscopedReadFromMetadataManagement(selectedDatabaseMetadataManagement),
  )
  const rolloverTargetMetadataContext = detailContext ?? metadataContext
  const selectedDecisionRequiresRollover = Boolean(selectedDecision?.metadata_compatibility?.is_compatible === false)
  const metadataContextFallbackActive = Boolean(effectiveSelectedDatabaseId && (listReadFallbackUsed || detailReadFallbackUsed))
  const canOpenRollover = Boolean(
    selectedDecision
    && effectiveSelectedDatabaseId
    && !metadataContextFallbackActive
    && buildEditorTargetSummary(rolloverTargetMetadataContext, {
      databaseId: effectiveSelectedDatabaseId,
      databaseLabel: selectedDatabaseLabel,
    }),
  )

  useEffect(() => {
    if (selectedDatabaseId !== undefined || databases.length === 0) return
    setSelectedDatabaseId(databases[0].id)
  }, [databases, selectedDatabaseId])

  useEffect(() => {
    if (!legacyImportOpen) {
      return
    }

    let cancelled = false

    const load = async () => {
      setPoolsLoading(true)
      setPoolsError(null)
      setLegacyImportError(null)

      try {
        const items = await listOrganizationPools()
        if (cancelled) return
        setPools(items)
      } catch (error) {
        if (cancelled) return
        const errorMessage = toErrorMessage(error, 'Failed to load pools for legacy import.')
        setPools([])
        setPoolsError(errorMessage)
        setLegacyImportError(errorMessage)
      } finally {
        if (!cancelled) {
          setPoolsLoading(false)
        }
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [legacyImportOpen])

  useEffect(() => {
    if (selectedDatabaseMetadataManagementPending) {
      setListLoading(true)
      return
    }

    let cancelled = false

    const load = async () => {
      setListLoading(true)
      setListError(null)
      setListReadFallbackUsed(false)

      try {
        const databaseIdForRead = shouldPreferUnscopedDecisionRead
          ? undefined
          : effectiveSelectedDatabaseId
        const { response, usedFallback } = await loadDecisionsCollection(databaseIdForRead)
        if (cancelled) return

        const items = filterDocumentPolicyDecisions(response.decisions ?? [])
        setDecisions(items)
        setSelectedDecisionId((current) => (
          current && items.some((decision) => decision.id === current)
            ? current
            : items[0]?.id ?? null
        ))
        setMetadataContext(response.metadata_context ?? null)
        setListReadFallbackUsed(usedFallback || shouldPreferUnscopedDecisionRead)
      } catch (error) {
        if (cancelled) return
        setListError(toErrorMessage(error, 'Failed to load decision table revisions.'))
        setDecisions([])
        setMetadataContext(null)
        setSelectedDecisionId(null)
      } finally {
        if (!cancelled) {
          setListLoading(false)
        }
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [
    effectiveSelectedDatabaseId,
    reloadTick,
    selectedDatabaseMetadataManagementPending,
    shouldPreferUnscopedDecisionRead,
  ])

  const decisionSnapshotFilter = useMemo(
    () => resolveDecisionSnapshotFilter({
      decisions,
      metadataContext,
      fallbackUsed: listReadFallbackUsed,
      mode: snapshotFilterMode,
    }),
    [decisions, listReadFallbackUsed, metadataContext, snapshotFilterMode],
  )

  const visibleDecisions = decisionSnapshotFilter.visibleDecisions

  useEffect(() => {
    if (listLoading) {
      return
    }

    const selectedDecisionIsVisible = Boolean(
      selectedDecisionId
      && visibleDecisions.some((decision) => decision.id === selectedDecisionId)
    )

    if (!selectedDecisionId || !selectedDecisionIsVisible) {
      setSelectedDecision(null)
      setDetailContext(null)
      setDetailError(null)
      setDetailReadFallbackUsed(false)
      setDetailLoading(false)
      return
    }

    let cancelled = false

    const load = async () => {
      setDetailLoading(true)
      setDetailError(null)
      setDetailReadFallbackUsed(false)

      try {
        const detailDatabaseId = listReadFallbackUsed ? undefined : effectiveSelectedDatabaseId
        const { response, usedFallback } = await loadDecisionDetail(selectedDecisionId, detailDatabaseId)
        if (cancelled) return
        setSelectedDecision(response.decision)
        setDetailContext(response.metadata_context ?? null)
        setDetailReadFallbackUsed(usedFallback)
      } catch (error) {
        if (cancelled) return
        setDetailError(toErrorMessage(error, 'Failed to load decision detail.'))
        setSelectedDecision(null)
        setDetailContext(null)
      } finally {
        if (!cancelled) {
          setDetailLoading(false)
        }
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [effectiveSelectedDatabaseId, listLoading, listReadFallbackUsed, selectedDecisionId, visibleDecisions])

  useEffect(() => {
    if (!legacyImportDraft || legacyImportDraft.poolId || pools.length === 0) return
    setLegacyImportDraft((current) => (
      current ? { ...current, poolId: pools[0].id } : current
    ))
  }, [legacyImportDraft, pools])

  useEffect(() => {
    if (!legacyImportDraft?.poolId) {
      setLegacyImportGraph(null)
      return
    }

    let cancelled = false

    const load = async () => {
      setLegacyImportGraphLoading(true)
      setLegacyImportError(null)

      try {
        const graph = await getPoolGraph(legacyImportDraft.poolId)
        if (cancelled) return
        setLegacyImportGraph(graph)
      } catch (error) {
        if (cancelled) return
        setLegacyImportGraph(null)
        setLegacyImportError(toErrorMessage(error, 'Failed to load pool topology for legacy import.'))
      } finally {
        if (!cancelled) {
          setLegacyImportGraphLoading(false)
        }
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [legacyImportDraft?.poolId])

  useEffect(() => {
    if (!legacyImportDraft) return

    const legacyEdgeIds = legacyImportGraph?.edges
      .filter((edge) => hasLegacyDocumentPolicy(edge.metadata))
      .map((edge) => edge.edge_version_id) ?? []

    if (legacyEdgeIds.length === 0) {
      if (!legacyImportDraft.edgeVersionId) return
      setLegacyImportDraft((current) => (
        current ? { ...current, edgeVersionId: '' } : current
      ))
      return
    }

    if (legacyImportDraft.edgeVersionId && legacyEdgeIds.includes(legacyImportDraft.edgeVersionId)) {
      return
    }

    setLegacyImportDraft((current) => (
      current ? { ...current, edgeVersionId: legacyEdgeIds[0] } : current
    ))
  }, [legacyImportDraft, legacyImportGraph])

  const selectedPolicy = useMemo(() => {
    if (!selectedDecision) return null
    try {
      return extractDocumentPolicyOutput(selectedDecision, { allowNonDefaultRuleId: true })
    } catch {
      return null
    }
  }, [selectedDecision])
  const hiddenDecisionCount = decisionSnapshotFilter.hiddenCount
  const decisionListTitle = decisionSnapshotFilter.canFilterBySnapshot
    ? `Decision revisions (${visibleDecisions.length} of ${decisions.length})`
    : `Decision revisions (${decisions.length})`
  const snapshotFilterMessage = decisionSnapshotFilter.canFilterBySnapshot
    ? (
      snapshotFilterMode === 'all'
        ? (
          hiddenDecisionCount > 0
            ? `Showing all ${decisions.length} revisions for diagnostics. ${hiddenDecisionCount} ${hiddenDecisionCount === 1 ? 'revision does' : 'revisions do'} not match the selected configuration.`
            : `Showing all ${decisions.length} revisions for diagnostics. All revisions match the selected configuration.`
        )
        : `Showing ${visibleDecisions.length} of ${decisions.length} revisions matching the selected configuration.`
    )
    : null

  const metadataContextWarning = metadataContextFallbackActive
    ? METADATA_CONTEXT_FALLBACK_MESSAGE
    : null

  useEffect(() => {
    setSnapshotFilterMode('matching_snapshot')
  }, [effectiveSelectedDatabaseId])

  useEffect(() => {
    if (listLoading) {
      return
    }

    setSelectedDecisionId((current) => (
      current && visibleDecisions.some((decision) => decision.id === current)
        ? current
        : visibleDecisions[0]?.id ?? null
    ))
  }, [listLoading, visibleDecisions])

  const openEditor = (_mode: DecisionEditorMode, draft: DecisionEditorState) => {
    setEditorDraft(draft)
    setEditorError(null)
    setLegacyImportDraft(null)
    setLegacyImportGraph(null)
    setLegacyImportError(null)
  }

  const closeEditor = () => {
    if (saving) return
    setEditorDraft(null)
    setEditorError(null)
  }

  const openLegacyImport = () => {
    setEditorDraft(null)
    setEditorError(null)
    setLegacyImportDraft(buildEmptyLegacyImportDraft(pools[0]?.id ?? ''))
    setLegacyImportGraph(null)
    setLegacyImportError(null)
  }

  const closeLegacyImport = () => {
    if (saving) return
    setLegacyImportDraft(null)
    setLegacyImportGraph(null)
    setLegacyImportError(null)
  }

  const openRawImport = () => {
    openEditor('import', buildEmptyDraft('import', 'raw'))
  }

  const handleOpenSelectedDecisionForEdit = () => {
    if (!selectedDecision) return
    if (metadataContextFallbackActive) {
      setEditorDraft(null)
      setEditorError(METADATA_CONTEXT_ACTION_BLOCKED_MESSAGE)
      setLegacyImportDraft(null)
      setLegacyImportGraph(null)
      setLegacyImportError(null)
      return
    }
    if (selectedDecisionRequiresRollover) {
      setEditorDraft(null)
      setEditorError('This revision is outside the selected target configuration. Use guided rollover to publish a new revision for the current database.')
      setLegacyImportDraft(null)
      setLegacyImportGraph(null)
      setLegacyImportError(null)
      return
    }

    try {
      openEditor('revise', buildDraftFromDecision(selectedDecision))
    } catch (error) {
      setEditorDraft(null)
      setEditorError(toErrorMessage(error, 'Selected decision cannot be opened in the editor.'))
      setLegacyImportDraft(null)
      setLegacyImportGraph(null)
      setLegacyImportError(null)
    }
  }

  const handleOpenSelectedDecisionForRollover = () => {
    if (!selectedDecision) return
    if (!effectiveSelectedDatabaseId || !selectedDatabaseLabel) {
      setEditorDraft(null)
      setEditorError('Select a target database before starting guided rollover.')
      setLegacyImportDraft(null)
      setLegacyImportGraph(null)
      setLegacyImportError(null)
      return
    }

    const targetSummary = buildEditorTargetSummary(rolloverTargetMetadataContext, {
      databaseId: effectiveSelectedDatabaseId,
      databaseLabel: selectedDatabaseLabel,
    })
    if (!targetSummary) {
      setEditorDraft(null)
      setEditorError(METADATA_CONTEXT_ROLLOVER_BLOCKED_MESSAGE)
      setLegacyImportDraft(null)
      setLegacyImportGraph(null)
      setLegacyImportError(null)
      return
    }

    try {
      openEditor(
        'rollover',
        buildDraftFromDecision(selectedDecision, {
          mode: 'rollover',
          targetDatabaseId: effectiveSelectedDatabaseId,
          targetSummary,
        }),
      )
    } catch (error) {
      setEditorDraft(null)
      setEditorError(toErrorMessage(error, 'Selected decision cannot be opened as a rollover source.'))
      setLegacyImportDraft(null)
      setLegacyImportGraph(null)
      setLegacyImportError(null)
    }
  }

  const handleEditorTabChange = (nextTab: DecisionEditorTab) => {
    if (!editorDraft || editorDraft.activeTab === nextTab) return

    if (nextTab === 'raw') {
      try {
        const rawJson = formatJson(buildDocumentPolicyFromBuilder(editorDraft.chains))
        setEditorDraft({ ...editorDraft, activeTab: 'raw', rawJson })
        setEditorError(null)
        return
      } catch {
        setEditorDraft({ ...editorDraft, activeTab: 'raw' })
        setEditorError(null)
        return
      }
    }

    try {
      const parsed = JSON.parse(editorDraft.rawJson || '{}')
      const chains = documentPolicyToBuilderChains(parsed)
      setEditorDraft({ ...editorDraft, activeTab: 'builder', chains })
      setEditorError(null)
    } catch (error) {
      setEditorError(toErrorMessage(error, 'Failed to parse raw document policy JSON.'))
    }
  }

  const handleSaveDecision = async () => {
    if (!editorDraft) return

    setSaving(true)
    setEditorError(null)

    try {
      const payload = buildDocumentPolicyDecisionPayload({
        database_id: editorDraft.targetDatabaseId ?? effectiveSelectedDatabaseId,
        decision_table_id: editorDraft.decisionTableId,
        name: editorDraft.name,
        description: editorDraft.description,
        chains: buildChainsFromDraft(editorDraft),
        parent_version_id: editorDraft.parentVersionId,
        is_active: editorDraft.isActive,
      })

      const response = await api.postDecisionsCollection(payload, DECISIONS_API_OPTIONS)
      const nextDecisionId = response?.decision?.id ?? null
      message.success(
        editorDraft.mode === 'rollover'
          ? 'Rollover revision created'
          : editorDraft.mode === 'revise'
            ? 'Decision revision created'
            : 'Decision saved',
      )
      setEditorDraft(null)
      setSelectedDecisionId(nextDecisionId)
      setReloadTick((value) => value + 1)
    } catch (error) {
      setEditorError(toErrorMessage(error, 'Failed to save decision.'))
    } finally {
      setSaving(false)
    }
  }

  const handleDeactivateSelected = async () => {
    if (!selectedDecision) return
    if (metadataContextFallbackActive) {
      setEditorError(METADATA_CONTEXT_ACTION_BLOCKED_MESSAGE)
      return
    }

    setSaving(true)
    setEditorError(null)

    try {
      const policy = extractDocumentPolicyOutput(selectedDecision, { allowNonDefaultRuleId: true })
      const payload = buildDocumentPolicyDecisionPayload({
        database_id: effectiveSelectedDatabaseId,
        decision_table_id: selectedDecision.decision_table_id,
        name: selectedDecision.name,
        description: selectedDecision.description ?? '',
        chains: documentPolicyToBuilderChains(policy),
        parent_version_id: selectedDecision.id,
        is_active: false,
      })

      await api.postDecisionsCollection(payload, DECISIONS_API_OPTIONS)
      message.warning('Decision deactivated')
      setReloadTick((value) => value + 1)
    } catch (error) {
      setEditorError(toErrorMessage(error, 'Failed to deactivate decision.'))
    } finally {
      setSaving(false)
    }
  }

  const handleImportLegacyEdge = async () => {
    if (!legacyImportDraft) return

    const poolId = legacyImportDraft.poolId.trim()
    const edgeVersionId = legacyImportDraft.edgeVersionId.trim()

    if (!poolId) {
      setLegacyImportError('Select a pool for legacy import.')
      return
    }
    if (!edgeVersionId) {
      setLegacyImportError('Select a topology edge with legacy document_policy metadata.')
      return
    }

    setSaving(true)
    setLegacyImportError(null)

    try {
      const payload = {
        edge_version_id: edgeVersionId,
        ...(legacyImportDraft.decisionTableId.trim()
          ? { decision_table_id: legacyImportDraft.decisionTableId.trim() }
          : {}),
        ...(legacyImportDraft.name.trim() ? { name: legacyImportDraft.name.trim() } : {}),
        ...(legacyImportDraft.description.trim()
          ? { description: legacyImportDraft.description.trim() }
          : {}),
      }

      const response = await migratePoolEdgeDocumentPolicy(poolId, payload)
      setLegacyImportResult(response)
      setSelectedDecisionId(response.decision.id || null)
      setLegacyImportDraft(null)
      setLegacyImportGraph(null)
      message.success(
        response.migration.binding_update_required
          ? 'Legacy policy imported to /decisions. Pin the resulting decision ref where needed.'
          : 'Legacy policy imported to /decisions.',
      )
      setReloadTick((value) => value + 1)
    } catch (error) {
      setLegacyImportError(toErrorMessage(error, 'Failed to import legacy document policy.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Space direction="vertical" size={4}>
        <Title level={2} style={{ marginBottom: 0 }}>Decision Policy Library</Title>
        <Text type="secondary">/decisions is the primary surface for document_policy authoring.</Text>
      </Space>

      {editorError && !editorDraft ? (
        <Alert
          type="error"
          showIcon
          message={editorError}
          action={editorError.includes('/databases') ? (
            <Button
              size="small"
              onClick={() => { navigate('/databases') }}
              data-testid="decisions-open-databases"
            >
              Открыть /databases
            </Button>
          ) : undefined}
        />
      ) : null}

      {legacyImportResult ? (
        <Alert
          closable
          showIcon
          type={legacyImportResult.migration.binding_update_required ? 'warning' : 'success'}
          message="Imported to /decisions"
          description={(
            <Space direction="vertical" size={4}>
              <span>
                {`Source: ${legacyImportResult.migration.source.source_path} (${legacyImportResult.migration.source.edge_version_id})`}
              </span>
              <span>
                {`Decision ref: ${legacyImportResult.migration.decision_ref.decision_table_id} r${legacyImportResult.migration.decision_ref.decision_revision}`}
              </span>
              <span>
                {`Binding slot: ${legacyImportResult.migration.slot_key}`}
              </span>
              {legacyImportResult.migration.binding_update_required ? (
                <span>Updated bindings: manual binding pin required</span>
              ) : (
                <span>Affected workflow bindings were updated automatically.</span>
              )}
            </Space>
          )}
          onClose={() => setLegacyImportResult(null)}
        />
      ) : null}

      <Card>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space wrap align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
            <Space wrap>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => openEditor('create', buildEmptyDraft('create', 'builder'))}
                disabled={saving}
                aria-label="New policy"
              >
                New policy
              </Button>
              <Button
                icon={<ImportOutlined />}
                onClick={openLegacyImport}
                disabled={saving}
                aria-label="Import legacy edge"
              >
                Import legacy edge
              </Button>
              <Button
                onClick={() => openEditor('import', buildEmptyDraft('import', 'raw'))}
                disabled={saving}
                aria-label="Import raw JSON"
              >
                Import raw JSON
              </Button>
                <Button
                  icon={<EditOutlined />}
                  onClick={handleOpenSelectedDecisionForEdit}
                  disabled={!selectedDecision || saving || selectedDecisionRequiresRollover || metadataContextFallbackActive}
                  aria-label="Edit selected decision"
                >
                  Edit selected decision
              </Button>
              <Button
                onClick={handleOpenSelectedDecisionForRollover}
                disabled={!selectedDecision || saving || !canOpenRollover}
                aria-label="Rollover selected revision"
              >
                Rollover selected revision
              </Button>
                <Button
                  danger
                  icon={<MinusCircleOutlined />}
                  onClick={() => void handleDeactivateSelected()}
                  disabled={!selectedDecision || saving || selectedDecisionRequiresRollover || metadataContextFallbackActive}
                  aria-label="Deactivate selected decision"
                >
                Deactivate selected decision
              </Button>
            </Space>

            <Select
              allowClear
              data-testid="decisions-database-select"
              placeholder="Select database"
              value={effectiveSelectedDatabaseId}
              style={{ minWidth: 260 }}
              options={databases.map((database) => ({
                value: database.id,
                label: `${database.name} (${database.base_name ?? database.version ?? database.id})`,
              }))}
              onChange={(nextValue) => setSelectedDatabaseId(nextValue ?? null)}
              loading={databasesQuery.isLoading}
            />
          </Space>

          <Descriptions
            size="small"
            column={{ xs: 1, md: 3 }}
            items={normalizeMetadataItems(metadataContext).map((item) => ({
              key: item.key,
              label: item.label,
              children: item.value,
            }))}
          />

          {metadataContextWarning ? (
            <Alert
              type="warning"
              showIcon
              message={metadataContextWarning}
              action={(
                <Button
                  size="small"
                  onClick={() => { navigate('/databases') }}
                  data-testid="decisions-warning-open-databases"
                >
                  Открыть /databases
                </Button>
              )}
            />
          ) : null}
        </Space>
      </Card>

      {listError ? <Alert type="error" showIcon message={listError} /> : null}

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(320px, 420px) minmax(0, 1fr)',
          gap: 24,
          alignItems: 'start',
        }}
      >
        <Card title={decisionListTitle}>
          {snapshotFilterMessage ? (
            <Alert
              type={snapshotFilterMode === 'all' ? 'info' : hiddenDecisionCount > 0 ? 'info' : 'success'}
              showIcon
              message={snapshotFilterMessage}
              description={(
                <Space wrap size={[8, 8]}>
                  <Text type="secondary">Selected configuration</Text>
                  <Tag>{decisionSnapshotFilter.selectedConfigurationLabel}</Tag>
                  {(hiddenDecisionCount > 0 || snapshotFilterMode === 'all') ? (
                    <Button
                      type="link"
                      onClick={() => setSnapshotFilterMode((current) => (
                        current === 'matching_snapshot' ? 'all' : 'matching_snapshot'
                      ))}
                    >
                      {snapshotFilterMode === 'all' ? 'Show matching configuration only' : 'Show all revisions'}
                    </Button>
                  ) : null}
                </Space>
              )}
              style={{ marginBottom: 16 }}
            />
          ) : null}
          {listLoading ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: '32px 0' }}>
              <Spin />
            </div>
          ) : visibleDecisions.length === 0 ? (
            <Empty
              description={decisionSnapshotFilter.canFilterBySnapshot
                ? 'No decision revisions match the selected configuration'
                : 'No decision revisions yet'}
            />
          ) : (
            <List
              dataSource={visibleDecisions}
              renderItem={(decision) => (
                <List.Item
                  style={{
                    cursor: 'pointer',
                    paddingInline: 0,
                    borderLeft: selectedDecisionId === decision.id ? '3px solid #1677ff' : '3px solid transparent',
                    paddingLeft: 12,
                  }}
                  onClick={() => setSelectedDecisionId(decision.id)}
                >
                  <Space direction="vertical" size={2} style={{ width: '100%' }}>
                    <Space wrap>
                      <Text strong>{decision.name}</Text>
                      <Tag color={decision.is_active ? 'green' : 'default'}>
                        {decision.is_active ? 'active' : 'inactive'}
                      </Tag>
                      {renderCompatibilityTag(decision.metadata_compatibility)}
                    </Space>
                    <Text type="secondary">{decision.decision_table_id}</Text>
                    <Text type="secondary">Revision {decision.decision_revision}</Text>
                  </Space>
                </List.Item>
              )}
            />
          )}
        </Card>

        <Card title={selectedDecision?.name || 'Decision detail'}>
          {detailError ? <Alert type="error" showIcon message={detailError} /> : null}
          {detailLoading ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: '32px 0' }}>
              <Spin />
            </div>
          ) : !selectedDecision ? (
            <Empty description="Select a decision revision to inspect metadata and output" />
          ) : (
            <Space direction="vertical" size="large" style={{ width: '100%' }}>
              <Descriptions
                size="small"
                column={{ xs: 1, md: 2 }}
                items={[
                  {
                    key: 'decision-table-id',
                    label: 'Decision table ID',
                    children: selectedDecision.decision_table_id,
                  },
                  {
                    key: 'decision-key',
                    label: 'Canonical key',
                    children: selectedDecision.decision_key,
                  },
                  {
                    key: 'revision',
                    label: 'Revision',
                    children: selectedDecision.decision_revision,
                  },
                  {
                    key: 'parent-version',
                    label: 'Parent version',
                    children: selectedDecision.parent_version || '—',
                  },
                  {
                    key: 'status',
                    label: 'Compatibility',
                    children: renderCompatibilityTag(selectedDecision.metadata_compatibility),
                  },
                ]}
              />

              <Descriptions
                size="small"
                column={{ xs: 1, md: 2 }}
                items={normalizeMetadataItems(selectedDecision.metadata_context ?? detailContext).map((item) => ({
                  key: `detail-${item.key}`,
                  label: item.label,
                  children: item.value,
                }))}
              />

              {selectedDecision.metadata_compatibility?.reason ? (
                <Alert
                  type="warning"
                  showIcon
                  message={selectedDecision.metadata_compatibility.reason}
                />
              ) : null}

              {selectedDecisionRequiresRollover ? (
                <Alert
                  type="info"
                  showIcon
                  message="This revision is outside the default compatible set for the selected database. Use Rollover selected revision to create a new revision for the current target metadata context."
                />
              ) : null}

              <div>
                <Space direction="vertical" size="small" style={{ width: '100%' }}>
                  <Text strong>Structured policy view</Text>
                  <Text type="secondary">
                    Browse the selected decision as chains, documents, field mappings, and table-part mappings.
                    Use Edit selected decision to save any changes as a new revision.
                  </Text>
                </Space>
                <div style={{ marginTop: 12 }}>
                  <DocumentPolicyViewer policy={selectedPolicy} />
                </div>
              </div>

              <div>
                <Text strong>Compiled document_policy JSON</Text>
                <div style={{ marginTop: 12 }}>
                  <LazyJsonCodeEditor
                    value={selectedPolicy ? formatJson(selectedPolicy) : '{}'}
                    onChange={() => {}}
                    readOnly
                    height={320}
                    title="Document policy output"
                    enableCopy
                  />
                </div>
              </div>
            </Space>
          )}
        </Card>
      </div>

      {legacyImportDraft ? (
        <DecisionLegacyImportPanel
          value={legacyImportDraft}
          pools={pools}
          poolsLoading={poolsLoading}
          graph={legacyImportGraph}
          graphLoading={legacyImportGraphLoading}
          error={legacyImportError}
          saving={saving}
          onCancel={closeLegacyImport}
          onOpenRawImport={openRawImport}
          onChange={(nextValue) => {
            setLegacyImportDraft(nextValue)
            setLegacyImportError(null)
          }}
          onImport={() => void handleImportLegacyEdge()}
        />
      ) : null}

      {editorDraft ? (
        <DecisionEditorPanel
          value={editorDraft}
          error={editorError}
          saving={saving}
          onCancel={closeEditor}
          onSave={() => void handleSaveDecision()}
          onChange={setEditorDraft}
          onTabChange={handleEditorTabChange}
        />
      ) : null}
    </Space>
  )
}

export default DecisionsPage

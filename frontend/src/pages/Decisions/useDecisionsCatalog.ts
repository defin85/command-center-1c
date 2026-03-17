import { useEffect, useMemo, useState, type Dispatch, type SetStateAction } from 'react'

import type { DecisionTable, PoolODataMetadataCatalogResponse } from '../../api/generated/model'
import { listOrganizationPools, type OrganizationPool } from '../../api/intercompanyPools'
import { useDatabaseMetadataManagement, useDatabases } from '../../api/queries/databases'
import { extractDocumentPolicyOutput } from './documentPolicyBuilder'
import {
  isDecisionPinnedInBinding,
  isDocumentPolicyDecision,
  resolveDecisionSnapshotFilter,
  type DecisionSnapshotFilterMode,
} from './decisionSnapshotFilter'
import {
  buildEditorTargetSummary,
  collectPinnedDecisionRefs,
  formatDatabaseOptionLabel,
  loadDecisionDetail,
  loadDecisionsCollection,
  METADATA_CONTEXT_FALLBACK_MESSAGE,
  shouldPreferUnscopedReadFromMetadataManagement,
  toErrorMessage,
} from './decisionPageUtils'

type DecisionsCatalogState = {
  databases: Array<{ id: string; name?: string | null; base_name?: string | null; version?: string | null }>
  databasesQuery: ReturnType<typeof useDatabases>
  selectedDatabaseId: string | null | undefined
  setSelectedDatabaseId: Dispatch<SetStateAction<string | null | undefined>>
  effectiveSelectedDatabaseId: string | undefined
  selectedDatabaseLabel: string
  metadataContext: PoolODataMetadataCatalogResponse | null
  detailContext: PoolODataMetadataCatalogResponse | null
  listLoading: boolean
  detailLoading: boolean
  listError: string | null
  detailError: string | null
  bindingUsageError: string | null
  selectedDecisionId: string | null
  setSelectedDecisionId: Dispatch<SetStateAction<string | null>>
  selectedDecision: DecisionTable | null
  visibleDecisions: DecisionTable[]
  decisionListTitle: string
  snapshotFilterMessage: string | null
  snapshotFilterMode: DecisionSnapshotFilterMode
  setSnapshotFilterMode: Dispatch<SetStateAction<DecisionSnapshotFilterMode>>
  hiddenDecisionCount: number
  canFilterBySnapshot: boolean
  selectedConfigurationLabel: string
  pinnedDecisionRefs: ReturnType<typeof collectPinnedDecisionRefs>
  selectedPolicy: ReturnType<typeof extractDocumentPolicyOutput> | null
  selectedDecisionSupportsDocumentPolicyAuthoring: boolean
  selectedDecisionPinnedInBinding: boolean
  selectedDecisionRequiresRollover: boolean
  metadataContextFallbackActive: boolean
  metadataContextWarning: string | null
  canOpenRollover: boolean
  rolloverTargetMetadataContext: PoolODataMetadataCatalogResponse | null
  reloadCatalog: () => void
}

export function useDecisionsCatalog(): DecisionsCatalogState {
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
  const [bindingUsagePools, setBindingUsagePools] = useState<OrganizationPool[]>([])
  const [bindingUsageError, setBindingUsageError] = useState<string | null>(null)
  const [listReadFallbackUsed, setListReadFallbackUsed] = useState(false)
  const [detailReadFallbackUsed, setDetailReadFallbackUsed] = useState(false)
  const [snapshotFilterMode, setSnapshotFilterMode] = useState<DecisionSnapshotFilterMode>('matching_snapshot')
  const [reloadTick, setReloadTick] = useState(0)
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
  const shouldPreferUnscopedDecisionRead = Boolean(
    effectiveSelectedDatabaseId
    && shouldPreferUnscopedReadFromMetadataManagement(selectedDatabaseMetadataManagement),
  )

  useEffect(() => {
    if (selectedDatabaseId !== undefined || databases.length === 0) return
    setSelectedDatabaseId(databases[0].id)
  }, [databases, selectedDatabaseId])

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

        const items = response.decisions ?? []
        setDecisions(items)
        setSelectedDecisionId((current) => (
          current && items.some((decision) => decision.id === current)
            ? current
            : null
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

  const pinnedDecisionRefs = useMemo(
    () => collectPinnedDecisionRefs(bindingUsagePools),
    [bindingUsagePools],
  )
  const hasNonDocumentPolicyDecisions = useMemo(
    () => decisions.some((decision) => !isDocumentPolicyDecision(decision)),
    [decisions],
  )

  useEffect(() => {
    if (!hasNonDocumentPolicyDecisions) {
      setBindingUsagePools([])
      setBindingUsageError(null)
      return
    }

    let cancelled = false

    const load = async () => {
      setBindingUsageError(null)

      try {
        const items = await listOrganizationPools()
        if (cancelled) return
        setBindingUsagePools(items)
      } catch (error) {
        if (cancelled) return
        setBindingUsagePools([])
        setBindingUsageError(
          toErrorMessage(error, 'Failed to load workflow binding usage. Decisions pinned in bindings may be hidden.')
        )
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [hasNonDocumentPolicyDecisions, reloadTick])

  const decisionSnapshotFilter = useMemo(
    () => resolveDecisionSnapshotFilter({
      decisions,
      metadataContext,
      fallbackUsed: listReadFallbackUsed,
      mode: snapshotFilterMode,
      pinnedDecisionRefs,
    }),
    [decisions, listReadFallbackUsed, metadataContext, pinnedDecisionRefs, snapshotFilterMode],
  )

  const visibleDecisions = decisionSnapshotFilter.visibleDecisions

  useEffect(() => {
    if (listLoading) {
      return
    }

    setSelectedDecisionId((current) => (
      current && visibleDecisions.some((decision) => decision.id === current)
        ? current
        : (
          visibleDecisions.find((decision) => isDocumentPolicyDecision(decision))?.id
          ?? visibleDecisions[0]?.id
          ?? null
        )
    ))
  }, [listLoading, visibleDecisions])

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
    setSnapshotFilterMode('matching_snapshot')
  }, [effectiveSelectedDatabaseId])

  const rolloverTargetMetadataContext = detailContext ?? metadataContext
  const selectedDecisionSupportsDocumentPolicyAuthoring = Boolean(
    selectedDecision && isDocumentPolicyDecision(selectedDecision),
  )
  const selectedDecisionPinnedInBinding = Boolean(
    selectedDecision && isDecisionPinnedInBinding(selectedDecision, pinnedDecisionRefs),
  )
  const selectedDecisionRequiresRollover = Boolean(
    selectedDecisionSupportsDocumentPolicyAuthoring
    && selectedDecision?.metadata_compatibility?.is_compatible === false,
  )
  const metadataContextFallbackActive = Boolean(effectiveSelectedDatabaseId && (listReadFallbackUsed || detailReadFallbackUsed))
  const canOpenRollover = Boolean(
    selectedDecisionSupportsDocumentPolicyAuthoring
    && effectiveSelectedDatabaseId
    && !metadataContextFallbackActive
    && buildEditorTargetSummary(rolloverTargetMetadataContext, {
      databaseId: effectiveSelectedDatabaseId,
      databaseLabel: selectedDatabaseLabel,
    }),
  )

  const selectedPolicy = useMemo(() => {
    if (!selectedDecision) return null
    try {
      return extractDocumentPolicyOutput(selectedDecision, { allowNonDefaultRuleId: true })
    } catch {
      return null
    }
  }, [selectedDecision])

  const hiddenDecisionCount = decisionSnapshotFilter.hiddenCount
  const pinnedVisibleDecisionCount = decisionSnapshotFilter.pinnedVisibleCount
  const decisionListTitle = decisionSnapshotFilter.canFilterBySnapshot
    ? `Decision revisions (${visibleDecisions.length} of ${decisions.length})`
    : `Decision revisions (${decisions.length})`
  const snapshotFilterMessage = decisionSnapshotFilter.canFilterBySnapshot
    ? (
      snapshotFilterMode === 'all'
        ? (
          hiddenDecisionCount > 0
            ? `Showing all ${decisions.length} revisions for diagnostics. ${hiddenDecisionCount} ${hiddenDecisionCount === 1 ? 'revision is' : 'revisions are'} outside the selected configuration and not pinned in workflow bindings.`
            : `Showing all ${decisions.length} revisions for diagnostics. All revisions match the selected configuration.`
        )
        : (
          pinnedVisibleDecisionCount > 0
            ? `Showing ${visibleDecisions.length} of ${decisions.length} revisions matching the selected configuration or pinned in workflow bindings.`
            : `Showing ${visibleDecisions.length} of ${decisions.length} revisions matching the selected configuration.`
        )
    )
    : null

  const metadataContextWarning = metadataContextFallbackActive
    ? METADATA_CONTEXT_FALLBACK_MESSAGE
    : null

  return {
    databases,
    databasesQuery,
    selectedDatabaseId,
    setSelectedDatabaseId,
    effectiveSelectedDatabaseId,
    selectedDatabaseLabel,
    metadataContext,
    detailContext,
    listLoading,
    detailLoading,
    listError,
    detailError,
    bindingUsageError,
    selectedDecisionId,
    setSelectedDecisionId,
    selectedDecision,
    visibleDecisions,
    decisionListTitle,
    snapshotFilterMessage,
    snapshotFilterMode,
    setSnapshotFilterMode,
    hiddenDecisionCount,
    canFilterBySnapshot: decisionSnapshotFilter.canFilterBySnapshot,
    selectedConfigurationLabel: decisionSnapshotFilter.selectedConfigurationLabel,
    pinnedDecisionRefs,
    selectedPolicy,
    selectedDecisionSupportsDocumentPolicyAuthoring,
    selectedDecisionPinnedInBinding,
    selectedDecisionRequiresRollover,
    metadataContextFallbackActive,
    metadataContextWarning,
    canOpenRollover,
    rolloverTargetMetadataContext,
    reloadCatalog: () => setReloadTick((value) => value + 1),
  }
}

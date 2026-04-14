import { useEffect, useMemo, useRef, useState, type Dispatch, type SetStateAction } from 'react'
import { useSearchParams } from 'react-router-dom'

import type { DecisionTable, PoolODataMetadataCatalogResponse } from '../../api/generated/model'
import { listOrganizationPools, type OrganizationPool } from '../../api/intercompanyPools'
import { useDecisionsTranslation } from '../../i18n'
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
  type MetadataContextLike,
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
  detailContext: MetadataContextLike
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
  selectDatabase: (databaseId: string | null) => void
  selectDecision: (decisionId: string) => void
  toggleSnapshotFilterMode: () => void
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
  rolloverTargetMetadataContext: MetadataContextLike
  reloadCatalog: () => void
}

const normalizeRouteParam = (value: string | null): string | null => {
  const normalized = value?.trim() ?? ''
  return normalized.length > 0 ? normalized : null
}

const resolveStateUpdate = <T,>(current: T, next: SetStateAction<T>): T => (
  typeof next === 'function'
    ? (next as (value: T) => T)(current)
    : next
)

const parseSnapshotFilterMode = (value: string | null): DecisionSnapshotFilterMode => (
  value === 'all' ? 'all' : 'matching_snapshot'
)

export function useDecisionsCatalog(): DecisionsCatalogState {
  const { t } = useDecisionsTranslation()
  const [searchParams, setSearchParams] = useSearchParams()
  const routeUpdateModeRef = useRef<'push' | 'replace'>('replace')
  const pendingRouteSyncRef = useRef<{
    selectedDatabaseId: string | null | undefined
    selectedDecisionId: string | null
    snapshotFilterMode: DecisionSnapshotFilterMode
  } | null>(null)
  const databaseFromUrl = normalizeRouteParam(searchParams.get('database'))
  const decisionFromUrl = normalizeRouteParam(searchParams.get('decision'))
  const snapshotModeFromUrl = parseSnapshotFilterMode(searchParams.get('snapshot'))
  const databasesQuery = useDatabases({ filters: { limit: 500, offset: 0 } })
  const databases = useMemo(
    () => databasesQuery.data?.databases ?? [],
    [databasesQuery.data?.databases],
  )
  const [selectedDatabaseIdState, setSelectedDatabaseIdState] = useState<string | null | undefined>(
    () => databaseFromUrl ?? undefined
  )
  const [decisions, setDecisions] = useState<DecisionTable[]>([])
  const [selectedDecisionIdState, setSelectedDecisionIdState] = useState<string | null>(
    () => decisionFromUrl
  )
  const [selectedDecision, setSelectedDecision] = useState<DecisionTable | null>(null)
  const [metadataContext, setMetadataContext] = useState<PoolODataMetadataCatalogResponse | null>(null)
  const [detailContext, setDetailContext] = useState<MetadataContextLike>(null)
  const [listLoading, setListLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [listError, setListError] = useState<string | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [bindingUsagePools, setBindingUsagePools] = useState<OrganizationPool[]>([])
  const [bindingUsageError, setBindingUsageError] = useState<string | null>(null)
  const [listReadFallbackUsed, setListReadFallbackUsed] = useState(false)
  const [detailReadFallbackUsed, setDetailReadFallbackUsed] = useState(false)
  const [snapshotFilterModeState, setSnapshotFilterModeState] = useState<DecisionSnapshotFilterMode>(
    () => snapshotModeFromUrl
  )
  const [reloadTick, setReloadTick] = useState(0)
  const selectedDatabaseIdRef = useRef<string | null | undefined>(selectedDatabaseIdState)
  const selectedDatabaseId = selectedDatabaseIdState
  const selectedDecisionId = selectedDecisionIdState
  const snapshotFilterMode = snapshotFilterModeState
  selectedDatabaseIdRef.current = selectedDatabaseId
  const effectiveSelectedDatabaseId = selectedDatabaseId ?? undefined
  const databaseSelectionPending = selectedDatabaseId === undefined
  const setSelectedDatabaseId = ((next) => {
    setSelectedDatabaseIdState((current) => resolveStateUpdate(current, next))
  }) as Dispatch<SetStateAction<string | null | undefined>>
  const setSelectedDecisionId = ((next) => {
    setSelectedDecisionIdState((current) => resolveStateUpdate(current, next))
  }) as Dispatch<SetStateAction<string | null>>
  const setSnapshotFilterMode = ((next) => {
    setSnapshotFilterModeState((current) => resolveStateUpdate(current, next))
  }) as Dispatch<SetStateAction<DecisionSnapshotFilterMode>>
  const selectDatabase = (databaseId: string | null) => {
    routeUpdateModeRef.current = 'push'
    setSnapshotFilterModeState('matching_snapshot')
    setSelectedDatabaseIdState(databaseId)
    setSelectedDecisionIdState(null)
  }
  const selectDecision = (decisionId: string) => {
    routeUpdateModeRef.current = 'push'
    setSelectedDecisionIdState(decisionId)
  }
  const toggleSnapshotFilterMode = () => {
    routeUpdateModeRef.current = 'push'
    setSnapshotFilterModeState((current) => (
      current === 'matching_snapshot' ? 'all' : 'matching_snapshot'
    ))
  }

  useEffect(() => {
    const nextSelectedDatabaseId = databaseFromUrl
      ? databaseFromUrl
      : (selectedDatabaseIdRef.current === undefined ? undefined : null)

    pendingRouteSyncRef.current = {
      selectedDatabaseId: nextSelectedDatabaseId,
      selectedDecisionId: decisionFromUrl,
      snapshotFilterMode: snapshotModeFromUrl,
    }

    setSelectedDatabaseIdState((current) => (
      current === nextSelectedDatabaseId ? current : nextSelectedDatabaseId
    ))
    setSelectedDecisionIdState((current) => (
      current === decisionFromUrl ? current : decisionFromUrl
    ))
    setSnapshotFilterModeState((current) => (
      current === snapshotModeFromUrl ? current : snapshotModeFromUrl
    ))
  }, [databaseFromUrl, decisionFromUrl, snapshotModeFromUrl])

  useEffect(() => {
    const pendingRouteSync = pendingRouteSyncRef.current
    if (pendingRouteSync) {
      const databaseMatches = selectedDatabaseId === pendingRouteSync.selectedDatabaseId
      const decisionMatches = selectedDecisionId === pendingRouteSync.selectedDecisionId
      const snapshotMatches = snapshotFilterMode === pendingRouteSync.snapshotFilterMode

      if (!databaseMatches || !decisionMatches || !snapshotMatches) {
        return
      }

      pendingRouteSyncRef.current = null
      return
    }

    const next = new URLSearchParams(searchParams)

    if (selectedDatabaseId) {
      next.set('database', selectedDatabaseId)
    } else {
      next.delete('database')
    }

    if (selectedDecisionId) {
      next.set('decision', selectedDecisionId)
    } else {
      next.delete('decision')
    }

    if (snapshotFilterMode === 'matching_snapshot') {
      next.delete('snapshot')
    } else {
      next.set('snapshot', snapshotFilterMode)
    }

    if (next.toString() !== searchParams.toString()) {
      setSearchParams(
        next,
        routeUpdateModeRef.current === 'replace'
          ? { replace: true }
          : undefined
      )
    }
    routeUpdateModeRef.current = 'replace'
  }, [
    searchParams,
    selectedDatabaseId,
    selectedDecisionId,
    setSearchParams,
    snapshotFilterMode,
  ])

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
    if (selectedDatabaseId !== undefined || databasesQuery.isLoading) return
    routeUpdateModeRef.current = 'replace'
    setSelectedDatabaseId(databases[0]?.id ?? null)
  }, [databases, databasesQuery.isLoading, selectedDatabaseId])

  useEffect(() => {
    if (databaseSelectionPending) {
      setListLoading(true)
      return
    }

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
        routeUpdateModeRef.current = 'replace'
        setSelectedDecisionId((current) => (
          current && items.some((decision) => decision.id === current)
            ? current
            : null
        ))
        setMetadataContext(response.metadata_context ?? null)
        setListReadFallbackUsed(usedFallback || shouldPreferUnscopedDecisionRead)
      } catch (error) {
        if (cancelled) return
        setListError(toErrorMessage(error, t(($) => $.page.listError)))
        setDecisions([])
        setMetadataContext(null)
        routeUpdateModeRef.current = 'replace'
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
    databaseSelectionPending,
    databasesQuery.isLoading,
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
  const shouldLoadBindingUsage = hasNonDocumentPolicyDecisions && snapshotFilterMode === 'all'

  useEffect(() => {
    if (!shouldLoadBindingUsage) {
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
          toErrorMessage(error, t(($) => $.page.bindingUsageError))
        )
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [reloadTick, shouldLoadBindingUsage])

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

    routeUpdateModeRef.current = 'replace'
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

    const summaryDecision = visibleDecisions.find((decision) => decision.id === selectedDecisionId) ?? null
    setSelectedDecision(summaryDecision)
    setDetailContext(summaryDecision?.metadata_context ?? null)

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
        setDetailError(toErrorMessage(error, t(($) => $.messages.detailLoadFailed)))
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
    ? t(($) => $.listTitle.filtered, {
      visible: String(visibleDecisions.length),
      total: String(decisions.length),
    })
    : t(($) => $.listTitle.all, { total: String(decisions.length) })
  const snapshotFilterMessage = decisionSnapshotFilter.canFilterBySnapshot
    ? (
      snapshotFilterMode === 'all'
        ? (
          hiddenDecisionCount > 0
            ? (
              hiddenDecisionCount === 1
                ? t(($) => $.snapshot.allOutsideSingle, {
                  total: String(decisions.length),
                  hidden: String(hiddenDecisionCount),
                })
                : t(($) => $.snapshot.allOutsideMany, {
                  total: String(decisions.length),
                  hidden: String(hiddenDecisionCount),
                })
            )
            : t(($) => $.snapshot.allMatching, { total: String(decisions.length) })
        )
        : (
          pinnedVisibleDecisionCount > 0
            ? t(($) => $.snapshot.matchingPinned, {
              visible: String(visibleDecisions.length),
              total: String(decisions.length),
            })
            : t(($) => $.snapshot.matching, {
              visible: String(visibleDecisions.length),
              total: String(decisions.length),
            })
        )
    )
    : null

  const metadataContextWarning = metadataContextFallbackActive
    ? t(($) => $.messages.metadataContextFallback)
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
    selectDatabase,
    selectDecision,
    toggleSnapshotFilterMode,
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

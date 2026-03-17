import { useEffect, useState } from 'react'

import { getPoolGraph, listOrganizationPools, migratePoolEdgeDocumentPolicy, type PoolDocumentPolicyMigrationResponse } from '../../api/intercompanyPools'
import type { DecisionLegacyImportState } from './DecisionLegacyImportPanel'
import {
  buildEmptyLegacyImportDraft,
  hasLegacyDocumentPolicy,
  toErrorMessage,
} from './decisionPageUtils'

type MessageLike = {
  success: (content: string) => void
}

type UseDecisionLegacyImportArgs = {
  message: MessageLike
  onImportComplete: (decisionId: string | null) => void
}

export function useDecisionLegacyImport({
  message,
  onImportComplete,
}: UseDecisionLegacyImportArgs) {
  const [legacyImportDraft, setLegacyImportDraft] = useState<DecisionLegacyImportState | null>(null)
  const [legacyImportGraph, setLegacyImportGraph] = useState<Awaited<ReturnType<typeof getPoolGraph>> | null>(null)
  const [legacyImportGraphLoading, setLegacyImportGraphLoading] = useState(false)
  const [legacyImportError, setLegacyImportError] = useState<string | null>(null)
  const [legacyImportResult, setLegacyImportResult] = useState<PoolDocumentPolicyMigrationResponse | null>(null)
  const [pools, setPools] = useState<Awaited<ReturnType<typeof listOrganizationPools>>>([])
  const [poolsLoading, setPoolsLoading] = useState(false)
  const [, setPoolsError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const legacyImportOpen = Boolean(legacyImportDraft)

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

  const openLegacyImport = () => {
    setLegacyImportDraft(buildEmptyLegacyImportDraft())
    setLegacyImportGraph(null)
    setLegacyImportError(null)
  }

  const closeLegacyImport = () => {
    if (saving) return
    setLegacyImportDraft(null)
    setLegacyImportGraph(null)
    setLegacyImportError(null)
  }

  const resetLegacyImport = () => {
    if (saving) return
    setLegacyImportDraft(null)
    setLegacyImportGraph(null)
    setLegacyImportError(null)
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
      setLegacyImportDraft(null)
      setLegacyImportGraph(null)
      message.success(
        response.migration.binding_update_required
          ? 'Legacy policy imported to /decisions. Pin the resulting decision ref where needed.'
          : 'Legacy policy imported to /decisions.',
      )
      onImportComplete(response.decision.id || null)
    } catch (error) {
      setLegacyImportError(toErrorMessage(error, 'Failed to import legacy document policy.'))
    } finally {
      setSaving(false)
    }
  }

  return {
    legacyImportDraft,
    setLegacyImportDraft,
    legacyImportGraph,
    legacyImportGraphLoading,
    legacyImportError,
    setLegacyImportError,
    legacyImportResult,
    setLegacyImportResult,
    pools,
    poolsLoading,
    saving,
    openLegacyImport,
    closeLegacyImport,
    resetLegacyImport,
    handleImportLegacyEdge,
  }
}

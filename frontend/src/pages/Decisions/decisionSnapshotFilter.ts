import type {
  DecisionRevisionMetadataContext,
  PoolODataMetadataCatalogResponse,
} from '../../api/generated/model'
import type { DecisionTable } from '../../api/generated/model/decisionTable'

export type DecisionSnapshotFilterMode = 'matching_snapshot' | 'all'

export type PinnedDecisionRefs = {
  decisionIds: readonly string[]
  decisionTableKeys: readonly string[]
}

type MetadataContextLike =
  | PoolODataMetadataCatalogResponse
  | DecisionRevisionMetadataContext
  | null
  | undefined

type NormalizedMetadataSnapshot = {
  configName: string
  configVersion: string
  metadataHash: string
}

export type DecisionSnapshotFilterResult = {
  canFilterBySnapshot: boolean
  visibleDecisions: DecisionTable[]
  hiddenCount: number
  pinnedVisibleCount: number
  selectedConfigurationLabel: string
}

const trimString = (value: unknown): string => (
  typeof value === 'string' ? value.trim() : ''
)

export const isDocumentPolicyDecision = (decision: DecisionTable): boolean => (
  trimString(decision.decision_key) === 'document_policy'
)

export const buildDecisionBindingRefKey = (
  decisionKey: string | null | undefined,
  decisionTableId: string | null | undefined,
): string => {
  const normalizedDecisionKey = trimString(decisionKey)
  const normalizedDecisionTableId = trimString(decisionTableId)
  if (!normalizedDecisionKey || !normalizedDecisionTableId) {
    return ''
  }
  return `${normalizedDecisionKey}::${normalizedDecisionTableId}`
}

export const isDecisionPinnedInBinding = (
  decision: DecisionTable,
  pinnedDecisionRefs: PinnedDecisionRefs,
): boolean => {
  const decisionId = trimString(decision.id)
  if (decisionId && pinnedDecisionRefs.decisionIds.some((value) => trimString(value) === decisionId)) {
    return true
  }

  const bindingRefKey = buildDecisionBindingRefKey(decision.decision_key, decision.decision_table_id)
  if (!bindingRefKey) {
    return false
  }
  return pinnedDecisionRefs.decisionTableKeys.some((value) => trimString(value) === bindingRefKey)
}

const normalizeMetadataSnapshot = (
  metadata: MetadataContextLike
): NormalizedMetadataSnapshot | null => {
  if (!metadata) return null

  const configName = trimString(metadata.config_name)
  const configVersion = trimString(metadata.config_version)
  if (!configName || !configVersion) return null

  const metadataHash = trimString(metadata.metadata_hash)

  return {
    configName,
    configVersion,
    metadataHash,
  }
}

export const decisionMatchesMetadataSnapshot = (
  decision: DecisionTable,
  metadataContext: MetadataContextLike
): boolean => {
  if (!isDocumentPolicyDecision(decision)) {
    return true
  }

  const currentSnapshot = normalizeMetadataSnapshot(metadataContext)
  if (!currentSnapshot) {
    return true
  }

  const storedSnapshot = normalizeMetadataSnapshot(decision.metadata_context)
  if (!storedSnapshot) {
    return false
  }

  return (
    storedSnapshot.configName === currentSnapshot.configName
    && storedSnapshot.configVersion === currentSnapshot.configVersion
  )
}

export const resolveDecisionSnapshotFilter = ({
  decisions,
  metadataContext,
  fallbackUsed,
  mode,
  pinnedDecisionRefs,
}: {
  decisions: DecisionTable[]
  metadataContext: MetadataContextLike
  fallbackUsed: boolean
  mode: DecisionSnapshotFilterMode
  pinnedDecisionRefs: PinnedDecisionRefs
}): DecisionSnapshotFilterResult => {
  const isVisibleInMatchingMode = (decision: DecisionTable): boolean => {
    if (isDecisionPinnedInBinding(decision, pinnedDecisionRefs)) {
      return true
    }
    if (!isDocumentPolicyDecision(decision)) {
      return false
    }
    return decisionMatchesMetadataSnapshot(decision, metadataContext)
  }

  const pinnedVisibleCount = decisions.filter((decision) => (
    isDecisionPinnedInBinding(decision, pinnedDecisionRefs)
  )).length

  const currentSnapshot = normalizeMetadataSnapshot(metadataContext)
  if (!currentSnapshot || fallbackUsed) {
    return {
      canFilterBySnapshot: false,
      visibleDecisions: decisions,
      hiddenCount: 0,
      pinnedVisibleCount,
      selectedConfigurationLabel: '',
    }
  }

  if (mode === 'all') {
    const hiddenCount = decisions
      .filter((decision) => !isVisibleInMatchingMode(decision))
      .length
    return {
      canFilterBySnapshot: true,
      visibleDecisions: decisions,
      hiddenCount,
      pinnedVisibleCount,
      selectedConfigurationLabel: `${currentSnapshot.configName} (${currentSnapshot.configVersion})`,
    }
  }

  const visibleDecisions = decisions
    .filter((decision) => isVisibleInMatchingMode(decision))
  return {
    canFilterBySnapshot: true,
    visibleDecisions,
    hiddenCount: Math.max(decisions.length - visibleDecisions.length, 0),
    pinnedVisibleCount,
    selectedConfigurationLabel: `${currentSnapshot.configName} (${currentSnapshot.configVersion})`,
  }
}

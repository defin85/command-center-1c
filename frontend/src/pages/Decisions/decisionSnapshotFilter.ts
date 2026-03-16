import type {
  DecisionRevisionMetadataContext,
  DecisionTable,
  PoolODataMetadataCatalogResponse,
} from '../../api/generated/model'

export type DecisionSnapshotFilterMode = 'matching_snapshot' | 'all'

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
  selectedConfigurationLabel: string
}

const trimString = (value: unknown): string => (
  typeof value === 'string' ? value.trim() : ''
)

export const isDocumentPolicyDecision = (decision: DecisionTable): boolean => (
  trimString(decision.decision_key) === 'document_policy'
)

export const filterDocumentPolicyDecisions = (decisions: DecisionTable[]): DecisionTable[] => (
  decisions.filter(isDocumentPolicyDecision)
)

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
}: {
  decisions: DecisionTable[]
  metadataContext: MetadataContextLike
  fallbackUsed: boolean
  mode: DecisionSnapshotFilterMode
}): DecisionSnapshotFilterResult => {
  const documentPolicyDecisions = filterDocumentPolicyDecisions(decisions)

  const currentSnapshot = normalizeMetadataSnapshot(metadataContext)
  if (!currentSnapshot || fallbackUsed) {
    return {
      canFilterBySnapshot: false,
      visibleDecisions: documentPolicyDecisions,
      hiddenCount: 0,
      selectedConfigurationLabel: '',
    }
  }

  if (mode === 'all') {
    const hiddenCount = documentPolicyDecisions
      .filter((decision) => !decisionMatchesMetadataSnapshot(decision, metadataContext))
      .length
    return {
      canFilterBySnapshot: true,
      visibleDecisions: documentPolicyDecisions,
      hiddenCount,
      selectedConfigurationLabel: `${currentSnapshot.configName} (${currentSnapshot.configVersion})`,
    }
  }

  const visibleDecisions = documentPolicyDecisions
    .filter((decision) => decisionMatchesMetadataSnapshot(decision, metadataContext))
  return {
    canFilterBySnapshot: true,
    visibleDecisions,
    hiddenCount: Math.max(documentPolicyDecisions.length - visibleDecisions.length, 0),
    selectedConfigurationLabel: `${currentSnapshot.configName} (${currentSnapshot.configVersion})`,
  }
}

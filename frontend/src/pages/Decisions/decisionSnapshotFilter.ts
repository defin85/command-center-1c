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

const isMetadataAwareDocumentPolicy = (decision: DecisionTable): boolean => (
  trimString(decision.decision_key) === 'document_policy'
)

export const decisionMatchesMetadataSnapshot = (
  decision: DecisionTable,
  metadataContext: MetadataContextLike
): boolean => {
  if (!isMetadataAwareDocumentPolicy(decision)) {
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
  const currentSnapshot = normalizeMetadataSnapshot(metadataContext)
  if (!currentSnapshot || fallbackUsed) {
    return {
      canFilterBySnapshot: false,
      visibleDecisions: decisions,
      hiddenCount: 0,
      selectedConfigurationLabel: '',
    }
  }

  if (mode === 'all') {
    const hiddenCount = decisions.filter((decision) => !decisionMatchesMetadataSnapshot(decision, metadataContext)).length
    return {
      canFilterBySnapshot: true,
      visibleDecisions: decisions,
      hiddenCount,
      selectedConfigurationLabel: `${currentSnapshot.configName} (${currentSnapshot.configVersion})`,
    }
  }

  const visibleDecisions = decisions.filter((decision) => decisionMatchesMetadataSnapshot(decision, metadataContext))
  return {
    canFilterBySnapshot: true,
    visibleDecisions,
    hiddenCount: Math.max(decisions.length - visibleDecisions.length, 0),
    selectedConfigurationLabel: `${currentSnapshot.configName} (${currentSnapshot.configVersion})`,
  }
}

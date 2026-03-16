import type { AvailableDecisionRevision } from '../../types/workflow'

const trimString = (value: unknown): string => (
  typeof value === 'string' ? value.trim() : ''
)

export const isDecisionAvailableByDefault = (
  decision: AvailableDecisionRevision
): boolean => decision.metadataCompatibility?.is_compatible !== false

export const formatAvailableDecisionLabel = (
  decision: AvailableDecisionRevision
): string => {
  const decisionKey = trimString(decision.decisionKey)
  const decisionIdentity = trimString(decision.decisionTableId)
  const decisionTypeSuffix = decisionKey && decisionKey !== 'document_policy'
    ? ` (${decisionKey})`
    : ''
  const baseLabel = `${decision.name} · ${decisionIdentity}${decisionTypeSuffix} · r${decision.decisionRevision}`
  const configName = trimString(decision.metadataContext?.config_name)
  const configVersion = trimString(decision.metadataContext?.config_version)
  const configLabel = configName && configVersion
    ? `${configName} ${configVersion}`
    : ''
  const hasPublicationDrift = decision.metadataContext?.publication_drift === true
    || decision.metadataCompatibility?.reason === 'metadata_surface_diverged'

  const suffixes = [configLabel]
  if (hasPublicationDrift) {
    suffixes.push('drift')
  }

  const normalizedSuffixes = suffixes.filter(Boolean)
  if (normalizedSuffixes.length === 0) {
    return baseLabel
  }

  return `${baseLabel} · ${normalizedSuffixes.join(' · ')}`
}

import type {
  PoolODataMetadataCatalogDocument,
  PoolODataMetadataCatalogTablePart,
} from '../../api/generated/model'
import type {
  DocumentPolicyBuilderChainFormValue,
  DocumentPolicyBuilderDocumentFormValue,
  DocumentPolicyBuilderTablePartMappingFormValue,
} from './documentPolicyBuilder'

export type SuggestionOption = {
  value: string
  label: string
}

type SuggestionCandidate = string | {
  value?: string | null | undefined
  label?: string | null | undefined
}

const normalizeString = (value: unknown): string => String(value ?? '').trim()

const createOptionMap = () => new Map<string, SuggestionOption>()

const appendOption = (
  options: Map<string, SuggestionOption>,
  candidate: SuggestionCandidate,
) => {
  const value = typeof candidate === 'string'
    ? normalizeString(candidate)
    : normalizeString(candidate.value)
  if (!value) {
    return
  }

  if (options.has(value)) {
    return
  }

  const label = typeof candidate === 'string'
    ? value
    : normalizeString(candidate.label) || value
  options.set(value, { value, label })
}

export const buildSuggestionOptions = (
  candidates: SuggestionCandidate[],
  currentValue?: string | null,
): SuggestionOption[] => {
  const options = createOptionMap()
  candidates.forEach((candidate) => appendOption(options, candidate))
  if (normalizeString(currentValue)) {
    appendOption(options, normalizeString(currentValue))
  }
  return [...options.values()]
}

const collectDocuments = (
  chains: DocumentPolicyBuilderChainFormValue[],
): DocumentPolicyBuilderDocumentFormValue[] => (
  chains.flatMap((chain) => chain.documents ?? [])
)

export const buildChainIdOptions = (
  chains: DocumentPolicyBuilderChainFormValue[],
  currentValue?: string | null,
): SuggestionOption[] => (
  buildSuggestionOptions(chains.map((chain) => normalizeString(chain.chain_id)), currentValue)
)

export const buildDocumentRoleOptions = (
  chains: DocumentPolicyBuilderChainFormValue[],
  currentValue?: string | null,
): SuggestionOption[] => (
  buildSuggestionOptions(
    collectDocuments(chains).map((document) => normalizeString(document.document_role)),
    currentValue,
  )
)

export const buildChainDocumentIdOptions = (
  chain: DocumentPolicyBuilderChainFormValue,
  currentValue?: string | null,
  options?: {
    excludeDocumentIndex?: number
  },
): SuggestionOption[] => (
  buildSuggestionOptions(
    (chain.documents ?? [])
      .flatMap((document, documentIndex) => (
        documentIndex === options?.excludeDocumentIndex
          ? []
          : [normalizeString(document.document_id)]
      )),
    currentValue,
  )
)

export const buildLinkRuleTargetOptions = (
  chain: DocumentPolicyBuilderChainFormValue,
  document: DocumentPolicyBuilderDocumentFormValue,
  currentValue?: string | null,
  options?: {
    excludeDocumentIndex?: number
  },
): SuggestionOption[] => (
  buildSuggestionOptions(
    [
      ...buildChainDocumentIdOptions(chain, undefined, options),
      ...((document.link_rules ?? []).map((linkRule) => normalizeString(linkRule.target))),
    ],
    currentValue,
  )
)

export const buildSourceExpressionOptions = (
  chains: DocumentPolicyBuilderChainFormValue[],
  currentValue?: string | null,
): SuggestionOption[] => {
  const sources: string[] = []

  for (const chain of chains) {
    for (const document of chain.documents ?? []) {
      for (const mapping of document.field_mappings ?? []) {
        sources.push(normalizeString(mapping.source))
      }
      for (const linkRule of document.link_rules ?? []) {
        sources.push(normalizeString(linkRule.source))
      }
      for (const tablePartMapping of document.table_part_mappings ?? []) {
        for (const rowMapping of tablePartMapping.row_mappings ?? []) {
          sources.push(normalizeString(rowMapping.source))
        }
      }
    }
  }

  return buildSuggestionOptions(sources, currentValue)
}

export const findMetadataDocument = (
  metadataDocuments: readonly PoolODataMetadataCatalogDocument[],
  entityName?: string | null,
): PoolODataMetadataCatalogDocument | undefined => {
  const normalizedEntityName = normalizeString(entityName)
  if (!normalizedEntityName) {
    return undefined
  }

  return metadataDocuments.find((document) => document.entity_name === normalizedEntityName)
}

export const buildEntityOptions = (
  metadataDocuments: readonly PoolODataMetadataCatalogDocument[],
  currentValue?: string | null,
): SuggestionOption[] => (
  buildSuggestionOptions(
    metadataDocuments.map((document) => ({
      value: document.entity_name,
      label: document.display_name
        ? `${document.entity_name} (${document.display_name})`
        : document.entity_name,
    })),
    currentValue,
  )
)

export const buildFieldTargetOptions = (
  document: DocumentPolicyBuilderDocumentFormValue,
  metadataDocument?: PoolODataMetadataCatalogDocument,
  currentValue?: string | null,
): SuggestionOption[] => (
  buildSuggestionOptions(
    [
      ...(metadataDocument?.fields ?? []).map((field) => field.name),
      ...((document.field_mappings ?? []).map((mapping) => normalizeString(mapping.target))),
    ],
    currentValue,
  )
)

export const buildTablePartOptions = (
  document: DocumentPolicyBuilderDocumentFormValue,
  metadataDocument?: PoolODataMetadataCatalogDocument,
  currentValue?: string | null,
): SuggestionOption[] => (
  buildSuggestionOptions(
    [
      ...(metadataDocument?.table_parts ?? []).map((tablePart) => tablePart.name),
      ...((document.table_part_mappings ?? []).map((mapping) => normalizeString(mapping.table_part))),
    ],
    currentValue,
  )
)

export const findMetadataTablePart = (
  metadataDocument: PoolODataMetadataCatalogDocument | undefined,
  tablePartName?: string | null,
): PoolODataMetadataCatalogTablePart | undefined => {
  const normalizedTablePartName = normalizeString(tablePartName)
  if (!normalizedTablePartName) {
    return undefined
  }

  return metadataDocument?.table_parts.find((tablePart) => tablePart.name === normalizedTablePartName)
}

export const buildRowTargetOptions = (
  tablePartMapping: DocumentPolicyBuilderTablePartMappingFormValue,
  metadataTablePart?: PoolODataMetadataCatalogTablePart,
  currentValue?: string | null,
): SuggestionOption[] => (
  buildSuggestionOptions(
    [
      ...(metadataTablePart?.row_fields ?? []).map((field) => field.name),
      ...((tablePartMapping.row_mappings ?? []).map((mapping) => normalizeString(mapping.target))),
    ],
    currentValue,
  )
)

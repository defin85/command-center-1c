import type { DecisionTableWriteRequest } from '../../api/generated/v2/v2'

export const DOCUMENT_POLICY_VERSION = 'document_policy.v1'
export const DOCUMENT_POLICY_DECISION_KEY = 'document_policy'
const DEFAULT_DECISION_RULE_ID = 'default'
const DEFAULT_HIT_POLICY = 'first_match'
const DEFAULT_VALIDATION_MODE = 'fail_closed'

export type DocumentPolicyBuilderMappingFormValue = {
  target?: string
  source?: string
}

export type DocumentPolicyBuilderTablePartMappingFormValue = {
  table_part?: string
  row_mappings?: DocumentPolicyBuilderMappingFormValue[]
}

export type DocumentPolicyBuilderDocumentFormValue = {
  document_id?: string
  entity_name?: string
  document_role?: string
  invoice_mode?: 'optional' | 'required' | string
  link_to?: string
  field_mappings?: DocumentPolicyBuilderMappingFormValue[]
  table_part_mappings?: DocumentPolicyBuilderTablePartMappingFormValue[]
  link_rules?: DocumentPolicyBuilderMappingFormValue[]
}

export type DocumentPolicyBuilderChainFormValue = {
  chain_id?: string
  documents?: DocumentPolicyBuilderDocumentFormValue[]
}

export type DocumentPolicyDocumentOutput = {
  document_id: string
  entity_name: string
  document_role: string
  invoice_mode?: 'optional' | 'required'
  link_to?: string
  field_mapping: Record<string, string>
  table_parts_mapping: Record<string, Record<string, string>>
  link_rules: Record<string, string>
}

export type DocumentPolicyChainOutput = {
  chain_id: string
  documents: DocumentPolicyDocumentOutput[]
}

export type DocumentPolicyOutput = {
  version: typeof DOCUMENT_POLICY_VERSION
  chains: DocumentPolicyChainOutput[]
}

export type BuildDocumentPolicyDecisionPayloadInput = {
  database_id?: string
  decision_table_id?: string
  name: string
  description?: string
  chains: DocumentPolicyBuilderChainFormValue[] | null | undefined
  is_active?: boolean
  parent_version_id?: string
}

export class DocumentPolicyBuilderValidationError extends Error {
  issues: string[]

  constructor(issues: string[]) {
    super(issues[0] || 'Invalid document policy builder payload.')
    this.name = 'DocumentPolicyBuilderValidationError'
    this.issues = issues
  }
}

const asObject = (value: unknown): Record<string, unknown> | null => (
  value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null
)

const trimString = (value: unknown): string => String(value ?? '').trim()

const sortRecordByKey = (value: Record<string, string>): Record<string, string> => (
  Object.fromEntries(
    Object.entries(value).sort(([left], [right]) => left.localeCompare(right))
  )
)

const sortTablePartsByKey = (
  value: Record<string, Record<string, string>>
): Record<string, Record<string, string>> => (
  Object.fromEntries(
    Object.entries(value)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([tablePart, rowMappings]) => [tablePart, sortRecordByKey(rowMappings)])
  )
)

const pushInvalidTargetSourceRow = (
  issues: string[],
  rowLabel: string,
  mappingKind: 'field_mapping' | 'table_parts_mapping' | 'link_rules',
  target: string,
  source: string
) => {
  if (!target && !source) return
  if (target && source) return
  issues.push(`${rowLabel}: ${mappingKind} должен содержать target и source.`)
}

const assertNoIssues = (issues: string[]): void => {
  if (issues.length > 0) {
    throw new DocumentPolicyBuilderValidationError(issues)
  }
}

const normalizeKeyValueRows = (
  rowsRaw: DocumentPolicyBuilderMappingFormValue[] | undefined,
  issues: string[],
  rowLabel: string,
  mappingKind: 'field_mapping' | 'table_parts_mapping' | 'link_rules'
): Record<string, string> => {
  const rows = Array.isArray(rowsRaw) ? rowsRaw : []
  const normalized: Record<string, string> = {}

  rows.forEach((row) => {
    const target = trimString(row?.target)
    const source = trimString(row?.source)
    pushInvalidTargetSourceRow(issues, rowLabel, mappingKind, target, source)
    if (!target || !source) return
    normalized[target] = source
  })

  return sortRecordByKey(normalized)
}

const validateDocumentPolicyOutput = (policy: unknown, contextLabel: string): DocumentPolicyOutput => {
  const policyObject = asObject(policy)
  if (!policyObject) {
    throw new DocumentPolicyBuilderValidationError([
      `${contextLabel}: document_policy должен быть object.`,
    ])
  }

  const issues: string[] = []
  const version = trimString(policyObject.version)
  if (version !== DOCUMENT_POLICY_VERSION) {
    issues.push(`${contextLabel}: document_policy.version должен быть "${DOCUMENT_POLICY_VERSION}".`)
  }

  const chainsRaw = Array.isArray(policyObject.chains) ? policyObject.chains : []
  if (chainsRaw.length === 0) {
    issues.push(`${contextLabel}: document_policy.chains должен содержать хотя бы одну цепочку.`)
  }

  const normalizedChains = chainsRaw.map<DocumentPolicyChainOutput>((chain, chainIndex) => {
    const chainLabel = `${contextLabel}: chain #${chainIndex + 1}`
    const chainObject = asObject(chain)
    if (!chainObject) {
      issues.push(`${chainLabel} должен быть object.`)
      return { chain_id: '', documents: [] }
    }

    const chainId = trimString(chainObject.chain_id)
    if (!chainId) {
      issues.push(`${chainLabel} должен содержать chain_id.`)
    }

    const documentsRaw = Array.isArray(chainObject.documents) ? chainObject.documents : []
    if (documentsRaw.length === 0) {
      issues.push(`${chainLabel} должен содержать documents[].`)
    }

    const normalizedDocuments = documentsRaw.map<DocumentPolicyDocumentOutput>((document, documentIndex) => {
      const documentLabel = `${chainLabel}, document #${documentIndex + 1}`
      const documentObject = asObject(document)
      if (!documentObject) {
        issues.push(`${documentLabel} должен быть object.`)
        return {
          document_id: '',
          entity_name: '',
          document_role: '',
          invoice_mode: 'optional',
          field_mapping: {},
          table_parts_mapping: {},
          link_rules: {},
        }
      }

      const documentId = trimString(documentObject.document_id)
      const entityName = trimString(documentObject.entity_name)
      const documentRole = trimString(documentObject.document_role)
      if (!documentId) issues.push(`${documentLabel} должен содержать document_id.`)
      if (!entityName) issues.push(`${documentLabel} должен содержать entity_name.`)
      if (!documentRole) issues.push(`${documentLabel} должен содержать document_role.`)

      const invoiceModeRaw = trimString(documentObject.invoice_mode)
      const invoiceMode = invoiceModeRaw || 'optional'
      if (invoiceMode !== 'optional' && invoiceMode !== 'required') {
        issues.push(`${documentLabel} содержит недопустимый invoice_mode.`)
      }

      const fieldMappingObject = asObject(documentObject.field_mapping) || {}
      const tablePartsObject = asObject(documentObject.table_parts_mapping) || {}
      const linkRulesObject = asObject(documentObject.link_rules) || {}

      const fieldMapping = sortRecordByKey(
        Object.fromEntries(
          Object.entries(fieldMappingObject).map(([target, source]) => [trimString(target), trimString(source)])
        )
      )

      const tablePartsMapping = sortTablePartsByKey(
        Object.fromEntries(
          Object.entries(tablePartsObject).map(([tablePart, rowMappings]) => {
            const rowMappingsObject = asObject(rowMappings) || {}
            return [
              trimString(tablePart),
              Object.fromEntries(
                Object.entries(rowMappingsObject).map(([target, source]) => [trimString(target), trimString(source)])
              ),
            ]
          })
        )
      )

      const linkRules = sortRecordByKey(
        Object.fromEntries(
          Object.entries(linkRulesObject).map(([target, source]) => [trimString(target), trimString(source)])
        )
      )

      const normalizedDocument: DocumentPolicyDocumentOutput = {
        document_id: documentId,
        entity_name: entityName,
        document_role: documentRole,
        invoice_mode: invoiceMode === 'required' ? 'required' : 'optional',
        field_mapping: fieldMapping,
        table_parts_mapping: tablePartsMapping,
        link_rules: linkRules,
      }

      const linkTo = trimString(documentObject.link_to)
      if (linkTo) {
        normalizedDocument.link_to = linkTo
      }
      return normalizedDocument
    })

    return {
      chain_id: chainId,
      documents: normalizedDocuments,
    }
  })

  assertNoIssues(issues)
  return {
    version: DOCUMENT_POLICY_VERSION,
    chains: normalizedChains,
  }
}

export const extractDocumentPolicyOutput = (decisionLike: unknown): DocumentPolicyOutput | null => {
  const root = asObject(decisionLike)
  if (!root) return null

  const decisionCandidate = root.decision !== undefined && root.rules === undefined
    ? asObject(root.decision)
    : root
  if (!decisionCandidate) return null

  const decisionKey = trimString(decisionCandidate.decision_key)
  if (decisionKey && decisionKey !== DOCUMENT_POLICY_DECISION_KEY) {
    throw new DocumentPolicyBuilderValidationError([
      `decision_key должен быть "${DOCUMENT_POLICY_DECISION_KEY}".`,
    ])
  }

  const rulesRaw = decisionCandidate.rules
  if (rulesRaw === undefined) return null
  if (!Array.isArray(rulesRaw) || rulesRaw.length === 0) {
    throw new DocumentPolicyBuilderValidationError([
      'decision.rules должен содержать single default rule output.',
    ])
  }

  const policyRules = rulesRaw.filter((rule) => {
    const ruleObject = asObject(rule)
    const outputs = asObject(ruleObject?.outputs)
    return outputs?.document_policy !== undefined
  })
  if (policyRules.length !== 1) {
    throw new DocumentPolicyBuilderValidationError([
      'decision.rules должен содержать ровно один rule с outputs.document_policy.',
    ])
  }

  const defaultRule = asObject(policyRules[0])
  const ruleId = trimString(defaultRule?.rule_id)
  if (ruleId && ruleId !== DEFAULT_DECISION_RULE_ID) {
    throw new DocumentPolicyBuilderValidationError([
      `rule_id должен быть "${DEFAULT_DECISION_RULE_ID}".`,
    ])
  }

  return validateDocumentPolicyOutput(
    asObject(defaultRule?.outputs)?.document_policy,
    'decision.rules[0].outputs.document_policy'
  )
}

export const documentPolicyToBuilderChains = (
  policy: DocumentPolicyOutput | Record<string, unknown> | null | undefined
): DocumentPolicyBuilderChainFormValue[] => {
  if (!policy) return []
  const normalizedPolicy = validateDocumentPolicyOutput(policy, 'document_policy')

  return normalizedPolicy.chains.map((chain) => ({
    chain_id: chain.chain_id,
    documents: chain.documents.map((document) => ({
      document_id: document.document_id,
      entity_name: document.entity_name,
      document_role: document.document_role,
      invoice_mode: document.invoice_mode || 'optional',
      link_to: document.link_to || '',
      field_mappings: Object.entries(document.field_mapping).map(([target, source]) => ({
        target,
        source,
      })),
      table_part_mappings: Object.entries(document.table_parts_mapping).map(([tablePart, rowMappings]) => ({
        table_part: tablePart,
        row_mappings: Object.entries(rowMappings).map(([target, source]) => ({
          target,
          source,
        })),
      })),
      link_rules: Object.entries(document.link_rules).map(([target, source]) => ({
        target,
        source,
      })),
    })),
  }))
}

export const buildDocumentPolicyFromBuilder = (
  chainsRaw: DocumentPolicyBuilderChainFormValue[] | null | undefined
): DocumentPolicyOutput => {
  const chains = Array.isArray(chainsRaw) ? chainsRaw : []
  const issues: string[] = []

  if (chains.length === 0) {
    throw new DocumentPolicyBuilderValidationError([
      'document_policy.chains должен содержать хотя бы одну цепочку.',
    ])
  }

  const normalizedChains = chains.map<DocumentPolicyChainOutput>((chain, chainIndex) => {
    const chainLabel = `chain #${chainIndex + 1}`
    const chainId = trimString(chain?.chain_id)
    if (!chainId) {
      issues.push(`${chainLabel} должен содержать chain_id.`)
    }

    const documents = Array.isArray(chain?.documents) ? chain.documents : []
    if (documents.length === 0) {
      issues.push(`${chainLabel} должен содержать documents[].`)
    }

    const normalizedDocuments = documents.map<DocumentPolicyDocumentOutput>((document, documentIndex) => {
      const documentLabel = `${chainLabel}, document #${documentIndex + 1}`
      const documentId = trimString(document?.document_id)
      const entityName = trimString(document?.entity_name)
      const documentRole = trimString(document?.document_role)
      if (!documentId) issues.push(`${documentLabel} должен содержать document_id.`)
      if (!entityName) issues.push(`${documentLabel} должен содержать entity_name.`)
      if (!documentRole) issues.push(`${documentLabel} должен содержать document_role.`)

      const invoiceModeRaw = trimString(document?.invoice_mode)
      const invoiceMode = invoiceModeRaw || 'optional'
      if (invoiceMode !== 'optional' && invoiceMode !== 'required') {
        issues.push(`${documentLabel} содержит недопустимый invoice_mode.`)
      }

      const fieldMapping = normalizeKeyValueRows(
        document?.field_mappings,
        issues,
        documentLabel,
        'field_mapping'
      )
      const linkRules = normalizeKeyValueRows(
        document?.link_rules,
        issues,
        documentLabel,
        'link_rules'
      )

      const tablePartMappingsRaw = Array.isArray(document?.table_part_mappings)
        ? document.table_part_mappings
        : []
      const tablePartsMapping: Record<string, Record<string, string>> = {}
      tablePartMappingsRaw.forEach((tablePartMapping) => {
        const tablePart = trimString(tablePartMapping?.table_part)
        const rowMappings = normalizeKeyValueRows(
          tablePartMapping?.row_mappings,
          issues,
          documentLabel,
          'table_parts_mapping'
        )
        if (!tablePart) {
          if (Object.keys(rowMappings).length > 0) {
            issues.push(`${documentLabel}: table_parts_mapping должен содержать table_part.`)
          }
          return
        }
        tablePartsMapping[tablePart] = rowMappings
      })

      const normalizedDocument: DocumentPolicyDocumentOutput = {
        document_id: documentId,
        entity_name: entityName,
        document_role: documentRole,
        invoice_mode: invoiceMode === 'required' ? 'required' : 'optional',
        field_mapping: fieldMapping,
        table_parts_mapping: sortTablePartsByKey(tablePartsMapping),
        link_rules: linkRules,
      }

      const linkTo = trimString(document?.link_to)
      if (linkTo) {
        normalizedDocument.link_to = linkTo
      }
      return normalizedDocument
    })

    return {
      chain_id: chainId,
      documents: normalizedDocuments,
    }
  })

  assertNoIssues(issues)
  return {
    version: DOCUMENT_POLICY_VERSION,
    chains: normalizedChains,
  }
}

export const buildDocumentPolicyDecisionPayload = (
  input: BuildDocumentPolicyDecisionPayloadInput
): DecisionTableWriteRequest => {
  const payload: DecisionTableWriteRequest = {
    name: trimString(input.name),
    description: trimString(input.description),
    decision_table_id: trimString(input.decision_table_id),
    decision_key: DOCUMENT_POLICY_DECISION_KEY,
    inputs: [],
    outputs: [
      {
        name: DOCUMENT_POLICY_DECISION_KEY,
        value_type: 'json',
        required: true,
      },
    ],
    rules: [
      {
        rule_id: DEFAULT_DECISION_RULE_ID,
        priority: 0,
        conditions: {},
        outputs: {
          [DOCUMENT_POLICY_DECISION_KEY]: buildDocumentPolicyFromBuilder(input.chains),
        },
      },
    ],
    hit_policy: DEFAULT_HIT_POLICY,
    validation_mode: DEFAULT_VALIDATION_MODE,
    is_active: input.is_active ?? true,
  }

  const databaseId = trimString(input.database_id)
  if (databaseId) {
    payload.database_id = databaseId
  }

  const parentVersionId = trimString(input.parent_version_id)
  payload.parent_version_id = parentVersionId || undefined

  return payload
}

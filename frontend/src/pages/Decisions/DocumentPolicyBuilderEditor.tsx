import { AutoComplete, Button, Card, Divider, Input, Select, Space, Typography } from 'antd'

import type {
  DocumentPolicyBuilderChainFormValue,
  DocumentPolicyBuilderDocumentFormValue,
  DocumentPolicyBuilderMappingFormValue,
  DocumentPolicyBuilderTablePartMappingFormValue,
} from './documentPolicyBuilder'
import {
  buildChainDocumentIdOptions,
  buildChainIdOptions,
  buildDocumentRoleOptions,
  buildEntityOptions,
  buildFieldTargetOptions,
  buildLinkRuleTargetOptions,
  buildRowTargetOptions,
  buildSourceExpressionOptions,
  buildTablePartOptions,
  findMetadataDocument,
  findMetadataTablePart,
  type SuggestionOption,
} from './documentPolicyBuilderSuggestions'
import type { PoolODataMetadataCatalogDocument } from '../../api/generated/model'
import { useDecisionsTranslation } from '../../i18n'

const { Text } = Typography

type DocumentPolicyBuilderEditorProps = {
  value: DocumentPolicyBuilderChainFormValue[]
  onChange: (value: DocumentPolicyBuilderChainFormValue[]) => void
  disabled?: boolean
  metadataDocuments?: readonly PoolODataMetadataCatalogDocument[]
}

const createEmptyMapping = (): DocumentPolicyBuilderMappingFormValue => ({
  target: '',
  source: '',
})

const createEmptyTablePartMapping = (): DocumentPolicyBuilderTablePartMappingFormValue => ({
  table_part: '',
  row_mappings: [],
})

const createEmptyDocument = (): DocumentPolicyBuilderDocumentFormValue => ({
  document_id: '',
  entity_name: '',
  document_role: '',
  invoice_mode: 'optional',
  link_to: '',
  field_mappings: [],
  table_part_mappings: [],
  link_rules: [],
})

const createEmptyChain = (): DocumentPolicyBuilderChainFormValue => ({
  chain_id: '',
  documents: [],
})

const cloneChains = (chains: DocumentPolicyBuilderChainFormValue[]): DocumentPolicyBuilderChainFormValue[] => (
  typeof structuredClone === 'function'
    ? structuredClone(chains)
    : JSON.parse(JSON.stringify(chains))
)

const getDraftChain = (
  draft: DocumentPolicyBuilderChainFormValue[],
  chainIndex: number,
): DocumentPolicyBuilderChainFormValue => {
  const chain = draft[chainIndex]
  if (chain) return chain

  const fallback = createEmptyChain()
  draft[chainIndex] = fallback
  return fallback
}

const ensureDraftDocuments = (
  draft: DocumentPolicyBuilderChainFormValue[],
  chainIndex: number,
): DocumentPolicyBuilderDocumentFormValue[] => {
  const chain = getDraftChain(draft, chainIndex)
  chain.documents = Array.isArray(chain.documents) ? chain.documents : []
  return chain.documents
}

const getDraftDocument = (
  draft: DocumentPolicyBuilderChainFormValue[],
  chainIndex: number,
  documentIndex: number,
): DocumentPolicyBuilderDocumentFormValue => {
  const documents = ensureDraftDocuments(draft, chainIndex)
  const document = documents[documentIndex]
  if (document) return document

  const fallback = createEmptyDocument()
  documents[documentIndex] = fallback
  return fallback
}

const ensureFieldMappings = (
  document: DocumentPolicyBuilderDocumentFormValue,
): DocumentPolicyBuilderMappingFormValue[] => {
  document.field_mappings = Array.isArray(document.field_mappings) ? document.field_mappings : []
  return document.field_mappings
}

const ensureTablePartMappings = (
  document: DocumentPolicyBuilderDocumentFormValue,
): DocumentPolicyBuilderTablePartMappingFormValue[] => {
  document.table_part_mappings = Array.isArray(document.table_part_mappings) ? document.table_part_mappings : []
  return document.table_part_mappings
}

const getTablePartMapping = (
  document: DocumentPolicyBuilderDocumentFormValue,
  tablePartIndex: number,
): DocumentPolicyBuilderTablePartMappingFormValue => {
  const tableParts = ensureTablePartMappings(document)
  const tablePart = tableParts[tablePartIndex]
  if (tablePart) return tablePart

  const fallback = createEmptyTablePartMapping()
  tableParts[tablePartIndex] = fallback
  return fallback
}

const ensureRowMappings = (
  tablePartMapping: DocumentPolicyBuilderTablePartMappingFormValue,
): DocumentPolicyBuilderMappingFormValue[] => {
  tablePartMapping.row_mappings = Array.isArray(tablePartMapping.row_mappings) ? tablePartMapping.row_mappings : []
  return tablePartMapping.row_mappings
}

const ensureLinkRules = (
  document: DocumentPolicyBuilderDocumentFormValue,
): DocumentPolicyBuilderMappingFormValue[] => {
  document.link_rules = Array.isArray(document.link_rules) ? document.link_rules : []
  return document.link_rules
}

const INLINE_FIELD_STYLE = { minWidth: 220, width: 240 }

const matchesSuggestionOption = (inputValue: string, option?: SuggestionOption) => (
  `${option?.value ?? ''} ${option?.label ?? ''}`
    .toLowerCase()
    .includes(inputValue.trim().toLowerCase())
)

type SuggestionInputProps = {
  ariaLabel: string
  value?: string
  placeholder: string
  options: SuggestionOption[]
  onChange: (value: string) => void
  disabled?: boolean
  style?: { minWidth?: number; width?: number | string }
}

function SuggestionInput({
  ariaLabel,
  value,
  placeholder,
  options,
  onChange,
  disabled,
  style,
}: SuggestionInputProps) {
  return (
    <AutoComplete
      value={value ?? ''}
      options={options}
      onChange={onChange}
      disabled={disabled}
      filterOption={matchesSuggestionOption}
      style={style}
    >
      <Input aria-label={ariaLabel} placeholder={placeholder} disabled={disabled} />
    </AutoComplete>
  )
}

export function DocumentPolicyBuilderEditor({
  value,
  onChange,
  disabled = false,
  metadataDocuments = [],
}: DocumentPolicyBuilderEditorProps) {
  const { t } = useDecisionsTranslation()
  const chains = Array.isArray(value) ? value : []
  const chainIdOptions = buildChainIdOptions(chains)
  const documentRoleOptions = buildDocumentRoleOptions(chains)
  const sourceExpressionOptions = buildSourceExpressionOptions(chains)

  const updateChains = (recipe: (draft: DocumentPolicyBuilderChainFormValue[]) => void) => {
    const next = cloneChains(chains)
    recipe(next)
    onChange(next)
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Button
        type="dashed"
        onClick={() => updateChains((draft) => { draft.push(createEmptyChain()) })}
        disabled={disabled}
      >
        {t(($) => $.builder.addChain)}
      </Button>

      {chains.length === 0 ? (
        <Text type="secondary">{t(($) => $.builder.empty)}</Text>
      ) : null}

      {chains.map((chain, chainIndex) => (
        <Card
          key={`chain-${chainIndex + 1}`}
          size="small"
          title={t(($) => $.builder.chainTitle, { index: String(chainIndex + 1) })}
          extra={(
            <Button
              danger
              size="small"
              onClick={() => updateChains((draft) => { draft.splice(chainIndex, 1) })}
              disabled={disabled}
            >
              {t(($) => $.builder.removeChain)}
            </Button>
          )}
        >
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <SuggestionInput
              ariaLabel={t(($) => $.builder.aria.chainId, { chain: String(chainIndex + 1) })}
              placeholder="sale_chain"
              value={chain.chain_id ?? ''}
              options={chainIdOptions}
              onChange={(nextValue) => updateChains((draft) => {
                draft[chainIndex].chain_id = nextValue
              })}
              disabled={disabled}
              style={{ width: '100%' }}
            />

            <Button
              type="dashed"
              onClick={() => updateChains((draft) => {
                ensureDraftDocuments(draft, chainIndex).push(createEmptyDocument())
              })}
              disabled={disabled}
            >
              {t(($) => $.builder.addDocument, { chain: String(chainIndex + 1) })}
            </Button>

            {(chain.documents ?? []).map((document, documentIndex) => (
              (() => {
                const selectedMetadataDocument = findMetadataDocument(metadataDocuments, document.entity_name)
                const documentIdOptions = buildChainDocumentIdOptions(
                  chain,
                  document.document_id,
                )
                const linkToOptions = buildChainDocumentIdOptions(
                  chain,
                  document.link_to,
                  { excludeDocumentIndex: documentIndex },
                )
                const entityOptions = buildEntityOptions(metadataDocuments, document.entity_name)
                const fieldTargetOptions = buildFieldTargetOptions(
                  document,
                  selectedMetadataDocument,
                )
                const tablePartOptions = buildTablePartOptions(
                  document,
                  selectedMetadataDocument,
                )

                return (
              <Card
                key={`chain-${chainIndex + 1}-document-${documentIndex + 1}`}
                size="small"
                type="inner"
                title={t(($) => $.builder.documentTitle, { index: String(documentIndex + 1) })}
                extra={(
                  <Button
                    danger
                    size="small"
                    onClick={() => updateChains((draft) => {
                      draft[chainIndex].documents?.splice(documentIndex, 1)
                    })}
                    disabled={disabled}
                  >
                    {t(($) => $.builder.removeDocument)}
                  </Button>
                )}
              >
                <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                  <SuggestionInput
                    ariaLabel={t(($) => $.builder.aria.documentId, {
                      chain: String(chainIndex + 1),
                      document: String(documentIndex + 1),
                    })}
                    placeholder="sale"
                    value={document.document_id ?? ''}
                    options={documentIdOptions}
                    onChange={(nextValue) => updateChains((draft) => {
                      getDraftDocument(draft, chainIndex, documentIndex).document_id = nextValue
                    })}
                    disabled={disabled}
                    style={{ width: '100%' }}
                  />
                  <SuggestionInput
                    ariaLabel={t(($) => $.builder.aria.documentEntity, {
                      chain: String(chainIndex + 1),
                      document: String(documentIndex + 1),
                    })}
                    placeholder="Document_Sales"
                    value={document.entity_name ?? ''}
                    options={entityOptions}
                    onChange={(nextValue) => updateChains((draft) => {
                      getDraftDocument(draft, chainIndex, documentIndex).entity_name = nextValue
                    })}
                    disabled={disabled}
                    style={{ width: '100%' }}
                  />
                  <SuggestionInput
                    ariaLabel={t(($) => $.builder.aria.documentRole, {
                      chain: String(chainIndex + 1),
                      document: String(documentIndex + 1),
                    })}
                    placeholder="base"
                    value={document.document_role ?? ''}
                    options={documentRoleOptions}
                    onChange={(nextValue) => updateChains((draft) => {
                      getDraftDocument(draft, chainIndex, documentIndex).document_role = nextValue
                    })}
                    disabled={disabled}
                    style={{ width: '100%' }}
                  />
                  <Select
                    aria-label={t(($) => $.builder.aria.invoiceMode, {
                      chain: String(chainIndex + 1),
                      document: String(documentIndex + 1),
                    })}
                    value={document.invoice_mode ?? 'optional'}
                    options={[
                      { value: 'optional', label: t(($) => $.builder.invoiceModes.optional) },
                      { value: 'required', label: t(($) => $.builder.invoiceModes.required) },
                    ]}
                    onChange={(nextValue) => updateChains((draft) => {
                      getDraftDocument(draft, chainIndex, documentIndex).invoice_mode = nextValue
                    })}
                    disabled={disabled}
                  />
                  <SuggestionInput
                    ariaLabel={t(($) => $.builder.aria.linkTo, {
                      chain: String(chainIndex + 1),
                      document: String(documentIndex + 1),
                    })}
                    placeholder="parent_document"
                    value={document.link_to ?? ''}
                    options={linkToOptions}
                    onChange={(nextValue) => updateChains((draft) => {
                      getDraftDocument(draft, chainIndex, documentIndex).link_to = nextValue
                    })}
                    disabled={disabled}
                    style={{ width: '100%' }}
                  />

                  <Divider orientation="left" plain>{t(($) => $.builder.sections.fieldMapping)}</Divider>
                  <Button
                    type="dashed"
                    onClick={() => updateChains((draft) => {
                      ensureFieldMappings(getDraftDocument(draft, chainIndex, documentIndex)).push(createEmptyMapping())
                    })}
                    disabled={disabled}
                  >
                    {t(($) => $.builder.addFieldMapping, {
                      chain: String(chainIndex + 1),
                      document: String(documentIndex + 1),
                    })}
                  </Button>
                  {(document.field_mappings ?? []).map((mapping, mappingIndex) => (
                    <Space key={`field-${mappingIndex + 1}`} align="start" wrap>
                      <SuggestionInput
                        ariaLabel={t(($) => $.builder.aria.fieldTarget, {
                          chain: String(chainIndex + 1),
                          document: String(documentIndex + 1),
                          mapping: String(mappingIndex + 1),
                        })}
                        placeholder="Amount"
                        value={mapping.target ?? ''}
                        options={fieldTargetOptions}
                        onChange={(nextValue) => updateChains((draft) => {
                          ensureFieldMappings(getDraftDocument(draft, chainIndex, documentIndex))[mappingIndex].target = nextValue
                        })}
                        disabled={disabled}
                        style={INLINE_FIELD_STYLE}
                      />
                      <SuggestionInput
                        ariaLabel={t(($) => $.builder.aria.fieldSource, {
                          chain: String(chainIndex + 1),
                          document: String(documentIndex + 1),
                          mapping: String(mappingIndex + 1),
                        })}
                        placeholder="allocation.amount"
                        value={mapping.source ?? ''}
                        options={sourceExpressionOptions}
                        onChange={(nextValue) => updateChains((draft) => {
                          ensureFieldMappings(getDraftDocument(draft, chainIndex, documentIndex))[mappingIndex].source = nextValue
                        })}
                        disabled={disabled}
                        style={INLINE_FIELD_STYLE}
                      />
                      <Button
                        danger
                        onClick={() => updateChains((draft) => {
                          ensureFieldMappings(getDraftDocument(draft, chainIndex, documentIndex)).splice(mappingIndex, 1)
                        })}
                        disabled={disabled}
                      >
                        {t(($) => $.builder.remove)}
                      </Button>
                    </Space>
                  ))}

                  <Divider orientation="left" plain>{t(($) => $.builder.sections.tablePartMapping)}</Divider>
                  <Button
                    type="dashed"
                    onClick={() => updateChains((draft) => {
                      ensureTablePartMappings(getDraftDocument(draft, chainIndex, documentIndex)).push(createEmptyTablePartMapping())
                    })}
                    disabled={disabled}
                  >
                    {t(($) => $.builder.addTablePartMapping, {
                      chain: String(chainIndex + 1),
                      document: String(documentIndex + 1),
                    })}
                  </Button>
                  {(document.table_part_mappings ?? []).map((tablePartMapping, tablePartIndex) => (
                    (() => {
                      const metadataTablePart = findMetadataTablePart(
                        selectedMetadataDocument,
                        tablePartMapping.table_part,
                      )
                      const rowTargetOptions = buildRowTargetOptions(
                        tablePartMapping,
                        metadataTablePart,
                      )

                      return (
                    <Card
                      key={`table-part-${tablePartIndex + 1}`}
                      size="small"
                      type="inner"
                      title={t(($) => $.builder.tablePartTitle, { index: String(tablePartIndex + 1) })}
                      extra={(
                        <Button
                          danger
                          size="small"
                          onClick={() => updateChains((draft) => {
                            ensureTablePartMappings(getDraftDocument(draft, chainIndex, documentIndex)).splice(tablePartIndex, 1)
                          })}
                          disabled={disabled}
                        >
                          {t(($) => $.builder.removeTablePart)}
                        </Button>
                      )}
                    >
                      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                        <SuggestionInput
                          ariaLabel={t(($) => $.builder.aria.tablePartName, {
                            chain: String(chainIndex + 1),
                            document: String(documentIndex + 1),
                            tablePart: String(tablePartIndex + 1),
                          })}
                          placeholder="Items"
                          value={tablePartMapping.table_part ?? ''}
                          options={tablePartOptions}
                          onChange={(nextValue) => updateChains((draft) => {
                            getTablePartMapping(getDraftDocument(draft, chainIndex, documentIndex), tablePartIndex).table_part = nextValue
                          })}
                          disabled={disabled}
                          style={{ width: '100%' }}
                        />
                        <Button
                          type="dashed"
                          onClick={() => updateChains((draft) => {
                            ensureRowMappings(getTablePartMapping(getDraftDocument(draft, chainIndex, documentIndex), tablePartIndex)).push(createEmptyMapping())
                          })}
                          disabled={disabled}
                        >
                          {t(($) => $.builder.addRowMapping, {
                            chain: String(chainIndex + 1),
                            document: String(documentIndex + 1),
                            tablePart: String(tablePartIndex + 1),
                          })}
                        </Button>
                        {(tablePartMapping.row_mappings ?? []).map((rowMapping, rowMappingIndex) => (
                          <Space key={`row-${rowMappingIndex + 1}`} align="start" wrap>
                            <SuggestionInput
                              ariaLabel={t(($) => $.builder.aria.rowTarget, {
                                chain: String(chainIndex + 1),
                                document: String(documentIndex + 1),
                                tablePart: String(tablePartIndex + 1),
                                mapping: String(rowMappingIndex + 1),
                              })}
                              placeholder="Quantity"
                              value={rowMapping.target ?? ''}
                              options={rowTargetOptions}
                              onChange={(nextValue) => updateChains((draft) => {
                                ensureRowMappings(getTablePartMapping(getDraftDocument(draft, chainIndex, documentIndex), tablePartIndex))[rowMappingIndex].target = nextValue
                              })}
                              disabled={disabled}
                              style={INLINE_FIELD_STYLE}
                            />
                            <SuggestionInput
                              ariaLabel={t(($) => $.builder.aria.rowSource, {
                                chain: String(chainIndex + 1),
                                document: String(documentIndex + 1),
                                tablePart: String(tablePartIndex + 1),
                                mapping: String(rowMappingIndex + 1),
                              })}
                              placeholder="allocation.lines.quantity"
                              value={rowMapping.source ?? ''}
                              options={sourceExpressionOptions}
                              onChange={(nextValue) => updateChains((draft) => {
                                ensureRowMappings(getTablePartMapping(getDraftDocument(draft, chainIndex, documentIndex), tablePartIndex))[rowMappingIndex].source = nextValue
                              })}
                              disabled={disabled}
                              style={INLINE_FIELD_STYLE}
                            />
                            <Button
                              danger
                              onClick={() => updateChains((draft) => {
                                ensureRowMappings(getTablePartMapping(getDraftDocument(draft, chainIndex, documentIndex), tablePartIndex)).splice(rowMappingIndex, 1)
                              })}
                              disabled={disabled}
                            >
                              {t(($) => $.builder.remove)}
                            </Button>
                          </Space>
                        ))}
                      </Space>
                    </Card>
                      )
                    })()
                  ))}

                  <Divider orientation="left" plain>{t(($) => $.builder.sections.linkRules)}</Divider>
                  <Button
                    type="dashed"
                    onClick={() => updateChains((draft) => {
                      ensureLinkRules(getDraftDocument(draft, chainIndex, documentIndex)).push(createEmptyMapping())
                    })}
                    disabled={disabled}
                  >
                    {t(($) => $.builder.addLinkRule, {
                      chain: String(chainIndex + 1),
                      document: String(documentIndex + 1),
                    })}
                  </Button>
                  {(document.link_rules ?? []).map((linkRule, linkRuleIndex) => (
                    <Space key={`link-rule-${linkRuleIndex + 1}`} align="start" wrap>
                      <SuggestionInput
                        ariaLabel={t(($) => $.builder.aria.linkRuleTarget, {
                          chain: String(chainIndex + 1),
                          document: String(documentIndex + 1),
                          mapping: String(linkRuleIndex + 1),
                        })}
                        placeholder="child_document"
                        value={linkRule.target ?? ''}
                        options={buildLinkRuleTargetOptions(
                          chain,
                          document,
                          linkRule.target,
                          { excludeDocumentIndex: documentIndex },
                        )}
                        onChange={(nextValue) => updateChains((draft) => {
                          ensureLinkRules(getDraftDocument(draft, chainIndex, documentIndex))[linkRuleIndex].target = nextValue
                        })}
                        disabled={disabled}
                        style={INLINE_FIELD_STYLE}
                      />
                      <SuggestionInput
                        ariaLabel={t(($) => $.builder.aria.linkRuleSource, {
                          chain: String(chainIndex + 1),
                          document: String(documentIndex + 1),
                          mapping: String(linkRuleIndex + 1),
                        })}
                        placeholder="parent.ref"
                        value={linkRule.source ?? ''}
                        options={sourceExpressionOptions}
                        onChange={(nextValue) => updateChains((draft) => {
                          ensureLinkRules(getDraftDocument(draft, chainIndex, documentIndex))[linkRuleIndex].source = nextValue
                        })}
                        disabled={disabled}
                        style={INLINE_FIELD_STYLE}
                      />
                      <Button
                        danger
                        onClick={() => updateChains((draft) => {
                          ensureLinkRules(getDraftDocument(draft, chainIndex, documentIndex)).splice(linkRuleIndex, 1)
                        })}
                        disabled={disabled}
                      >
                        {t(($) => $.builder.remove)}
                      </Button>
                    </Space>
                  ))}
                </Space>
              </Card>
                )
              })()
            ))}
          </Space>
        </Card>
      ))}
    </Space>
  )
}

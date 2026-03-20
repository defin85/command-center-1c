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
        Add chain
      </Button>

      {chains.length === 0 ? (
        <Text type="secondary">Add at least one chain to publish a document policy.</Text>
      ) : null}

      {chains.map((chain, chainIndex) => (
        <Card
          key={`chain-${chainIndex + 1}`}
          size="small"
          title={`Chain ${chainIndex + 1}`}
          extra={(
            <Button
              danger
              size="small"
              onClick={() => updateChains((draft) => { draft.splice(chainIndex, 1) })}
              disabled={disabled}
            >
              Remove chain
            </Button>
          )}
        >
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <SuggestionInput
              ariaLabel={`Chain ${chainIndex + 1} ID`}
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
              {`Add document to chain ${chainIndex + 1}`}
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
                title={`Document ${documentIndex + 1}`}
                extra={(
                  <Button
                    danger
                    size="small"
                    onClick={() => updateChains((draft) => {
                      draft[chainIndex].documents?.splice(documentIndex, 1)
                    })}
                    disabled={disabled}
                  >
                    Remove document
                  </Button>
                )}
              >
                <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                  <SuggestionInput
                    ariaLabel={`Chain ${chainIndex + 1} document ${documentIndex + 1} ID`}
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
                    ariaLabel={`Chain ${chainIndex + 1} document ${documentIndex + 1} entity`}
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
                    ariaLabel={`Chain ${chainIndex + 1} document ${documentIndex + 1} role`}
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
                    aria-label={`Chain ${chainIndex + 1} document ${documentIndex + 1} invoice mode`}
                    value={document.invoice_mode ?? 'optional'}
                    options={[
                      { value: 'optional', label: 'optional' },
                      { value: 'required', label: 'required' },
                    ]}
                    onChange={(nextValue) => updateChains((draft) => {
                      getDraftDocument(draft, chainIndex, documentIndex).invoice_mode = nextValue
                    })}
                    disabled={disabled}
                  />
                  <SuggestionInput
                    ariaLabel={`Chain ${chainIndex + 1} document ${documentIndex + 1} link to`}
                    placeholder="parent_document"
                    value={document.link_to ?? ''}
                    options={linkToOptions}
                    onChange={(nextValue) => updateChains((draft) => {
                      getDraftDocument(draft, chainIndex, documentIndex).link_to = nextValue
                    })}
                    disabled={disabled}
                    style={{ width: '100%' }}
                  />

                  <Divider orientation="left" plain>Field mapping</Divider>
                  <Button
                    type="dashed"
                    onClick={() => updateChains((draft) => {
                      ensureFieldMappings(getDraftDocument(draft, chainIndex, documentIndex)).push(createEmptyMapping())
                    })}
                    disabled={disabled}
                  >
                    {`Add field mapping to chain ${chainIndex + 1} document ${documentIndex + 1}`}
                  </Button>
                  {(document.field_mappings ?? []).map((mapping, mappingIndex) => (
                    <Space key={`field-${mappingIndex + 1}`} align="start" wrap>
                      <SuggestionInput
                        ariaLabel={`Chain ${chainIndex + 1} document ${documentIndex + 1} field mapping ${mappingIndex + 1} target`}
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
                        ariaLabel={`Chain ${chainIndex + 1} document ${documentIndex + 1} field mapping ${mappingIndex + 1} source`}
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
                        Remove
                      </Button>
                    </Space>
                  ))}

                  <Divider orientation="left" plain>Table-part mapping</Divider>
                  <Button
                    type="dashed"
                    onClick={() => updateChains((draft) => {
                      ensureTablePartMappings(getDraftDocument(draft, chainIndex, documentIndex)).push(createEmptyTablePartMapping())
                    })}
                    disabled={disabled}
                  >
                    {`Add table part mapping to chain ${chainIndex + 1} document ${documentIndex + 1}`}
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
                      title={`Table part ${tablePartIndex + 1}`}
                      extra={(
                        <Button
                          danger
                          size="small"
                          onClick={() => updateChains((draft) => {
                            ensureTablePartMappings(getDraftDocument(draft, chainIndex, documentIndex)).splice(tablePartIndex, 1)
                          })}
                          disabled={disabled}
                        >
                          Remove table part
                        </Button>
                      )}
                    >
                      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                        <SuggestionInput
                          ariaLabel={`Chain ${chainIndex + 1} document ${documentIndex + 1} table part mapping ${tablePartIndex + 1} name`}
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
                          {`Add row mapping to chain ${chainIndex + 1} document ${documentIndex + 1} table part ${tablePartIndex + 1}`}
                        </Button>
                        {(tablePartMapping.row_mappings ?? []).map((rowMapping, rowMappingIndex) => (
                          <Space key={`row-${rowMappingIndex + 1}`} align="start" wrap>
                            <SuggestionInput
                              ariaLabel={`Chain ${chainIndex + 1} document ${documentIndex + 1} table part ${tablePartIndex + 1} row mapping ${rowMappingIndex + 1} target`}
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
                              ariaLabel={`Chain ${chainIndex + 1} document ${documentIndex + 1} table part ${tablePartIndex + 1} row mapping ${rowMappingIndex + 1} source`}
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
                              Remove
                            </Button>
                          </Space>
                        ))}
                      </Space>
                    </Card>
                      )
                    })()
                  ))}

                  <Divider orientation="left" plain>Link rules</Divider>
                  <Button
                    type="dashed"
                    onClick={() => updateChains((draft) => {
                      ensureLinkRules(getDraftDocument(draft, chainIndex, documentIndex)).push(createEmptyMapping())
                    })}
                    disabled={disabled}
                  >
                    {`Add link rule to chain ${chainIndex + 1} document ${documentIndex + 1}`}
                  </Button>
                  {(document.link_rules ?? []).map((linkRule, linkRuleIndex) => (
                    <Space key={`link-rule-${linkRuleIndex + 1}`} align="start" wrap>
                      <SuggestionInput
                        ariaLabel={`Chain ${chainIndex + 1} document ${documentIndex + 1} link rule ${linkRuleIndex + 1} target`}
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
                        ariaLabel={`Chain ${chainIndex + 1} document ${documentIndex + 1} link rule ${linkRuleIndex + 1} source`}
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
                        Remove
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

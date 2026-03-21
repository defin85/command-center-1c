import { describe, expect, it } from 'vitest'

import {
  DocumentPolicyBuilderValidationError,
  buildDocumentPolicyDecisionPayload,
  buildDocumentPolicyFromBuilder,
  documentPolicyToBuilderChains,
  extractDocumentPolicyOutput,
  type DocumentPolicyBuilderChainFormValue,
  type DocumentPolicyOutput,
} from '../documentPolicyBuilder'

const basePolicy: DocumentPolicyOutput = {
  version: 'document_policy.v1',
  chains: [
    {
      chain_id: 'sale_chain',
      documents: [
        {
          document_id: 'sale',
          entity_name: 'Document_Sales',
          document_role: 'sale',
          invoice_mode: 'required',
          field_mapping: {
            Amount: 'allocation.amount',
            Organization: 'allocation.organization_ref',
          },
          table_parts_mapping: {
            Goods: [
              {
                Item: 'allocation.items[].item_ref',
                Quantity: 'allocation.items[].qty',
              },
            ],
          },
          link_rules: {},
        },
        {
          document_id: 'invoice',
          entity_name: 'Document_Invoice',
          document_role: 'invoice',
          invoice_mode: 'optional',
          link_to: 'sale',
          field_mapping: {
            BaseDocument: 'sale.ref',
          },
          table_parts_mapping: {},
          link_rules: {
            depends_on: 'sale',
          },
        },
      ],
    },
  ],
}

describe('documentPolicyBuilder', () => {
  it('extracts document_policy output and round-trips builder <-> policy', () => {
    const extracted = extractDocumentPolicyOutput({
      decision_key: 'document_policy',
      rules: [
        {
          rule_id: 'default',
          priority: 0,
          conditions: {},
          outputs: {
            document_policy: basePolicy,
          },
        },
      ],
    })

    const builder = documentPolicyToBuilderChains(extracted)

    expect(builder).toEqual([
      {
        chain_id: 'sale_chain',
        documents: [
          {
            document_id: 'sale',
            entity_name: 'Document_Sales',
            document_role: 'sale',
            invoice_mode: 'required',
            link_to: '',
            field_mappings: [
              { target: 'Amount', source: 'allocation.amount' },
              { target: 'Organization', source: 'allocation.organization_ref' },
            ],
            table_part_mappings: [
              {
                table_part: 'Goods',
                row_mappings: [
                  { target: 'Item', source: 'allocation.items[].item_ref' },
                  { target: 'Quantity', source: 'allocation.items[].qty' },
                ],
              },
            ],
            link_rules: [],
          },
          {
            document_id: 'invoice',
            entity_name: 'Document_Invoice',
            document_role: 'invoice',
            invoice_mode: 'optional',
            link_to: 'sale',
            field_mappings: [
              { target: 'BaseDocument', source: 'sale.ref' },
            ],
            table_part_mappings: [],
            link_rules: [
              { target: 'depends_on', source: 'sale' },
            ],
          },
        ],
      },
    ])

    expect(buildDocumentPolicyFromBuilder(builder)).toEqual(basePolicy)
  })

  it('preserves table-part row arrays and rich mapping values via builder encoding', () => {
    const richPolicy: DocumentPolicyOutput = {
      version: 'document_policy.v1',
      chains: [
        {
          chain_id: 'services',
          documents: [
            {
              document_id: 'sale',
              entity_name: 'Document_РеализацияТоваровУслуг',
              document_role: 'sale',
              invoice_mode: 'optional',
              field_mapping: {
                Date: '2023-10-04T12:00:00',
                СуммаДокумента: 'allocation.amount',
                СуммаВключаетНДС: true,
                КурсВзаиморасчетов: 1,
              },
              table_parts_mapping: {
                АгентскиеУслуги: [
                  {
                    Количество: 1,
                    Сумма: 'allocation.amount',
                    СуммаНДС: {
                      $derive: {
                        op: 'div',
                        args: ['allocation.amount', 6],
                        scale: 2,
                      },
                    },
                  },
                ],
              },
              link_rules: {},
            },
          ],
        },
      ],
    }

    const extracted = extractDocumentPolicyOutput({
      decision_key: 'document_policy',
      rules: [
        {
          rule_id: 'default',
          priority: 0,
          conditions: {},
          outputs: {
            document_policy: richPolicy,
          },
        },
      ],
    })

    expect(extracted).toEqual(richPolicy)

    const builder = documentPolicyToBuilderChains(extracted)

    expect(builder[0]?.documents?.[0]?.field_mappings).toEqual(
      expect.arrayContaining([
        { target: 'СуммаВключаетНДС', source: '@json:true' },
        { target: 'КурсВзаиморасчетов', source: '@json:1' },
      ]),
    )
    expect(builder[0]?.documents?.[0]?.table_part_mappings).toEqual([
      {
        table_part: 'АгентскиеУслуги',
        row_mappings: [
          { target: 'Количество', source: '@json:1' },
          { target: 'Сумма', source: 'allocation.amount' },
          {
            target: 'СуммаНДС',
            source: '@json:{"$derive":{"args":["allocation.amount",6],"op":"div","scale":2}}',
          },
        ],
      },
    ])

    expect(buildDocumentPolicyFromBuilder(builder)).toEqual(richPolicy)
  })

  it('supports detail response shape in extractDocumentPolicyOutput', () => {
    expect(
      extractDocumentPolicyOutput({
        decision: {
          decision_key: 'document_policy',
          rules: [
            {
              rule_id: 'default',
              outputs: {
                document_policy: basePolicy,
              },
            },
          ],
        },
      })
    ).toEqual(basePolicy)
  })

  it('allows reading legacy document_policy rules with non-default rule_id when explicitly requested', () => {
    expect(
      extractDocumentPolicyOutput(
        {
          decision_key: 'document_policy',
          rules: [
            {
              rule_id: 'legacy_rule',
              outputs: {
                document_policy: basePolicy,
              },
            },
          ],
        },
        { allowNonDefaultRuleId: true }
      )
    ).toEqual(basePolicy)
  })

  it.each([
    {
      name: 'missing chain_id',
      chains: [{ documents: [{ document_id: 'sale', entity_name: 'Document_Sales', document_role: 'sale' }] }],
      issue: 'chain_id',
    },
    {
      name: 'missing documents',
      chains: [{ chain_id: 'sale_chain', documents: [] }],
      issue: 'documents',
    },
    {
      name: 'missing required document fields',
      chains: [{ chain_id: 'sale_chain', documents: [{}] }],
      issue: 'document_id',
    },
    {
      name: 'invalid invoice_mode',
      chains: [
        {
          chain_id: 'sale_chain',
          documents: [
            {
              document_id: 'sale',
              entity_name: 'Document_Sales',
              document_role: 'sale',
              invoice_mode: 'always',
            },
          ],
        },
      ],
      issue: 'invoice_mode',
    },
    {
      name: 'field mapping requires target and source',
      chains: [
        {
          chain_id: 'sale_chain',
          documents: [
            {
              document_id: 'sale',
              entity_name: 'Document_Sales',
              document_role: 'sale',
              field_mappings: [{ target: 'Amount', source: '' }],
            },
          ],
        },
      ],
      issue: 'field_mapping',
    },
    {
      name: 'table part mapping requires table_part',
      chains: [
        {
          chain_id: 'sale_chain',
          documents: [
            {
              document_id: 'sale',
              entity_name: 'Document_Sales',
              document_role: 'sale',
              table_part_mappings: [
                {
                  table_part: '',
                  row_mappings: [{ target: 'Amount', source: 'allocation.items[].amount' }],
                },
              ],
            },
          ],
        },
      ],
      issue: 'table_part',
    },
    {
      name: 'link rule requires target and source',
      chains: [
        {
          chain_id: 'sale_chain',
          documents: [
            {
              document_id: 'invoice',
              entity_name: 'Document_Invoice',
              document_role: 'invoice',
              link_rules: [{ target: 'depends_on', source: '' }],
            },
          ],
        },
      ],
      issue: 'link_rules',
    },
  ])('fails closed for $name', ({ chains, issue }) => {
    let thrown: unknown

    try {
      buildDocumentPolicyFromBuilder(chains as DocumentPolicyBuilderChainFormValue[])
    } catch (error) {
      thrown = error
    }

    expect(thrown).toBeInstanceOf(DocumentPolicyBuilderValidationError)
    expect((thrown as DocumentPolicyBuilderValidationError).issues).toEqual(
      expect.arrayContaining([expect.stringContaining(issue)])
    )
  })

  it('builds POST /api/v2/decisions payload with single default document_policy rule', () => {
    const chains = documentPolicyToBuilderChains(basePolicy)

    expect(
      buildDocumentPolicyDecisionPayload({
        database_id: 'db-2',
        decision_table_id: 'services-publication-policy',
        name: 'Services publication policy',
        description: 'Publishes service documents',
        chains,
        is_active: false,
        parent_version_id: 'decision-version-1',
      })
    ).toEqual({
      database_id: 'db-2',
      decision_table_id: 'services-publication-policy',
      decision_key: 'document_policy',
      name: 'Services publication policy',
      description: 'Publishes service documents',
      inputs: [],
      outputs: [
        {
          name: 'document_policy',
          value_type: 'json',
          required: true,
        },
      ],
      rules: [
        {
          rule_id: 'default',
          priority: 0,
          conditions: {},
          outputs: {
            document_policy: basePolicy,
          },
        },
      ],
      hit_policy: 'first_match',
      validation_mode: 'fail_closed',
      is_active: false,
      parent_version_id: 'decision-version-1',
    })
  })
})

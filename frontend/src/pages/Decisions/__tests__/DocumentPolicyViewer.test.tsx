import { render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { changeLanguage } from '@/i18n/runtime'

import { DocumentPolicyViewer } from '../DocumentPolicyViewer'
import type { DocumentPolicyOutput } from '../documentPolicyBuilder'

describe('DocumentPolicyViewer', () => {
  beforeEach(async () => {
    await changeLanguage('en')
  })

  afterEach(async () => {
    await changeLanguage('ru')
  })

  it('renders row mappings from table_parts_mapping arrays', () => {
    const policy: DocumentPolicyOutput = {
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
                СуммаДокумента: 'allocation.amount',
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

    render(<DocumentPolicyViewer policy={policy} />)

    expect(screen.getByText('Table part: АгентскиеУслуги')).toBeInTheDocument()
    expect(screen.getByText('Количество')).toBeInTheDocument()
    expect(screen.getByText('Сумма')).toBeInTheDocument()
    expect(screen.getAllByText('allocation.amount')).toHaveLength(2)
    expect(screen.getAllByText('1').length).toBeGreaterThan(0)
    expect(
      screen.getByText('{"$derive":{"op":"div","args":["allocation.amount",6],"scale":2}}'),
    ).toBeInTheDocument()
  })
})

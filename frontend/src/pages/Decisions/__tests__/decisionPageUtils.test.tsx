import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { buildDraftFromDecision, renderCompatibilityTag } from '../decisionPageUtils'

describe('decisionPageUtils', () => {
  it('renders incompatible compatibility status with contrast-safe badge styling', () => {
    render(
      <div>
        {renderCompatibilityTag({
          status: 'incompatible',
          reason: 'configuration_scope_mismatch',
          is_compatible: false,
        })}
      </div>,
    )

    expect(screen.getByText('Incompatible')).toHaveStyle({
      backgroundColor: '#ffedd5',
      borderColor: '#fdba74',
      color: '#9a3412',
    })
  })

  it('builds clone draft without parent_version_id and with source summary', () => {
    const decision = {
      id: 'decision-version-2',
      decision_table_id: 'services-publication-policy',
      decision_key: 'document_policy',
      decision_revision: 2,
      name: 'Services publication policy',
      description: 'Publishes service documents',
      inputs: [],
      outputs: [],
      rules: [
        {
          rule_id: 'default',
          priority: 0,
          conditions: {},
          outputs: {
            document_policy: {
              version: 'document_policy.v1',
              chains: [
                {
                  chain_id: 'sale_chain',
                  documents: [
                    {
                      document_id: 'sale',
                      entity_name: 'Document_Sales',
                      document_role: 'base',
                      field_mapping: {
                        Amount: 'allocation.amount',
                      },
                      table_parts_mapping: {},
                      link_rules: {},
                    },
                  ],
                },
              ],
            },
          },
        },
      ],
      hit_policy: 'first_match',
      validation_mode: 'fail_closed',
      is_active: true,
      parent_version: 'decision-version-1',
      metadata_context: {
        snapshot_id: 'snapshot-1',
        config_name: 'shared-profile',
        config_version: '8.3.24',
        extensions_fingerprint: '',
        metadata_hash: 'a'.repeat(64),
        resolution_mode: 'shared_scope',
        is_shared_snapshot: true,
        provenance_database_id: 'db-1',
        provenance_confirmed_at: '2026-03-10T11:00:00Z',
      },
      metadata_compatibility: {
        status: 'compatible',
        reason: null,
        is_compatible: true,
      },
      created_at: '2026-03-10T12:00:00Z',
      updated_at: '2026-03-10T12:00:00Z',
    }

    const draft = buildDraftFromDecision(decision, { mode: 'clone', targetDatabaseId: 'db-2' })

    expect(draft.mode).toBe('clone')
    expect(draft.decisionTableId).toBe('services-publication-policy-copy')
    expect(draft.parentVersionId).toBeUndefined()
    expect(draft.targetDatabaseId).toBe('db-2')
    expect(draft.sourceSummary).toEqual({
      decisionId: 'decision-version-2',
      decisionTableId: 'services-publication-policy',
      decisionRevision: 2,
      name: 'Services publication policy',
      compatibilityStatus: 'compatible',
      compatibilityReason: undefined,
    })
  })
})

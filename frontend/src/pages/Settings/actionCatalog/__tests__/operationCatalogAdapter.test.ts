import { describe, expect, test } from 'vitest'

import {
  buildCatalogFromOperationCatalogRecords,
  buildOperationCatalogUpsertFromAction,
} from '../operationCatalogAdapter'

describe('operationCatalogAdapter', () => {
  test('buildCatalogFromOperationCatalogRecords merges capability config into executor', () => {
    const catalog = buildCatalogFromOperationCatalogRecords([
      {
        exposure: {
          id: 'exp-1',
          definition_id: 'def-1',
          surface: 'action_catalog',
          alias: 'extensions.set_flags',
          tenant_id: null,
          name: 'Set flags',
          description: '',
          is_active: true,
          capability: 'extensions.set_flags',
          contexts: ['bulk_page'],
          display_order: 1,
          capability_config: {
            target_binding: { extension_name_param: 'extension_name' },
            apply_mask: {
              active: true,
              safe_mode: false,
              unsafe_action_protection: false,
            },
          },
          status: 'published',
        },
        definition: {
          id: 'def-1',
          tenant_scope: 'global',
          executor_kind: 'ibcmd_cli',
          executor_payload: {
            kind: 'ibcmd_cli',
            driver: 'ibcmd',
            command_id: 'infobase.extension.update',
            params: {
              active: '$policy.active',
            },
          },
          contract_version: 1,
          fingerprint: 'fp',
          status: 'active',
        },
      },
    ])

    expect(catalog).toMatchObject({
      catalog_version: 1,
      extensions: {
        actions: [
          {
            id: 'extensions.set_flags',
            capability: 'extensions.set_flags',
            executor: {
              kind: 'ibcmd_cli',
              driver: 'ibcmd',
              command_id: 'infobase.extension.update',
              target_binding: {
                extension_name_param: 'extension_name',
              },
              fixed: {
                apply_mask: {
                  active: true,
                  safe_mode: false,
                  unsafe_action_protection: false,
                },
              },
            },
          },
        ],
      },
    })
  })

  test('buildOperationCatalogUpsertFromAction splits target_binding and apply_mask into capability_config', () => {
    const payload = buildOperationCatalogUpsertFromAction(
      {
        id: 'extensions.set_flags',
        label: 'Set flags',
        capability: 'extensions.set_flags',
        contexts: ['bulk_page'],
        executor: {
          kind: 'ibcmd_cli',
          driver: 'ibcmd',
          command_id: 'infobase.extension.update',
          params: {
            active: '$policy.active',
            safe_mode: '$policy.safe_mode',
          },
          target_binding: {
            extension_name_param: 'extension_name',
          },
          fixed: {
            apply_mask: {
              active: true,
              safe_mode: false,
              unsafe_action_protection: false,
            },
          },
        },
      },
      { displayOrder: 3 }
    )

    expect(payload).not.toBeNull()
    expect(payload?.definition).toMatchObject({
      executor_kind: 'ibcmd_cli',
      executor_payload: {
        kind: 'ibcmd_cli',
        driver: 'ibcmd',
        command_id: 'infobase.extension.update',
        params: {
          active: '$policy.active',
          safe_mode: '$policy.safe_mode',
        },
      },
    })
    expect(payload?.definition?.executor_payload).not.toHaveProperty('target_binding')
    expect(payload?.definition?.executor_payload).not.toHaveProperty('fixed')

    expect(payload?.exposure).toMatchObject({
      alias: 'extensions.set_flags',
      capability: 'extensions.set_flags',
      display_order: 3,
      capability_config: {
        target_binding: {
          extension_name_param: 'extension_name',
        },
        apply_mask: {
          active: true,
          safe_mode: false,
          unsafe_action_protection: false,
        },
      },
    })
  })
})

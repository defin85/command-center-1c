import { describe, it, expect } from 'vitest'

import { buildActionFromForm, deriveActionFormValues } from '../../actionCatalogUtils'
import { validateActionCatalogDraft } from '../actionCatalogValidation'

describe('Action Catalog: executor.connection', () => {
  it('drops executor.connection on form round-trip', () => {
    const base: any = {
      id: 'ListExtension',
      label: 'List extension',
      contexts: ['database_card'],
      executor: {
        kind: 'ibcmd_cli',
        driver: 'ibcmd',
        command_id: 'infobase.extension.list',
        connection: {
          remote: 'http://host:1545',
          pid: 123,
          extra_key: 'keep-me',
          offline: {
            config: '/path/to/config',
            dbms: 'PostgreSQL',
            extra_offline: 'keep-offline',
            db_user: 'secret',
            db_pwd: 'secret2',
          },
        },
      },
    }

    const values = deriveActionFormValues(base)
    expect((values as any).executor.connection).toBeUndefined()

    const rebuilt = buildActionFromForm(base, values) as any
    expect(rebuilt.executor.connection).toBeUndefined()
  })

  it('validation rejects executor.connection', () => {
    const badDraft: any = {
      catalog_version: 1,
      extensions: {
        actions: [
          {
            id: 'a',
            label: 'a',
            contexts: ['database_card'],
            executor: {
              kind: 'ibcmd_cli',
              driver: 'ibcmd',
              command_id: 'infobase.extension.list',
              connection: { offline: { db_user: 'u' } },
            },
          },
        ],
      },
    }
    const res = validateActionCatalogDraft(badDraft)
    expect(res.ok).toBe(false)
    expect(res.errors.join('\n')).toMatch(/executor\.connection/i)
  })
})

describe('Action Catalog: capability fixed round-trip', () => {
  it('preserves dynamic fixed payload on form round-trip', () => {
    const base: any = {
      id: 'flags.custom',
      capability: 'extensions.set_flags',
      label: 'Custom fixed',
      contexts: ['bulk_page'],
      executor: {
        kind: 'ibcmd_cli',
        driver: 'ibcmd',
        command_id: 'infobase.extension.set',
        fixed: {
          confirm_dangerous: true,
          timeout_seconds: 120,
          apply_mask: {
            active: true,
            safe_mode: false,
            unsafe_action_protection: false,
          },
          policy: {
            mode: 'strict',
            retries: 2,
          },
          custom_toggle: false,
        },
      },
    }

    const values = deriveActionFormValues(base)
    expect((values as any).executor.fixed.policy).toEqual({ mode: 'strict', retries: 2 })

    const rebuilt = buildActionFromForm(base, values) as any
    expect(rebuilt.executor.fixed).toEqual(base.executor.fixed)
  })

  it('drops fixed group when it is explicitly cleared in form state', () => {
    const base: any = {
      id: 'flags.clear',
      capability: 'extensions.set_flags',
      label: 'Clear fixed',
      contexts: ['bulk_page'],
      executor: {
        kind: 'ibcmd_cli',
        driver: 'ibcmd',
        command_id: 'infobase.extension.set',
        fixed: {
          apply_mask: {
            active: true,
            safe_mode: false,
            unsafe_action_protection: false,
          },
          policy: {
            mode: 'strict',
          },
        },
      },
    }

    const values = deriveActionFormValues(base)
    const fixed = values.executor.fixed as any
    fixed.apply_mask = undefined

    const rebuilt = buildActionFromForm(base, values) as any
    expect(rebuilt.executor.fixed.apply_mask).toBeUndefined()
    expect(rebuilt.executor.fixed.policy).toEqual({ mode: 'strict' })
  })
})

describe('Action Catalog: reserved capabilities', () => {
  it('validation allows multiple extensions.set_flags actions (1->N mapping)', () => {
    const draft: any = {
      catalog_version: 1,
      extensions: {
        actions: [
          {
            id: 'a',
            capability: 'extensions.set_flags',
            label: 'a',
            contexts: ['bulk_page'],
            executor: { kind: 'ibcmd_cli', driver: 'ibcmd', command_id: 'infobase.extension.set' },
          },
          {
            id: 'b',
            capability: 'extensions.set_flags',
            label: 'b',
            contexts: ['bulk_page'],
            executor: { kind: 'ibcmd_cli', driver: 'ibcmd', command_id: 'infobase.extension.set' },
          },
        ],
      },
    }

    const res = validateActionCatalogDraft(draft)
    expect(res.ok).toBe(true)
    expect(res.errors).toEqual([])
  })
})

describe('Action Catalog: fixed schema hints', () => {
  const draftWithPreset: any = {
    catalog_version: 1,
    extensions: {
      actions: [
        {
          id: 'flags.active',
          capability: 'extensions.set_flags',
          label: 'Set active flag',
          contexts: ['bulk_page'],
          executor: {
            kind: 'ibcmd_cli',
            driver: 'ibcmd',
            command_id: 'infobase.extension.set',
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
  }

  it('does not reject capability fixed keys without hints', () => {
    const draft: any = {
      ...draftWithPreset,
      extensions: {
        actions: [
          {
            ...draftWithPreset.extensions.actions[0],
            executor: {
              ...draftWithPreset.extensions.actions[0].executor,
              fixed: {
                ...draftWithPreset.extensions.actions[0].executor.fixed,
                custom_toggle: true,
              },
            },
          },
        ],
      },
    }
    const res = validateActionCatalogDraft(draft)
    expect(res.ok).toBe(true)
    expect(res.errors).toEqual([])
  })

  it('validates fixed payload with backend hints schema', () => {
    const hints = {
      capabilities: {
        'extensions.set_flags': {
          fixed_schema: {
            type: 'object',
            additionalProperties: false,
            properties: {
              apply_mask: {
                type: 'object',
                additionalProperties: false,
                required: ['active', 'safe_mode', 'unsafe_action_protection'],
                properties: {
                  active: { type: 'boolean' },
                  safe_mode: { type: 'boolean' },
                  unsafe_action_protection: { type: 'boolean' },
                },
              },
            },
          },
        },
      },
    }
    const invalidDraft: any = {
      ...draftWithPreset,
      extensions: {
        actions: [
          {
            ...draftWithPreset.extensions.actions[0],
            executor: {
              ...draftWithPreset.extensions.actions[0].executor,
              fixed: {
                apply_mask: {
                  active: true,
                  safe_mode: false,
                  unknown_flag: true,
                },
              },
            },
          },
        ],
      },
    }
    const invalidRes = validateActionCatalogDraft(invalidDraft, { editorHints: hints })
    expect(invalidRes.ok).toBe(false)
    expect(invalidRes.errors.join('\n')).toMatch(/executor\.fixed\.apply_mask: unknown key: unknown_flag/i)

    const validRes = validateActionCatalogDraft(draftWithPreset, { editorHints: hints })
    expect(validRes.ok).toBe(true)
  })
})

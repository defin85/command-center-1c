import { describe, it, expect } from 'vitest'

import { buildActionFromForm, deriveActionFormValues } from '../../actionCatalogUtils'
import { validateActionCatalogDraft } from '../actionCatalogValidation'

describe('Action Catalog: executor.connection', () => {
  it('drops executor.connection on form round-trip', () => {
    const base = {
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
    expect((values as { executor: { connection?: unknown } }).executor.connection).toBeUndefined()

    const rebuilt = buildActionFromForm(base, values) as { executor: { connection?: unknown } }
    expect(rebuilt.executor.connection).toBeUndefined()
  })

  it('validation rejects executor.connection', () => {
    const badDraft = {
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
  it('strips apply_mask preset for extensions.set_flags and preserves other fixed keys', () => {
    const base = {
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
    const valuesFixed = (values as { executor: { fixed: Record<string, unknown> } }).executor.fixed
    expect(valuesFixed.policy).toEqual({ mode: 'strict', retries: 2 })
    expect(valuesFixed.apply_mask).toBeUndefined()

    const rebuilt = buildActionFromForm(base, values) as { executor: { fixed: Record<string, unknown> } }
    expect(rebuilt.executor.fixed.apply_mask).toBeUndefined()
    expect(rebuilt.executor.fixed.policy).toEqual({ mode: 'strict', retries: 2 })
    expect(rebuilt.executor.fixed.custom_toggle).toBe(false)
  })

  it('drops fixed group when it is explicitly cleared in form state', () => {
    const base = {
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
    const fixed = values.executor.fixed as Record<string, unknown>
    fixed.apply_mask = undefined

    const rebuilt = buildActionFromForm(base, values) as { executor: { fixed: Record<string, unknown> } }
    expect(rebuilt.executor.fixed.apply_mask).toBeUndefined()
    expect(rebuilt.executor.fixed.policy).toEqual({ mode: 'strict' })
  })
})

describe('Action Catalog: reserved capabilities', () => {
  it('validation allows multiple extensions.set_flags actions (1->N mapping)', () => {
    const draft = {
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
  const draftWithPreset = {
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

  it('rejects set_flags apply_mask preset even without hints', () => {
    const res = validateActionCatalogDraft(draftWithPreset)
    expect(res.ok).toBe(false)
    expect(res.errors.join('\n')).toMatch(/executor\.fixed\.apply_mask: preset is not allowed/i)
  })

  it('does not reject other fixed keys without hints', () => {
    const draft = {
      ...draftWithPreset,
      extensions: {
        actions: [
          {
            ...draftWithPreset.extensions.actions[0],
            executor: {
              ...draftWithPreset.extensions.actions[0].executor,
              fixed: {
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

  it('target_binding hints work without fixed_schema', () => {
    const hints = {
      capabilities: {
        'extensions.set_flags': {
          target_binding_schema: {
            type: 'object',
            required: ['extension_name_param'],
            properties: {
              extension_name_param: { type: 'string' },
            },
          },
        },
      },
    }

    const invalidRes = validateActionCatalogDraft(draftWithPreset, { editorHints: hints })
    expect(invalidRes.ok).toBe(false)
    expect(invalidRes.errors.join('\n')).toMatch(/executor\.target_binding: is required/i)

    const validDraft = {
      ...draftWithPreset,
      extensions: {
        actions: [
          {
            ...draftWithPreset.extensions.actions[0],
            executor: {
              ...draftWithPreset.extensions.actions[0].executor,
              fixed: undefined,
              target_binding: {
                extension_name_param: 'extension_name',
              },
            },
          },
        ],
      },
    }
    const validRes = validateActionCatalogDraft(validDraft, { editorHints: hints })
    expect(validRes.ok).toBe(true)
  })
})

describe('Action Catalog: target_binding hints', () => {
  const hints = {
    capabilities: {
      'extensions.set_flags': {
        target_binding_schema: {
          type: 'object',
          additionalProperties: false,
          required: ['extension_name_param'],
          properties: {
            extension_name_param: { type: 'string', minLength: 1 },
          },
        },
      },
    },
  }

  it('preserves target_binding on form round-trip', () => {
    const base = {
      id: 'flags.binding',
      capability: 'extensions.set_flags',
      label: 'Set flags binding',
      contexts: ['bulk_page'],
      executor: {
        kind: 'ibcmd_cli',
        driver: 'ibcmd',
        command_id: 'infobase.extension.update',
        target_binding: {
          extension_name_param: 'extension_name',
        },
      },
    }

    const values = deriveActionFormValues(base)
    expect(values.executor.target_binding_extension_name_param).toBe('extension_name')

    const rebuilt = buildActionFromForm(base, values) as { executor: { target_binding: unknown } }
    expect(rebuilt.executor.target_binding).toEqual({ extension_name_param: 'extension_name' })
  })

  it('validates required target_binding with backend hints schema', () => {
    const invalidDraft = {
      catalog_version: 1,
      extensions: {
        actions: [
          {
            id: 'flags.binding.invalid',
            capability: 'extensions.set_flags',
            label: 'Missing binding',
            contexts: ['bulk_page'],
            executor: {
              kind: 'ibcmd_cli',
              driver: 'ibcmd',
              command_id: 'infobase.extension.update',
            },
          },
        ],
      },
    }
    const invalidRes = validateActionCatalogDraft(invalidDraft, { editorHints: hints })
    expect(invalidRes.ok).toBe(false)
    expect(invalidRes.errors.join('\n')).toMatch(/executor\.target_binding: is required/i)

    const validDraft = {
      ...invalidDraft,
      extensions: {
        actions: [
          {
            ...invalidDraft.extensions.actions[0],
            executor: {
              ...invalidDraft.extensions.actions[0].executor,
              target_binding: {
                extension_name_param: 'extension_name',
              },
            },
          },
        ],
      },
    }
    const validRes = validateActionCatalogDraft(validDraft, { editorHints: hints })
    expect(validRes.ok).toBe(true)
  })
})

describe('Action Catalog: canonical kind/driver mapping', () => {
  it('allows omitting driver for canonical executor kinds', () => {
    const draft = {
      catalog_version: 1,
      extensions: {
        actions: [
          {
            id: 'extensions.list.no-driver',
            label: 'List extensions',
            contexts: ['database_card'],
            executor: {
              kind: 'ibcmd_cli',
              command_id: 'infobase.extension.list',
            },
          },
        ],
      },
    }

    const result = validateActionCatalogDraft(draft)
    expect(result.ok).toBe(true)
    expect(result.errors).toEqual([])
  })

  it('fails closed on conflicting kind/driver pairs', () => {
    const draft = {
      catalog_version: 1,
      extensions: {
        actions: [
          {
            id: 'extensions.bad-driver',
            label: 'Bad driver',
            contexts: ['database_card'],
            executor: {
              kind: 'ibcmd_cli',
              driver: 'cli',
              command_id: 'infobase.extension.list',
            },
          },
        ],
      },
    }

    const result = validateActionCatalogDraft(draft)
    expect(result.ok).toBe(false)
    expect(result.errors.join('\n')).toMatch(/executor\.driver: mismatch/i)
  })
})

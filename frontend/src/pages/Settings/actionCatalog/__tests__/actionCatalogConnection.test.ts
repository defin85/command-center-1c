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

describe('Action Catalog: reserved capabilities', () => {
  it('validation rejects duplicate extensions.set_flags', () => {
    const badDraft: any = {
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

    const res = validateActionCatalogDraft(badDraft)
    expect(res.ok).toBe(false)
    expect(res.errors.join('\n')).toMatch(/duplicate reserved capability \(extensions\.set_flags\)/i)
  })
})

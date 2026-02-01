import { describe, it, expect } from 'vitest'

import { buildActionFromForm, deriveActionFormValues } from '../../actionCatalogUtils'
import { validateActionCatalogDraft } from '../actionCatalogValidation'

describe('Action Catalog: executor.connection', () => {
  it('round-trips connection and strips db_user/db_pwd', () => {
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
    expect(values.executor.connection?.remote).toBe('http://host:1545')
    expect(values.executor.connection?.pid).toBe(123)
    expect(values.executor.connection?.offline?.config).toBe('/path/to/config')
    expect(values.executor.connection?.offline?.dbms).toBe('PostgreSQL')

    const rebuilt = buildActionFromForm(base, values) as any
    expect(rebuilt.executor.connection.extra_key).toBe('keep-me')
    expect(rebuilt.executor.connection.offline.extra_offline).toBe('keep-offline')
    expect(rebuilt.executor.connection.offline.db_user).toBeUndefined()
    expect(rebuilt.executor.connection.offline.db_pwd).toBeUndefined()
  })

  it('validation allows executor.connection for ibcmd_cli and rejects secrets', () => {
    const okDraft: any = {
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
              connection: { remote: 'http://host:1545' },
            },
          },
        ],
      },
    }
    expect(validateActionCatalogDraft(okDraft).ok).toBe(true)

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
    expect(res.errors.join('\n')).toMatch(/db_user\/db_pwd/i)
  })
})


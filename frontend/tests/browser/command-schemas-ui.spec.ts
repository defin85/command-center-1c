import { test, expect, type Page } from '@playwright/test'

type AnyRecord = Record<string, any>

async function fulfillJson(route: any, data: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(data),
    headers: {
      'cache-control': 'no-store',
    },
  })
}

async function setupAuth(page: Page) {
  await page.addInitScript(() => {
    ;(window as any).__CC1C_ENV__ = {
      VITE_BASE_HOST: '127.0.0.1',
      VITE_API_URL: 'http://127.0.0.1:5173',
      VITE_WS_HOST: '127.0.0.1:5173',
    }
    localStorage.setItem('auth_token', 'test-token')
  })
}

const deepCopy = <T,>(value: T): T => {
  try {
    return JSON.parse(JSON.stringify(value)) as T
  } catch (_err) {
    return value
  }
}

const isPlainObject = (value: unknown): value is AnyRecord => (
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)
)

const deepMerge = (target: AnyRecord, patch: AnyRecord): void => {
  for (const [key, value] of Object.entries(patch)) {
    const current = target[key]
    if (isPlainObject(value) && isPlainObject(current)) {
      deepMerge(current, value)
      continue
    }
    target[key] = value
  }
}

function buildEffectiveCatalog(base: AnyRecord, overridesCatalog: AnyRecord): AnyRecord {
  const effective = deepCopy(base)
  const commandsPatch = overridesCatalog?.overrides?.commands_by_id
  if (!isPlainObject(commandsPatch)) return effective

  if (!isPlainObject(effective.commands_by_id)) {
    effective.commands_by_id = {}
  }

  for (const [commandId, patch] of Object.entries(commandsPatch)) {
    if (!isPlainObject(patch)) continue
    const current = effective.commands_by_id[commandId]
    if (!isPlainObject(current)) {
      effective.commands_by_id[commandId] = deepCopy(patch)
      continue
    }
    deepMerge(current, patch)
  }
  return effective
}

async function setupApiMocks(
  page: Page,
  state: {
    baseCatalog: AnyRecord
    baseApprovedVersion: string
    baseLatestVersion: string
    activeOverridesVersion: string
    overridesByVersion: Record<string, AnyRecord>
    reasonsByVersion: Record<string, string>
    captures: {
      overridesUpdate: any[]
      overridesRollback: any[]
    }
  }
) {
  await page.route('**/api/v2/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    const currentEtag = `etag-${state.activeOverridesVersion}`

    if (method === 'GET' && path === '/api/v2/system/me/') {
      return fulfillJson(route, { id: 1, username: 'admin', is_staff: false })
    }

    if (method === 'GET' && path === '/api/v2/rbac/get-effective-access/') {
      return fulfillJson(route, { clusters: [], databases: [] })
    }

    if (method === 'GET' && path === '/api/v2/rbac/list-roles/') {
      return fulfillJson(route, { roles: [], count: 0, total: 0 })
    }

    if (method === 'GET' && path === '/api/v2/settings/command-schemas/audit/') {
      return fulfillJson(route, { items: [], count: 0, total: 0 })
    }

    if (method === 'GET' && path === '/api/v2/settings/command-schemas/editor/') {
      const driver = (url.searchParams.get('driver') || '').trim().toLowerCase()
      const overridesCatalog = state.overridesByVersion[state.activeOverridesVersion]
      const effectiveCatalog = buildEffectiveCatalog(state.baseCatalog, overridesCatalog)
      return fulfillJson(route, {
        driver,
        etag: currentEtag,
        base: {
          approved_version: state.baseApprovedVersion,
          approved_version_id: 'base-id-approved',
          latest_version: state.baseLatestVersion,
          latest_version_id: 'base-id-latest',
        },
        overrides: {
          active_version: state.activeOverridesVersion,
          active_version_id: `ovr-id-${state.activeOverridesVersion}`,
        },
        catalogs: {
          base: state.baseCatalog,
          overrides: overridesCatalog,
          effective: {
            base_version: state.baseApprovedVersion,
            base_version_id: 'base-id-approved',
            base_alias: 'approved',
            overrides_version: state.activeOverridesVersion,
            overrides_version_id: `ovr-id-${state.activeOverridesVersion}`,
            catalog: effectiveCatalog,
            source: 'mock',
          },
        },
      })
    }

    if (method === 'GET' && path === '/api/v2/settings/command-schemas/versions/') {
      const driver = (url.searchParams.get('driver') || '').trim().toLowerCase()
      const artifact = (url.searchParams.get('artifact') || '').trim().toLowerCase()
      if (artifact !== 'overrides') {
        return fulfillJson(route, { driver, artifact, versions: [], count: 0 })
      }

      const versions = Object.keys(state.overridesByVersion)
        .sort()
        .reverse()
        .map((version) => ({
          id: `ovr-id-${version}`,
          version,
          created_at: new Date().toISOString(),
          created_by: 'tester',
          metadata: { reason: state.reasonsByVersion[version] ?? '' },
        }))

      return fulfillJson(route, { driver, artifact, versions, count: versions.length })
    }

    if (method === 'POST' && path === '/api/v2/settings/command-schemas/overrides/update/') {
      const body = request.postDataJSON()
      state.captures.overridesUpdate.push(body)

      if (body.expected_etag && body.expected_etag !== currentEtag) {
        return fulfillJson(route, { success: false, error: { code: 'CONFLICT', message: 'conflict' } }, 409)
      }

      const nextIndex = Object.keys(state.overridesByVersion).length
      const nextVersion = `ovr-${nextIndex}`
      state.overridesByVersion[nextVersion] = body.catalog
      state.reasonsByVersion[nextVersion] = String(body.reason || '')
      state.activeOverridesVersion = nextVersion

      return fulfillJson(route, { driver: body.driver, overrides_version: nextVersion, etag: `etag-${nextVersion}` })
    }

    if (method === 'POST' && path === '/api/v2/settings/command-schemas/overrides/rollback/') {
      const body = request.postDataJSON()
      state.captures.overridesRollback.push(body)

      if (body.expected_etag && body.expected_etag !== currentEtag) {
        return fulfillJson(route, { success: false, error: { code: 'CONFLICT', message: 'conflict' } }, 409)
      }

      const version = String(body.version || '')
      if (!state.overridesByVersion[version]) {
        return fulfillJson(route, { success: false, error: { code: 'VERSION_NOT_FOUND', message: 'not found' } }, 400)
      }

      state.activeOverridesVersion = version

      return fulfillJson(route, { driver: body.driver, overrides_version: version, etag: `etag-${version}` })
    }

    return fulfillJson(route, {}, 200)
  })
}

test('Command Schemas: load + save + rollback (smoke)', async ({ page }) => {
  const baseCatalog = {
    catalog_version: 2,
    driver: 'ibcmd',
    platform_version: '8.3.27',
    source: { type: 'its_import', doc_id: 'TI000', doc_url: 'http://example' },
    generated_at: '2026-01-01T00:00:00Z',
    commands_by_id: {
      'ibcmd.infobase.dump': {
        label: 'Dump',
        description: 'Dump infobase',
        argv: ['ibcmd', 'infobase', 'dump'],
        scope: 'per_database',
        risk_level: 'safe',
        params_by_name: {
          remote: { kind: 'flag', required: true, expects_value: true, flag: '--remote' },
        },
      },
    },
  }

  const captures = { overridesUpdate: [] as any[], overridesRollback: [] as any[] }
  const state = {
    baseCatalog,
    baseApprovedVersion: 'v-base',
    baseLatestVersion: 'v-base',
    activeOverridesVersion: 'ovr-0',
    overridesByVersion: {
      'ovr-0': { catalog_version: 2, driver: 'ibcmd', overrides: { commands_by_id: {} } },
    } as Record<string, AnyRecord>,
    reasonsByVersion: { 'ovr-0': 'initial' } as Record<string, string>,
    captures,
  }

  await setupAuth(page)
  await setupApiMocks(page, state)

  await page.goto('/settings/command-schemas', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Command Schemas', exact: true })).toBeVisible()
  await expect(page.getByTestId('command-schemas-command-ibcmd.infobase.dump')).toBeVisible()

  await page.getByTestId('command-schemas-command-ibcmd.infobase.dump').click()
  await expect(page.getByTestId('command-schemas-basics-label-input')).toBeVisible()

  await page.getByTestId('command-schemas-basics-label-override').click()
  await page.getByTestId('command-schemas-basics-label-input').fill('Dump updated')

  const unsaved = page.locator('[data-testid="command-schemas-unsaved-banner"]')
  await expect(unsaved).toHaveCount(1)

  await page.getByTestId('command-schemas-save-open').click()
  await page.getByTestId('command-schemas-save-reason').fill('test save')
  await page.getByTestId('command-schemas-save-confirm').click()

  await expect(unsaved).toHaveCount(0)
  await expect.poll(() => captures.overridesUpdate.length).toBe(1)

  await page.getByTestId('command-schemas-rollback-open').click()
  await expect(page.getByText('Rollback overrides', { exact: true })).toBeVisible()

  const rollbackSelect = page.getByTestId('command-schemas-rollback-version')
  await rollbackSelect.locator('.ant-select-selector').click()
  const dropdown = page.locator('.ant-select-dropdown:visible')
  await expect(dropdown).toBeVisible()
  await rollbackSelect.locator('input').fill('ovr-0')
  await page.keyboard.press('Enter')
  await page.getByTestId('command-schemas-rollback-reason').fill('test rollback')
  await page.getByTestId('command-schemas-rollback-confirm').click()

  await expect.poll(() => captures.overridesRollback.length).toBe(1)
  await expect(page.getByText('Overrides active: ovr-0')).toBeVisible()
})

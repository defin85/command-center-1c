import { test, expect, type Locator, type Page, type Route } from '@playwright/test'

type MockUser = { id: number; username: string; is_staff?: boolean }
type MockRole = { id: number; name: string; users_count: number; permissions_count: number; permission_codes: string[] }
type MockCluster = { id: string; name: string }
type MockDatabase = { id: string; name: string; cluster_id: string | null }
type MockDbmsUserMapping = {
  id: number
  database_id: string
  user?: { id: number; username: string } | null
  db_username: string
  db_password_configured: boolean
  auth_type?: string
  is_service?: boolean
  notes?: string
  created_at: string
  updated_at: string
}

declare global {
  interface Window {
    __CC1C_ENV__?: Record<string, string>
  }
}

type MockState = {
  me: { id: number; username: string; is_staff: boolean }
  users: MockUser[]
  roles: MockRole[]
  userRoleIdsByUserId: Record<number, number[]>
  clusters: MockCluster[]
  databases: MockDatabase[]
  dbmsUsers: MockDbmsUserMapping[]
  databasePermissions: Array<{
    user: { id: number; username: string }
    database: { id: string; name: string; cluster_id: string | null }
    level: string
    granted_by: { id: number; username: string } | null
    granted_at: string
      notes?: string
  }>
  effectiveAccess: unknown
}

async function fulfillJson(route: Route, data: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(data),
    headers: {
      'cache-control': 'no-store',
    },
  })
}

function defaultState(): MockState {
  const clusters: MockCluster[] = [
    { id: 'cl-1', name: 'Cluster One' },
    { id: 'cl-2', name: 'Cluster Two' },
  ]

  const databases: MockDatabase[] = [
    { id: 'db-1', name: 'Database One', cluster_id: 'cl-1' },
    { id: 'db-2', name: 'Database Two', cluster_id: 'cl-1' },
    { id: 'db-3', name: 'Database Three', cluster_id: 'cl-2' },
  ]

  return {
    me: { id: 1, username: 'admin', is_staff: true },
    users: [
      { id: 101, username: 'alice' },
      { id: 102, username: 'bob' },
    ],
    roles: [
      { id: 201, name: 'Ops', users_count: 1, permissions_count: 1, permission_codes: ['perm.ops'] },
    ],
    userRoleIdsByUserId: {
      101: [201],
      102: [],
    },
    clusters,
    databases,
    dbmsUsers: [],
    databasePermissions: [
      {
        user: { id: 101, username: 'alice' },
        database: { id: 'db-1', name: 'Database One', cluster_id: 'cl-1' },
        level: 'VIEW',
        granted_by: null,
        granted_at: new Date().toISOString(),
      },
    ],
    effectiveAccess: {
      user: { id: 101, username: 'alice' },
      clusters: [
        {
          cluster: { id: 'cl-1', name: 'Cluster One' },
          level: 'VIEW',
          sources: [{ source: 'direct', level: 'VIEW' }],
        },
        {
          cluster: { id: 'cl-2', name: 'Cluster Two' },
          level: 'ADMIN',
          sources: [{ source: 'group', level: 'ADMIN' }],
        },
      ],
      databases: [],
      operation_templates: [],
      workflow_templates: [],
      artifacts: [],
    },
  }
}

async function setupAuth(page: Page) {
  await page.addInitScript(() => {
    window.__CC1C_ENV__ = {
      VITE_BASE_HOST: '127.0.0.1',
      VITE_API_URL: 'http://127.0.0.1:15173',
      VITE_WS_HOST: '127.0.0.1:15173',
    }
    localStorage.setItem('auth_token', 'test-token')
  })
}

async function setupApiMocks(
  page: Page,
  state: MockState,
  captures?: {
    setUserRoles?: unknown[]
  }
) {
  await page.route('**/api/v2/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    if (method === 'GET' && path === '/api/v2/system/me/') {
      return fulfillJson(route, state.me)
    }

    if (method === 'GET' && path === '/api/v2/rbac/list-users/') {
      const search = (url.searchParams.get('search') ?? '').trim().toLowerCase()
      const filtered = search
        ? state.users.filter((u) => u.username.toLowerCase().includes(search) || String(u.id).includes(search))
        : state.users
      return fulfillJson(route, { users: filtered, count: filtered.length, total: filtered.length })
    }

    if (method === 'GET' && path === '/api/v2/rbac/list-users-with-roles/') {
      const search = (url.searchParams.get('search') ?? '').trim().toLowerCase()
      const roleIdRaw = url.searchParams.get('role_id')
      const roleId = roleIdRaw ? Number(roleIdRaw) : null
      const limit = Number(url.searchParams.get('limit') ?? '50')
      const offset = Number(url.searchParams.get('offset') ?? '0')

      const getRolesForUser = (userId: number) => {
        const roleIds = state.userRoleIdsByUserId[userId] ?? []
        return roleIds
          .map((id) => state.roles.find((r) => r.id === id))
          .filter((r): r is MockRole => Boolean(r))
          .map((r) => ({ id: r.id, name: r.name }))
      }

      let filtered = state.users
      if (search) {
        filtered = filtered.filter((u) => u.username.toLowerCase().includes(search) || String(u.id).includes(search))
      }
      if (typeof roleId === 'number' && Number.isFinite(roleId)) {
        filtered = filtered.filter((u) => (state.userRoleIdsByUserId[u.id] ?? []).includes(roleId))
      }

      const pageItems = filtered.slice(offset, offset + limit)
      const users = pageItems.map((u) => ({ id: u.id, username: u.username, roles: getRolesForUser(u.id) }))
      return fulfillJson(route, { users, count: users.length, total: filtered.length })
    }

    if (method === 'GET' && path === '/api/v2/rbac/list-roles/') {
      return fulfillJson(route, { roles: state.roles, count: state.roles.length, total: state.roles.length })
    }

    if (method === 'GET' && path === '/api/v2/rbac/list-capabilities/') {
      return fulfillJson(route, { capabilities: [{ code: 'perm.ops', name: 'perm.ops', app_label: 'rbac', codename: 'perm_ops', exists: true }], count: 1 })
    }

    if (method === 'GET' && path === '/api/v2/rbac/ref-clusters/') {
      return fulfillJson(route, { clusters: state.clusters, count: state.clusters.length, total: state.clusters.length })
    }

    if (method === 'GET' && path === '/api/v2/rbac/ref-databases/') {
      const clusterId = url.searchParams.get('cluster_id')
      const search = (url.searchParams.get('search') ?? '').trim().toLowerCase()
      const limit = Number(url.searchParams.get('limit') ?? '50')
      const offset = Number(url.searchParams.get('offset') ?? '0')

      let filtered = state.databases
      if (clusterId) {
        filtered = filtered.filter((db) => db.cluster_id === clusterId)
      }
      if (search) {
        filtered = filtered.filter((db) => db.name.toLowerCase().includes(search) || db.id.toLowerCase().includes(search))
      }

      const pageItems = filtered.slice(offset, offset + limit)
      return fulfillJson(route, { databases: pageItems, count: pageItems.length, total: filtered.length })
    }

    if (method === 'GET' && path === '/api/v2/rbac/ref-operation-templates/') {
      return fulfillJson(route, { templates: [], count: 0, total: 0 })
    }

    if (method === 'GET' && path === '/api/v2/rbac/ref-workflow-templates/') {
      return fulfillJson(route, { templates: [], count: 0, total: 0 })
    }

    if (method === 'GET' && path === '/api/v2/rbac/ref-artifacts/') {
      return fulfillJson(route, { artifacts: [], count: 0, total: 0 })
    }

    if (method === 'GET' && path === '/api/v2/rbac/list-database-permissions/') {
      return fulfillJson(route, { permissions: state.databasePermissions, count: state.databasePermissions.length, total: state.databasePermissions.length })
    }

    if (method === 'GET' && path === '/api/v2/rbac/get-effective-access/') {
      return fulfillJson(route, state.effectiveAccess)
    }

    if (method === 'GET' && path === '/api/v2/rbac/list-admin-audit/') {
      return fulfillJson(route, { items: [], count: 0, total: 0 })
    }

    if (method === 'GET' && path === '/api/v2/databases/list-dbms-users/') {
      const databaseId = url.searchParams.get('database_id')
      const search = (url.searchParams.get('search') ?? '').trim().toLowerCase()
      const authType = (url.searchParams.get('auth_type') ?? '').trim()
      const isServiceRaw = url.searchParams.get('is_service')
      const hasUserRaw = url.searchParams.get('has_user')
      const limit = Number(url.searchParams.get('limit') ?? '100')
      const offset = Number(url.searchParams.get('offset') ?? '0')

      let filtered = state.dbmsUsers.filter((u) => u.database_id === databaseId)
      if (search) {
        filtered = filtered.filter((u) => (
          u.db_username.toLowerCase().includes(search)
          || (u.user?.username ?? '').toLowerCase().includes(search)
          || String(u.user?.id ?? '').includes(search)
        ))
      }
      if (authType) {
        filtered = filtered.filter((u) => (u.auth_type ?? '') === authType)
      }
      if (isServiceRaw === 'true') {
        filtered = filtered.filter((u) => Boolean(u.is_service))
      } else if (isServiceRaw === 'false') {
        filtered = filtered.filter((u) => !u.is_service)
      }
      if (hasUserRaw === 'true') {
        filtered = filtered.filter((u) => Boolean(u.user))
      } else if (hasUserRaw === 'false') {
        filtered = filtered.filter((u) => !u.user)
      }

      const pageItems = filtered.slice(offset, offset + limit)
      return fulfillJson(route, { users: pageItems, count: pageItems.length, total: filtered.length })
    }

    if (method === 'POST' && path === '/api/v2/databases/create-dbms-user/') {
      const body = request.postDataJSON() as {
        database_id: string
        user_id?: number | null
        db_username: string
        auth_type?: string
        is_service?: boolean
        notes?: string
      }
      const now = new Date().toISOString()
      const nextId = Math.max(0, ...state.dbmsUsers.map((u) => u.id)) + 1
      const isService = Boolean(body.is_service)
      const user = !isService && typeof body.user_id === 'number'
        ? state.users.find((u) => u.id === body.user_id) ?? null
        : null
      const record: MockDbmsUserMapping = {
        id: nextId,
        database_id: body.database_id,
        user: user ? { id: user.id, username: user.username } : null,
        db_username: body.db_username,
        db_password_configured: false,
        auth_type: body.auth_type ?? 'local',
        is_service: isService,
        notes: body.notes,
        created_at: now,
        updated_at: now,
      }
      state.dbmsUsers.unshift(record)
      return fulfillJson(route, record)
    }

    if (method === 'POST' && path === '/api/v2/databases/update-dbms-user/') {
      const body = request.postDataJSON() as {
        id: number
        user_id?: number | null
        db_username?: string
        auth_type?: string
        is_service?: boolean
        notes?: string
      }
      const record = state.dbmsUsers.find((u) => u.id === body.id)
      if (!record) return fulfillJson(route, {}, 404)
      const now = new Date().toISOString()
      const isService = typeof body.is_service === 'boolean' ? body.is_service : Boolean(record.is_service)
      record.is_service = isService
      if (typeof body.db_username === 'string') record.db_username = body.db_username
      if (typeof body.auth_type === 'string') record.auth_type = body.auth_type
      if (typeof body.notes === 'string') record.notes = body.notes
      if (body.user_id === null || body.user_id === undefined) {
        record.user = null
      } else if (!isService && typeof body.user_id === 'number') {
        const user = state.users.find((u) => u.id === body.user_id)
        record.user = user ? { id: user.id, username: user.username } : null
      }
      record.updated_at = now
      return fulfillJson(route, record)
    }

    if (method === 'POST' && path === '/api/v2/databases/delete-dbms-user/') {
      const body = request.postDataJSON() as { id: number }
      state.dbmsUsers = state.dbmsUsers.filter((u) => u.id !== body.id)
      return fulfillJson(route, {})
    }

    if (method === 'POST' && path === '/api/v2/databases/set-dbms-user-password/') {
      const body = request.postDataJSON() as { id: number; password: string }
      const record = state.dbmsUsers.find((u) => u.id === body.id)
      if (!record) return fulfillJson(route, {}, 404)
      record.db_password_configured = true
      record.updated_at = new Date().toISOString()
      return fulfillJson(route, record)
    }

    if (method === 'POST' && path === '/api/v2/databases/reset-dbms-user-password/') {
      const body = request.postDataJSON() as { id: number }
      const record = state.dbmsUsers.find((u) => u.id === body.id)
      if (!record) return fulfillJson(route, {}, 404)
      record.db_password_configured = false
      record.updated_at = new Date().toISOString()
      return fulfillJson(route, {})
    }

    if (method === 'POST' && path === '/api/v2/rbac/set-user-roles/') {
      const body = request.postDataJSON() as { user_id: number; group_ids: number[]; mode?: string; reason: string }
      captures?.setUserRoles?.push(body)

      const user = state.users.find((u) => u.id === body.user_id)
      if (!user) return fulfillJson(route, {}, 404)

      const mode = body.mode ?? 'replace'
      const selectedIds = Array.isArray(body.group_ids) ? body.group_ids : []

      const current = new Set<number>(state.userRoleIdsByUserId[body.user_id] ?? [])
      if (mode === 'replace') {
        state.userRoleIdsByUserId[body.user_id] = Array.from(new Set(selectedIds)).sort((a, b) => a - b)
      } else if (mode === 'add') {
        selectedIds.forEach((id) => current.add(id))
        state.userRoleIdsByUserId[body.user_id] = Array.from(current).sort((a, b) => a - b)
      } else if (mode === 'remove') {
        selectedIds.forEach((id) => current.delete(id))
        state.userRoleIdsByUserId[body.user_id] = Array.from(current).sort((a, b) => a - b)
      }

      const roles = (state.userRoleIdsByUserId[body.user_id] ?? [])
        .map((id) => state.roles.find((r) => r.id === id))
        .filter((r): r is MockRole => Boolean(r))
        .map((r) => ({ id: r.id, name: r.name }))

      return fulfillJson(route, { user: { id: user.id, username: user.username }, roles })
    }

    return fulfillJson(route, {}, 200)
  })
}

test('RBAC: no English UI tokens (smoke)', async ({ page }) => {
  const state = defaultState()

  await setupAuth(page)
  await setupApiMocks(page, state)

  await page.goto('/rbac', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'RBAC', exact: true })).toBeVisible()

  const forbiddenText = [
    'Clear',
    'Clear selection',
    'Select cluster',
    'Select database',
    'Search clusters',
    'Search databases',
    'Loading...',
    'Load more...',
    'Grant',
    'Revoke',
    'Reason',
    'Reason (required)',
    'Notes (optional)',
    'Resource',
    'Effective access',
    'Audit',
    'Infobase Users',
    'Create Role',
    'Role name',
    'Rename role',
    'Save',
    'Replace',
    'Apply',
    'Current roles',
    'Clusters',
    'Databases',
  ]

  const assertNoEnglish = async (scope: Locator) => {
    for (const token of forbiddenText) {
      await expect(scope.locator(`text=${token}`), `Unexpected EN token in UI: ${token}`).toHaveCount(0)
      await expect(scope.locator(`[placeholder*="${token}"]`), `Unexpected EN token in placeholders: ${token}`).toHaveCount(0)
    }
  }

  const main = page.getByRole('main')
  await assertNoEnglish(main)

  const grantResourcePicker = page.getByTestId('rbac-permissions-grant-resource')
  await expect(grantResourcePicker).toBeVisible()

  const openButton = grantResourcePicker.locator('button').first()
  await openButton.click()
  const modal = page.locator('.ant-modal').first()
  await expect(modal).toBeVisible()
  await assertNoEnglish(main)
  await assertNoEnglish(modal)

  await page.keyboard.press('Escape')
  await expect(modal).toBeHidden()

  await page.getByTestId('rbac-tab-user-roles').click()
  await expect(page.getByTestId('rbac-user-roles-edit-101')).toBeVisible()
  await assertNoEnglish(main)

  await page.getByTestId('rbac-tab-effective-access').click()
  await expect(page.getByTestId('rbac-effective-access-refresh')).toBeVisible()
  await assertNoEnglish(main)

  await page.getByTestId('rbac-tab-audit').click()
  await expect(page.getByTestId('rbac-audit-panel')).toBeVisible()
  await assertNoEnglish(main)

  await page.getByTestId('rbac-tab-permissions').click()
  await expect(page.getByTestId('rbac-permissions-grant-resource')).toBeVisible()
  await assertNoEnglish(main)
})

test('RBAC: user roles replace empty shows guard + diff', async ({ page }) => {
  const state = defaultState()
  const setUserRoles: unknown[] = []

  await setupAuth(page)
  await setupApiMocks(page, state, { setUserRoles })

  await page.goto('/rbac', { waitUntil: 'domcontentloaded' })

  await page.getByTestId('rbac-tab-user-roles').click()
  await expect(page.getByTestId('rbac-user-roles-edit-101')).toBeVisible()
  await page.getByTestId('rbac-user-roles-edit-101').click()

  await expect(page.getByTestId('rbac-user-roles-editor')).toBeVisible()

  const roleIdsSelect = page.getByTestId('rbac-user-roles-editor-group-ids')
  await roleIdsSelect.hover()
  const clearIcon = roleIdsSelect.locator('.ant-select-clear')
  if (await clearIcon.count()) {
    await clearIcon.click()
  } else {
    const removeIcons = roleIdsSelect.locator('.ant-select-selection-item-remove')
    while (await removeIcons.count()) {
      await removeIcons.first().click()
    }
  }

  await page.getByTestId('rbac-user-roles-editor-reason').fill('test reason')
  await page.getByTestId('rbac-user-roles-editor-ok').click()

  await expect(page.getByTestId('rbac-user-roles-confirm-content')).toBeVisible()
  await expect(page.getByTestId('rbac-user-roles-confirm-remove-all-warning')).toBeVisible()
  await expect(page.getByTestId('rbac-user-roles-confirm-selected-count')).toContainText('0')
  await expect(page.getByTestId('rbac-user-roles-confirm-next-count')).toContainText('0')
  await expect(page.getByTestId('rbac-user-roles-confirm-selected-roles')).toContainText('-')
  await expect(page.getByTestId('rbac-user-roles-confirm-current-roles')).toContainText('Ops')
  await expect(page.getByTestId('rbac-user-roles-confirm-diff-added')).toContainText('-')
  await expect(page.getByTestId('rbac-user-roles-confirm-diff-removed')).toContainText('Ops')

  await page.getByTestId('rbac-user-roles-confirm-ok').click()

  await expect.poll(() => setUserRoles.length).toBe(1)
  expect(setUserRoles[0]).toMatchObject({
    user_id: 101,
    group_ids: [],
    mode: 'replace',
    reason: 'test reason',
  })
})

test('RBAC: DBMS user mappings CRUD + password configured (smoke)', async ({ page }) => {
  const state = defaultState()

  await setupAuth(page)
  await setupApiMocks(page, state)

  await page.goto('/rbac', { waitUntil: 'domcontentloaded' })

  await page.getByTestId('rbac-tab-dbms-users').click()
  await expect(page.locator('text=Пользователи DBMS').first()).toBeVisible()

  const toolbarDbSelect = page.getByTestId('rbac-dbms-users-toolbar-database')
  await toolbarDbSelect.click()
  await page.locator('.ant-select-dropdown').last().getByText('Database One').click()

  await expect(page.getByText('Выберите базу, чтобы посмотреть DBMS mappings')).toHaveCount(0)

  await page.getByTestId('rbac-dbms-user-form-db-username').fill('db_user_1')

  const userSelect = page.getByTestId('rbac-dbms-user-form-user-id')
  await userSelect.click()
  await page.locator('.ant-select-dropdown').last().getByText('alice').click()

  await page.getByTestId('rbac-dbms-user-form-save').click()

  const row = page.locator('tr').filter({ hasText: 'db_user_1' }).first()
  await expect(row).toBeVisible()
  await expect(row).toContainText('Не задан')

  await row.getByText('Установить пароль').click()
  await page.getByTestId('rbac-dbms-user-set-password-input').fill('secret')
  await page.getByTestId('rbac-dbms-user-set-password-ok').click()

  await expect(row).toContainText('Задан')

  await row.getByText('Редактировать').click()
  await page.getByTestId('rbac-dbms-user-form-db-username').fill('db_user_2')
  await page.getByTestId('rbac-dbms-user-form-save').click()

  const updatedRow = page.locator('tr').filter({ hasText: 'db_user_2' }).first()
  await expect(updatedRow).toBeVisible()

  await updatedRow.getByText('Сбросить пароль').click()
  await page.getByTestId('rbac-dbms-user-reset-password-ok').click()
  await expect(updatedRow).toContainText('Не задан')

  await updatedRow.getByText('Удалить').click()
  await page.locator('.ant-modal').last().getByRole('button', { name: 'Удалить' }).click()
  await expect(page.locator('tr').filter({ hasText: 'db_user_2' })).toHaveCount(0)
})

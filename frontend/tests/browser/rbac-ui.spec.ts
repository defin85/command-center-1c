import { test, expect, type Locator, type Page } from '@playwright/test'

type MockUser = { id: number; username: string; is_staff?: boolean }
type MockRole = { id: number; name: string; users_count: number; permissions_count: number; permission_codes: string[] }
type MockCluster = { id: string; name: string }
type MockDatabase = { id: string; name: string; cluster_id: string | null }

type MockState = {
  me: { id: number; username: string; is_staff: boolean }
  users: MockUser[]
  roles: MockRole[]
  clusters: MockCluster[]
  databases: MockDatabase[]
  databasePermissions: Array<{
    user: { id: number; username: string }
    database: { id: string; name: string; cluster_id: string | null }
    level: string
    granted_by: { id: number; username: string } | null
    granted_at: string
    notes?: string
  }>
  effectiveAccess: any
}

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
    clusters,
    databases,
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
    ;(window as any).__CC1C_ENV__ = {
      VITE_BASE_HOST: '127.0.0.1',
      VITE_API_URL: 'http://127.0.0.1:5173',
      VITE_WS_HOST: '127.0.0.1:5173',
    }
    localStorage.setItem('auth_token', 'test-token')
  })
}

async function setupApiMocks(
  page: Page,
  state: MockState,
  captures?: {
    grantDatabase?: any[]
    revokeDatabase?: any[]
    createRole?: any[]
    updateRole?: any[]
    effectiveAccess?: any[]
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

    if (method === 'POST' && path === '/api/v2/rbac/grant-database-permission/') {
      const body = request.postDataJSON()
      captures?.grantDatabase?.push(body)
      return fulfillJson(route, { created: true, permission: body })
    }

    if (method === 'POST' && path === '/api/v2/rbac/revoke-database-permission/') {
      const body = request.postDataJSON()
      captures?.revokeDatabase?.push(body)
      return fulfillJson(route, { deleted: true })
    }

    if (method === 'POST' && path === '/api/v2/rbac/create-role/') {
      const body = request.postDataJSON() as { name: string; reason: string }
      captures?.createRole?.push(body)
      const nextId = Math.max(0, ...state.roles.map((r) => r.id)) + 1
      state.roles.push({ id: nextId, name: body.name, users_count: 0, permissions_count: 0, permission_codes: [] })
      return fulfillJson(route, { id: nextId, name: body.name })
    }

    if (method === 'POST' && path === '/api/v2/rbac/update-role/') {
      const body = request.postDataJSON() as { group_id: number; name: string; reason: string }
      captures?.updateRole?.push(body)
      const role = state.roles.find((r) => r.id === body.group_id)
      if (role) role.name = body.name
      return fulfillJson(route, { id: body.group_id, name: body.name })
    }

    if (method === 'GET' && path === '/api/v2/rbac/get-effective-access/') {
      captures?.effectiveAccess?.push(Object.fromEntries(url.searchParams.entries()))
      return fulfillJson(route, state.effectiveAccess)
    }

    if (method === 'GET' && path === '/api/v2/rbac/list-admin-audit/') {
      return fulfillJson(route, { items: [], count: 0, total: 0 })
    }

    return fulfillJson(route, { error: `unmocked ${method} ${path}` }, 500)
  })
}

async function selectAntdOption(page: Page, optionText: string) {
  await page.locator('.ant-select-dropdown').getByText(optionText, { exact: true }).click()
}

async function openAndSelectDatabaseInPicker(page: Page, trigger: Locator, databaseName: string) {
  await trigger.click()
  await expect(page.getByText('Select database', { exact: true })).toBeVisible()

  const clusterNode = page.locator('.ant-tree-treenode').filter({ hasText: 'Cluster One' }).first()
  await clusterNode.locator('.ant-tree-switcher').click()
  await expect(page.locator('.ant-tree-treenode').filter({ hasText: databaseName }).first()).toBeVisible()
  await page.locator('.ant-tree-treenode').filter({ hasText: databaseName }).first().click()
}

test('RBAC: clusters->databases tree is usable in picker', async ({ page }) => {
  const state = defaultState()
  await setupAuth(page)
  await setupApiMocks(page, state)

  await page.goto('/rbac', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('button', { name: 'Grant', exact: true })).toBeVisible()

  const grantForm = page.locator('form').filter({ has: page.getByRole('button', { name: 'Grant', exact: true }) }).first()
  const resourcePickerGroup = grantForm.locator('.ant-space-compact').filter({ hasText: 'Clear' }).first()
  const resourcePickerButton = resourcePickerGroup.locator('button').first()

  await openAndSelectDatabaseInPicker(page, resourcePickerButton, 'Database One')
  await expect(resourcePickerButton).toHaveText(/Database One/)
})

test('RBAC: grant and revoke require reason (database permission)', async ({ page }) => {
  const state = defaultState()
  const grantDatabase: any[] = []
  const revokeDatabase: any[] = []

  await setupAuth(page)
  await setupApiMocks(page, state, { grantDatabase, revokeDatabase })

  await page.goto('/rbac', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('button', { name: 'Grant', exact: true })).toBeVisible()

  const grantForm = page.locator('form').filter({ has: page.getByRole('button', { name: 'Grant', exact: true }) }).first()
  const resourcePickerGroup = grantForm.locator('.ant-space-compact').filter({ hasText: 'Clear' }).first()
  const resourcePickerButton = resourcePickerGroup.locator('button').first()

  await grantForm.locator('.ant-select').first().click()
  await selectAntdOption(page, 'alice #101')

  await openAndSelectDatabaseInPicker(page, resourcePickerButton, 'Database One')

  await grantForm.locator('input[placeholder="Reason"]').fill('test grant')
  await grantForm.getByRole('button', { name: 'Grant', exact: true }).click()

  await expect.poll(() => grantDatabase.length).toBe(1)
  expect(grantDatabase[0]).toMatchObject({
    user_id: 101,
    database_id: 'db-1',
    level: 'VIEW',
    reason: 'test grant',
  })

  const permissionsCard = page.locator('.ant-card').filter({ has: page.locator('.ant-card-head-title', { hasText: 'Permissions' }) }).first()
  const permissionRow = permissionsCard.locator('tr').filter({ hasText: 'Database One' }).first()
  await permissionRow.getByRole('button', { name: 'Revoke', exact: true }).click()
  await page.getByPlaceholder('Reason (required)').fill('test revoke')
  await page.getByRole('button', { name: 'Confirm', exact: true }).click()

  await expect.poll(() => revokeDatabase.length).toBe(1)
  expect(revokeDatabase[0]).toMatchObject({
    user_id: 101,
    database_id: 'db-1',
    reason: 'test revoke',
  })
})

test('RBAC: create and rename role require reason', async ({ page }) => {
  const state = defaultState()
  const createRole: any[] = []
  const updateRole: any[] = []

  await setupAuth(page)
  await setupApiMocks(page, state, { createRole, updateRole })

  await page.goto('/rbac', { waitUntil: 'domcontentloaded' })

  const rolesModeToggle = page.locator('.ant-radio-button-wrapper').filter({
    has: page.locator('input[type="radio"][value="roles"]'),
  }).first()
  await rolesModeToggle.scrollIntoViewIfNeeded()
  await rolesModeToggle.click()
  await expect(page.getByText('Create Role', { exact: true })).toBeVisible()

  const createRoleCard = page.locator('.ant-card').filter({ has: page.locator('.ant-card-head-title', { hasText: 'Create Role' }) }).first()
  await createRoleCard.getByPlaceholder('Role name').fill('NewRole')
  await createRoleCard.getByPlaceholder('Reason').fill('create reason')
  await createRoleCard.getByRole('button', { name: 'Create', exact: true }).click()

  await expect.poll(() => createRole.length).toBe(1)
  expect(createRole[0]).toMatchObject({ name: 'NewRole', reason: 'create reason' })

  const rolesCard = page.locator('.ant-card').filter({ has: page.locator('.ant-card-head-title', { hasText: 'Roles' }) }).first()
  await rolesCard.getByRole('button', { name: 'Rename', exact: true }).first().click()
  await expect(page.getByText('Rename role', { exact: true })).toBeVisible()

  const renameModal = page.locator('.ant-modal').filter({ hasText: 'Rename role' }).first()
  await renameModal.getByPlaceholder('Role name').fill('OpsRenamed')
  await renameModal.getByPlaceholder('Reason (required)').fill('rename reason')
  await renameModal.getByRole('button', { name: 'Save', exact: true }).click()

  await expect.poll(() => updateRole.length).toBe(1)
  expect(updateRole[0]).toMatchObject({ group_id: 201, name: 'OpsRenamed', reason: 'rename reason' })
})

test('RBAC: effective access filters and expands sources', async ({ page }) => {
  const state = defaultState()

  await setupAuth(page)
  await setupApiMocks(page, state)

  await page.goto('/rbac', { waitUntil: 'domcontentloaded' })
  await page.getByRole('tab', { name: 'Effective access', exact: true }).click()

  const activeTabPane = page.locator('.ant-tabs-tabpane-active').first()
  const effectiveCard = activeTabPane.locator('.ant-card').filter({
    has: page.locator('.ant-card-head-title', { hasText: 'Effective access' }),
  }).first()
  await expect(effectiveCard).toBeVisible()
  await effectiveCard.locator('.ant-select').first().click()
  await selectAntdOption(page, 'alice #101')

  const resourceTypeSelect = effectiveCard.locator('.ant-select').nth(1)
  await resourceTypeSelect.click()
  await selectAntdOption(page, 'Clusters')

  const clusterPickerGroup = effectiveCard.locator('.ant-space-compact').filter({ hasText: 'Clear' }).first()
  const clusterPickerButton = clusterPickerGroup.locator('button').first()
  await clusterPickerButton.click()
  await expect(page.getByText('Select cluster', { exact: true })).toBeVisible()
  await page.locator('.ant-tree-treenode').filter({ hasText: 'Cluster Two' }).first().click()

  const clustersCard = activeTabPane.locator('.ant-card').filter({
    has: page.locator('.ant-card-head-title', { hasText: 'Clusters' }),
  }).first()
  await expect(clustersCard).toBeVisible()
  await clustersCard.locator('.ant-table-row-expand-icon').first().click()
  await expect(page.getByText('group', { exact: true })).toBeVisible()
})

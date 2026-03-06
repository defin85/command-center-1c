import { expect, test } from '@playwright/test'

type TenantsResponse = {
  active_tenant_id?: string | null
  tenants?: Array<{ id?: string | null }>
}

const LIVE_ENABLED = process.env.CC1C_POOLS_LIVE === '1'
const LIVE_USERNAME = process.env.CC1C_POOLS_LIVE_USERNAME ?? ''
const LIVE_PASSWORD = process.env.CC1C_POOLS_LIVE_PASSWORD ?? ''
const LIVE_POOL_LABEL = process.env.CC1C_POOLS_LIVE_POOL_LABEL
  ?? 'stroygrupp-full-publication-baseline - STROYGRUPP Full Publication Baseline'
const LIVE_PERIOD_START = process.env.CC1C_POOLS_LIVE_PERIOD_START ?? '2026-03-09'
const LIVE_STARTING_AMOUNT = process.env.CC1C_POOLS_LIVE_STARTING_AMOUNT ?? '12956834.00'

const resolveTenantId = (payload: TenantsResponse): string => {
  const activeTenantId = String(payload.active_tenant_id ?? '').trim()
  if (activeTenantId) {
    return activeTenantId
  }
  const fallbackTenantId = String(payload.tenants?.[0]?.id ?? '').trim()
  if (fallbackTenantId) {
    return fallbackTenantId
  }
  throw new Error('Active tenant is not configured for live pools smoke test.')
}

test.describe('Pools live publication smoke', () => {
  test.skip(!LIVE_ENABLED, 'Set CC1C_POOLS_LIVE=1 to enable live pools smoke test.')

  test('creates or reuses baseline run through UI and reaches passed OData verification', async ({ page, request }) => {
    test.setTimeout(180_000)
    test.skip(!LIVE_USERNAME || !LIVE_PASSWORD, 'Set CC1C_POOLS_LIVE_USERNAME and CC1C_POOLS_LIVE_PASSWORD.')

    const authResponse = await request.post('/api/token', {
      data: {
        username: LIVE_USERNAME,
        password: LIVE_PASSWORD,
      },
    })
    expect(authResponse.ok()).toBeTruthy()
    const authPayload = await authResponse.json() as { access: string }

    const tenantsResponse = await request.get('/api/v2/tenants/list-my-tenants/', {
      headers: {
        Authorization: `Bearer ${authPayload.access}`,
      },
    })
    expect(tenantsResponse.ok()).toBeTruthy()
    const tenantId = resolveTenantId(await tenantsResponse.json() as TenantsResponse)

    await page.addInitScript(({ accessToken, currentTenantId }) => {
      localStorage.setItem('auth_token', accessToken)
      localStorage.setItem('active_tenant_id', currentTenantId)
    }, {
      accessToken: authPayload.access,
      currentTenantId: tenantId,
    })

    await page.goto('/pools/runs')
    await expect(page.getByRole('heading', { name: 'Pool Runs' })).toBeVisible()

    await page.getByTestId('pool-runs-context-pool').click()
    await page.locator('.ant-select-dropdown:visible .ant-select-item-option-content', { hasText: LIVE_POOL_LABEL }).click()

    await page.getByLabel('Period start').fill(LIVE_PERIOD_START)
    await page.getByTestId('pool-runs-create-mode').click()
    await page.locator('.ant-select-dropdown:visible .ant-select-item-option-content', { hasText: 'unsafe' }).click()
    await page.getByRole('spinbutton', { name: /Starting amount/i }).fill(LIVE_STARTING_AMOUNT)
    await page.getByTestId('pool-runs-create-submit').click()

    await expect(
      page.getByText(/Run создан|Run переиспользован по idempotency key/),
    ).toBeVisible({ timeout: 30_000 })

    await page.getByRole('tab', { name: 'Inspect' }).click()
    await expect(page.getByTestId('pool-runs-verification-status')).toHaveText(/status:\s+passed/i, {
      timeout: 120_000,
    })
    await expect(page.getByText('Published documents verified')).toBeVisible()
    await expect(page.getByText(/mismatches:\s*0/i)).toBeVisible()
  })
})

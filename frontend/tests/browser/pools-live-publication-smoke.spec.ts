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
const LIVE_PERIOD_START = process.env.CC1C_POOLS_LIVE_PERIOD_START ?? new Date().toISOString().slice(0, 10)
const LIVE_STARTING_AMOUNT = process.env.CC1C_POOLS_LIVE_STARTING_AMOUNT ?? '12956834.00'
const LIVE_PERIOD_ATTEMPTS = Number.parseInt(process.env.CC1C_POOLS_LIVE_PERIOD_ATTEMPTS ?? '14', 10)

type CreateRunResponse = {
  run: {
    id: string
    mode?: string | null
    status?: string | null
    approval_state?: string | null
    publication_step_state?: string | null
  }
  created?: boolean
}

type PoolRunReportResponse = {
  run?: {
    id?: string | null
    mode?: string | null
    approval_state?: string | null
    verification_status?: string | null
    verification_summary?: {
      mismatches_count?: number | null
    } | null
  } | null
}

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

const addDays = (isoDate: string, days: number): string => {
  const [year, month, day] = isoDate.split('-').map((value) => Number.parseInt(value, 10))
  const next = new Date(Date.UTC(year, (month || 1) - 1, day || 1))
  next.setUTCDate(next.getUTCDate() + days)
  return next.toISOString().slice(0, 10)
}

test.describe('Pools live publication smoke', () => {
  test.skip(!LIVE_ENABLED, 'Set CC1C_POOLS_LIVE=1 to enable live pools smoke test.')

  test('creates safe baseline run through UI, confirms publication, and reaches passed OData verification', async ({ page, request }) => {
    test.setTimeout(240_000)
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

    const createSafeRun = async (periodStart: string): Promise<CreateRunResponse> => {
      await page.getByRole('tab', { name: 'Create' }).click()
      await page.getByLabel('Period start').fill(periodStart)
      await page.getByTestId('pool-runs-create-mode').click()
      await page
        .locator('.ant-select-dropdown:visible .ant-select-item-option-content')
        .filter({ hasText: /^safe$/ })
        .click()
      await page.getByRole('spinbutton', { name: /Starting amount/i }).fill(LIVE_STARTING_AMOUNT)

      const responsePromise = page.waitForResponse((response) => (
        response.url().includes('/api/v2/pools/runs/')
        && response.request().method() === 'POST'
      ))
      await page.getByTestId('pool-runs-create-submit').click()
      const response = await responsePromise
      expect(response.ok()).toBeTruthy()
      await expect(
        page.getByText(/Run создан|Run переиспользован по idempotency key/).last(),
      ).toBeVisible({ timeout: 30_000 })
      return await response.json() as CreateRunResponse
    }

    const fetchRunReport = async (runId: string): Promise<PoolRunReportResponse> => {
      const response = await request.get(`/api/v2/pools/runs/${runId}/report/`, {
        headers: {
          Authorization: `Bearer ${authPayload.access}`,
        },
      })
      expect(response.ok()).toBeTruthy()
      return await response.json() as PoolRunReportResponse
    }

    const selectRunInUi = async (runId: string): Promise<void> => {
      const shortRunId = runId.slice(0, 8)
      await page.getByRole('tab', { name: 'Inspect' }).click()

      for (let attempt = 0; attempt < 12; attempt += 1) {
        await page.getByRole('button', { name: 'Refresh Data' }).click()
        const row = page.getByRole('row', { name: new RegExp(shortRunId, 'i') }).first()
        try {
          await expect(row).toBeVisible({ timeout: 5_000 })
          await row.getByRole('radio').click()
          return
        } catch {
          await page.waitForTimeout(2_000)
        }
      }

      throw new Error(`Created run ${runId} did not appear in Inspect table.`)
    }

    let selectedRunId = ''
    let selectedPeriodStart = ''
    let safePathConfirmed = false
    for (let attemptIndex = 0; attemptIndex < Math.max(LIVE_PERIOD_ATTEMPTS, 1); attemptIndex += 1) {
      const candidatePeriodStart = addDays(LIVE_PERIOD_START, attemptIndex)
      const createPayload = await createSafeRun(candidatePeriodStart)
      const run = createPayload.run
      expect(run.mode).toBe('safe')

      selectedRunId = String(run.id || '').trim()
      expect(selectedRunId).not.toBe('')
      selectedPeriodStart = candidatePeriodStart

      if (run.status === 'published' || run.publication_step_state === 'completed') {
        continue
      }

      await selectRunInUi(selectedRunId)
      await page.getByRole('tab', { name: 'Safe Actions' }).click()
      const confirmButton = page.getByTestId('pool-runs-safe-confirm')
      await expect(confirmButton).toBeVisible()
      await expect(confirmButton).toBeEnabled({ timeout: 120_000 })
      await confirmButton.click()
      await expect(page.getByText('Confirm publication: accepted')).toBeVisible({ timeout: 30_000 })
      safePathConfirmed = true
      break
    }

    expect(safePathConfirmed, `Failed to allocate a non-terminal safe run starting from ${LIVE_PERIOD_START}.`).toBeTruthy()
    expect(selectedRunId).not.toBe('')

    await expect.poll(async () => {
      const report = await fetchRunReport(selectedRunId)
      return report.run?.verification_status ?? 'missing'
    }, {
      timeout: 180_000,
    }).toBe('passed')

    await selectRunInUi(selectedRunId)
    await page.getByRole('tab', { name: 'Inspect' }).click()
    await expect(page.getByTestId('pool-runs-verification-status')).toHaveText(/status:\s+passed/i, {
      timeout: 30_000,
    })
    await expect(page.getByText('Published documents verified')).toBeVisible()
    await expect(page.getByText(/mismatches:\s*0/i)).toBeVisible()

    const reportPayload = await fetchRunReport(selectedRunId)
    expect(reportPayload.run?.id).toBe(selectedRunId)
    expect(reportPayload.run?.mode).toBe('safe')
    expect(reportPayload.run?.approval_state).toBe('approved')
    expect(reportPayload.run?.verification_status).toBe('passed')
    expect(reportPayload.run?.verification_summary?.mismatches_count ?? 0).toBe(0)

    test.info().annotations.push({
      type: 'live-run',
      description: `period_start=${selectedPeriodStart} run_id=${selectedRunId}`,
    })
  })
})

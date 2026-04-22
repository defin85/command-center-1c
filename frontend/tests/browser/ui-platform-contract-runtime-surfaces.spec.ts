import { expect, test } from "@playwright/test";
import {
  ROUTE_MOUNT_TIMEOUT_MS,
  CLUSTER_RECORD,
  WORKFLOW_OPERATION,
  setupAuth,
  setupPersistentDatabaseStream,
  setupUiPlatformMocks,
  switchShellLocaleToEnglish,
  expectNoHorizontalOverflow,
  expectNoScopedHorizontalOverflow,
  createRequestCounts,
} from "./ui-platform-contract.helpers";

test("UI platform: /clusters restores selected cluster context and opens edit flow in a canonical modal shell", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page, { localeOverride: "ru" });
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto(
    "/clusters?cluster=cluster-1&context=edit&q=Main&status=active",
    {
      waitUntil: "domcontentloaded",
    },
  );

  await expect(
    page.getByRole("heading", { name: "Кластеры", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  const editModal = page.getByRole("dialog");
  await expect(editModal).toBeVisible();
  await expect(editModal.getByLabel("Имя кластера")).toHaveValue(
    CLUSTER_RECORD.name,
  );
  await expect(editModal.getByLabel("RAS Host")).toHaveValue(
    CLUSTER_RECORD.ras_host,
  );
  await expect(
    editModal.getByRole("button", { name: "Обновить" }),
  ).toBeVisible();
  await expect.poll(() => counts.clusterLists).toBe(1);
  await expect.poll(() => counts.clusterDetails).toBe(1);
  await expectNoHorizontalOverflow(page);
});

test("Runtime contract: /clusters hands off to /databases without replaying shell reads", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page, { localeOverride: "ru" });
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto("/clusters?cluster=cluster-1&context=inspect", {
    waitUntil: "domcontentloaded",
  });

  await expect(
    page.getByRole("heading", { name: "Кластеры", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(
    page.getByRole("button", { name: "Открыть базы" }),
  ).toBeVisible();
  await expect.poll(() => counts.clusterLists).toBe(1);
  await expect.poll(() => counts.clusterDetails).toBe(1);

  await page.getByRole("button", { name: "Открыть базы" }).click();

  await expect(page).toHaveURL(/\/databases\?cluster=cluster-1(?:&.*)?$/);
  await expect(
    page.getByRole("heading", { name: "Базы", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(counts.bootstrap).toBe(1);
  await expect(counts.meReads).toBe(0);
  await expect(counts.myTenantsReads).toBe(0);
});

test("Runtime contract: /clusters ignores same-route menu re-entry and keeps selected cluster context stable", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page, { localeOverride: "ru" });
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto("/clusters?cluster=cluster-1&context=inspect", {
    waitUntil: "domcontentloaded",
  });

  const clustersMenuItem = page.getByRole("menuitem", { name: /Кластеры/i });

  await expect(page.getByRole("button", { name: "Открыть базы" })).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(
    page.getByText("Primary RAS cluster for shared services"),
  ).toBeVisible();
  await expect.poll(() => counts.clusterLists).toBe(1);
  await expect.poll(() => counts.clusterDetails).toBe(1);

  const initialUrl = page.url();
  const initialClusterListReads = counts.clusterLists;
  const initialClusterDetailReads = counts.clusterDetails;

  await clustersMenuItem.click();
  await page.waitForTimeout(750);

  await expect(page).toHaveURL(initialUrl);
  await expect(
    page.getByRole("button", { name: "Открыть базы" }),
  ).toBeVisible();
  await expect(
    page.getByText("Primary RAS cluster for shared services"),
  ).toBeVisible();
  await expect(counts.bootstrap).toBe(1);
  await expect(counts.clusterLists).toBe(initialClusterListReads);
  await expect(counts.clusterDetails).toBe(initialClusterDetailReads);
  await expect(page.getByText("Request Error")).toHaveCount(0);
});

test("UI platform: /clusters opens inspect detail in a mobile-safe drawer without page-wide overflow", async ({
  page,
}) => {
  await setupAuth(page, { localeOverride: "ru" });
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true });
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto("/clusters?cluster=cluster-1&context=inspect", {
    waitUntil: "domcontentloaded",
  });

  await expect(
    page.getByRole("heading", { name: "Кластеры", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  const detailDrawer = page.getByRole("dialog");
  await expect(detailDrawer).toBeVisible();
  await expect(page.locator(".ant-drawer-content-wrapper:visible")).toHaveCount(
    1,
  );
  await expect(
    detailDrawer.getByRole("button", { name: "Открыть базы" }),
  ).toBeVisible();
  await expect(
    detailDrawer.getByText("Primary RAS cluster for shared services"),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await expectNoScopedHorizontalOverflow(
    detailDrawer,
    "Clusters detail drawer",
  );
});

test("Runtime contract: /clusters normalizes unauthorized mutating deep-links to inspect state", async ({
  page,
}) => {
  await setupAuth(page, { localeOverride: "ru" });
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, {
    isStaff: false,
    clusterAccessLevel: "VIEW",
  });

  await page.goto("/clusters?cluster=cluster-1&context=edit", {
    waitUntil: "domcontentloaded",
  });

  await expect(
    page.getByRole("heading", { name: "Кластеры", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(page.getByRole("button", { name: "Обновить" })).toHaveCount(0);
  await expect(
    page.getByText("Primary RAS cluster for shared services"),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Редактировать" }),
  ).toBeDisabled();
  await expect
    .poll(() => {
      const currentUrl = new URL(page.url());
      return {
        path: currentUrl.pathname,
        cluster: currentUrl.searchParams.get("cluster"),
        context: currentUrl.searchParams.get("context"),
      };
    })
    .toEqual({
      path: "/clusters",
      cluster: "cluster-1",
      context: "inspect",
    });
});

test("UI platform: /clusters keeps detail loading fail-closed until the detail snapshot arrives", async ({
  page,
}) => {
  await setupAuth(page, { localeOverride: "ru" });
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, {
    isStaff: true,
    clusterDetailDelayMs: 1500,
  });

  await page.goto("/clusters?cluster=cluster-1&context=inspect", {
    waitUntil: "domcontentloaded",
  });

  await expect(
    page.getByRole("heading", { name: "Кластеры", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await page.waitForTimeout(200);
  await expect(
    page.getByText("Для этого snapshot кластера базы не вернулись."),
  ).toHaveCount(0);
  await expect(page.getByText("Метаданные кластера")).toHaveCount(0);
  await expect(page.getByText("Превью баз")).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(page.getByText("db-services")).toBeVisible();
});

test("UI platform: /system-status keeps locale switch and reload aligned with the shell i18n context", async ({
  page,
}) => {
  const observedLocaleHeaders: string[] = [];
  const localeSelect = page.getByTestId("shell-locale-select");
  const localeSelectTrigger = localeSelect.locator(".ant-select-selector");
  const refreshButtonRu = page
    .locator("button")
    .filter({ hasText: /^Обновить$/ });
  const refreshButtonEn = page
    .locator("button")
    .filter({ hasText: /^Refresh$/ });
  const systemStatusMenuItemRu = page.getByRole("menuitem", {
    name: "Статус системы",
  });
  const databasesMenuItemRu = page.getByRole("menuitem", { name: "Базы" });
  const poolCatalogMenuItemRu = page.getByRole("menuitem", {
    name: "Каталог пулов",
  });
  const systemStatusMenuItemEn = page.getByRole("menuitem", {
    name: "System Status",
  });
  const databasesMenuItemEn = page.getByRole("menuitem", {
    name: "Databases",
  });
  const poolCatalogMenuItemEn = page.getByRole("menuitem", {
    name: "Pool Catalog",
  });

  await setupAuth(page, { localeOverride: "ru" });
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { observedLocaleHeaders });

  await page.goto("/system-status", { waitUntil: "domcontentloaded" });

  await expect(localeSelect).toBeVisible({ timeout: ROUTE_MOUNT_TIMEOUT_MS });
  await expect(localeSelect).toHaveAttribute("aria-label", "Язык");
  await expect(refreshButtonRu).toBeVisible();
  await expect(systemStatusMenuItemRu).toBeVisible();
  await expect(databasesMenuItemRu).toBeVisible();
  await expect(poolCatalogMenuItemRu).toBeVisible();
  await expect.poll(() => observedLocaleHeaders[0]).toBe("ru");

  await localeSelectTrigger.click();
  await page
    .locator(
      '.ant-select-dropdown:not(.ant-select-dropdown-hidden) [title="English"]',
    )
    .click();

  await expect(localeSelect).toHaveAttribute("aria-label", "Language");
  await expect(refreshButtonEn).toBeVisible();
  await expect(systemStatusMenuItemEn).toBeVisible();
  await expect(databasesMenuItemEn).toBeVisible();
  await expect(poolCatalogMenuItemEn).toBeVisible();
  await expect.poll(() => observedLocaleHeaders.at(-1)).toBe("en");

  await page.reload({ waitUntil: "domcontentloaded" });

  await expect(localeSelect).toBeVisible({ timeout: ROUTE_MOUNT_TIMEOUT_MS });
  await expect(localeSelect).toHaveAttribute("aria-label", "Language");
  await expect(refreshButtonEn).toBeVisible();
  await expect(systemStatusMenuItemEn).toBeVisible();
  await expect(databasesMenuItemEn).toBeVisible();
  await expect(poolCatalogMenuItemEn).toBeVisible();
  await expect.poll(() => observedLocaleHeaders.at(-1)).toBe("en");
});

for (const localeWaveCase of [
  {
    label: "2.1 /extensions",
    path: "/extensions",
    ruVisible: (page: Page) =>
      page.getByPlaceholder("Поиск по имени расширения"),
    enVisible: (page: Page) => page.getByPlaceholder("Search extension name"),
  },
  {
    label: "2.2 /artifacts",
    path: "/artifacts",
    ruVisible: (page: Page) =>
      page.getByRole("heading", { name: "Артефакты", level: 2 }),
    enVisible: (page: Page) =>
      page.getByRole("heading", { name: "Artifacts", level: 2 }),
  },
  {
    label: "2.3 /operations",
    path: "/operations",
    ruVisible: (page: Page) =>
      page.getByRole("heading", { name: "Монитор операций", level: 2 }),
    enVisible: (page: Page) =>
      page.getByRole("heading", { name: "Operations Monitor", level: 2 }),
  },
  {
    label: "2.4 /workflows",
    path: "/workflows",
    ruVisible: (page: Page) =>
      page.getByRole("heading", {
        name: "Библиотека workflow-схем",
        level: 2,
      }),
    enVisible: (page: Page) =>
      page.getByRole("heading", {
        name: "Workflow Scheme Library",
        level: 2,
      }),
  },
  {
    label: "2.5 /pools/templates",
    path: "/pools/templates",
    ruVisible: (page: Page) =>
      page.getByRole("button", { name: "Создать шаблон" }),
    enVisible: (page: Page) =>
      page.getByRole("button", { name: "Create Template" }),
  },
  {
    label: "2.6 /pools/runs",
    path: "/pools/runs",
    ruVisible: (page: Page) =>
      page.getByRole("button", { name: "Обновить данные" }),
    enVisible: (page: Page) =>
      page.getByRole("button", { name: "Refresh Data" }),
  },
] as const) {
  test(`UI platform: ${localeWaveCase.label} keeps locale switch and reload aligned with shell i18n`, async ({
    page,
  }) => {
    const observedLocaleHeaders: string[] = [];
    const localeSelect = page.getByTestId("shell-locale-select");

    await setupAuth(page, { localeOverride: "ru" });
    await setupPersistentDatabaseStream(page);
    await setupUiPlatformMocks(page, {
      isStaff: true,
      observedLocaleHeaders,
    });

    await page.goto(localeWaveCase.path, { waitUntil: "domcontentloaded" });

    await expect(localeSelect).toBeVisible({
      timeout: ROUTE_MOUNT_TIMEOUT_MS,
    });
    await expect(localeSelect).toHaveAttribute("aria-label", "Язык");
    await expect(localeWaveCase.ruVisible(page)).toBeVisible({
      timeout: ROUTE_MOUNT_TIMEOUT_MS,
    });
    await expect.poll(() => observedLocaleHeaders[0]).toBe("ru");

    await switchShellLocaleToEnglish(page);

    await expect(localeSelect).toHaveAttribute("aria-label", "Language");
    await expect.poll(() => observedLocaleHeaders.at(-1)).toBe("en");
    await expect(localeWaveCase.enVisible(page)).toBeVisible({
      timeout: ROUTE_MOUNT_TIMEOUT_MS,
    });

    await page.reload({ waitUntil: "domcontentloaded" });

    await expect(localeSelect).toBeVisible({
      timeout: ROUTE_MOUNT_TIMEOUT_MS,
    });
    await expect(localeSelect).toHaveAttribute("aria-label", "Language");
    await expect(localeWaveCase.enVisible(page)).toBeVisible({
      timeout: ROUTE_MOUNT_TIMEOUT_MS,
    });
    await expect(localeWaveCase.ruVisible(page)).toHaveCount(0);
    await expect.poll(() => observedLocaleHeaders.at(-1)).toBe("en");
  });
}

test("UI platform: /system-status restores diagnostics context in a mobile-safe drawer with paused polling", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto("/system-status?service=orchestrator&poll=paused", {
    waitUntil: "domcontentloaded",
  });

  await expect(
    page.getByRole("heading", { name: "System status", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  const detailDrawer = page.getByRole("dialog");
  await expect(detailDrawer).toBeVisible();
  await expect(page.locator(".ant-drawer-content-wrapper:visible")).toHaveCount(
    1,
  );
  await expect(
    page.getByRole("button", { name: "Resume auto-refresh" }),
  ).toBeVisible();
  await expect(detailDrawer).toContainText("orchestrator");
  await expect(detailDrawer.getByText("Delayed queue drain")).toBeVisible();
  await expect.poll(() => counts.systemHealthReads).toBeGreaterThan(0);
  await expectNoHorizontalOverflow(page);
  await expectNoScopedHorizontalOverflow(
    detailDrawer,
    "System status detail drawer",
  );
});

test("Runtime contract: /system-status hands off to /service-mesh without replaying shell reads", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto("/system-status?service=orchestrator&poll=paused", {
    waitUntil: "domcontentloaded",
  });

  await expect(
    page.getByRole("heading", { name: "System status", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(page.getByText("Delayed queue drain")).toBeVisible();
  await expect.poll(() => counts.systemHealthReads).toBeGreaterThan(0);

  await page.getByRole("button", { name: "Open service mesh" }).click();

  await expect(page).toHaveURL(/\/service-mesh\?service=orchestrator$/);
  await expect(
    page.getByRole("heading", { name: "Service mesh", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(page.getByTestId("service-mesh-service-drawer")).toBeVisible();
  await expect.poll(() => counts.serviceHistoryReads).toBeGreaterThan(0);
  await expect(counts.bootstrap).toBe(1);
  await expect(counts.meReads).toBe(0);
  await expect(counts.myTenantsReads).toBe(0);
});

test("Runtime contract: /system-status ignores same-route menu re-entry and keeps diagnostics context stable", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto("/system-status?service=orchestrator&poll=paused", {
    waitUntil: "domcontentloaded",
  });

  const systemStatusMenuItem = page.getByRole("menuitem", {
    name: /System status/i,
  });

  await expect(page.getByText("Delayed queue drain")).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect.poll(() => counts.systemHealthReads).toBeGreaterThan(0);

  const initialUrl = page.url();
  const initialSystemHealthReads = counts.systemHealthReads;

  await systemStatusMenuItem.click();
  await page.waitForTimeout(750);

  await expect(page).toHaveURL(initialUrl);
  await expect(page.getByText("Delayed queue drain")).toBeVisible();
  await expect(counts.bootstrap).toBe(1);
  await expect(counts.systemHealthReads).toBe(initialSystemHealthReads);
  await expect(page.getByText("Request Error")).toHaveCount(0);
});

test("Runtime control: /system-status exposes scheduler controls for worker-workflows and hands off cadence editing to runtime settings", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, {
    isStaff: true,
    canManageRuntimeControls: true,
    counts,
  });

  await page.goto(
    "/system-status?service=worker-workflows&tab=scheduler&poll=paused",
    {
      waitUntil: "domcontentloaded",
    },
  );

  await expect(
    page.getByRole("heading", { name: "System status", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(page.getByText("Global scheduler enablement")).toBeVisible();
  await expect(page.getByText("Pool factual active sync")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Trigger now" }).first(),
  ).toBeVisible();
  await expect.poll(() => counts.runtimeControlCatalogReads).toBeGreaterThan(0);
  await expect.poll(() => counts.runtimeControlRuntimeReads).toBeGreaterThan(0);

  await page.getByRole("button", { name: "Open cadence" }).first().click();

  await expect(page).toHaveURL(
    /\/settings\/runtime\?setting=runtime\.scheduler\.job\.pool_factual_active_sync\.schedule$/,
  );
  await expect(
    page.getByRole("heading", { name: "Runtime Settings", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect.poll(() => counts.runtimeSettingsReads).toBeGreaterThan(0);
});

test("Runtime control: /system-status restores selected scheduler job context from a deep-link", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, {
    isStaff: true,
    canManageRuntimeControls: true,
    counts,
  });

  await page.goto(
    "/system-status?service=worker-workflows&tab=scheduler&job=pool_factual_closed_quarter_reconcile&poll=paused",
    {
      waitUntil: "domcontentloaded",
    },
  );

  const selectedJob = page.getByTestId("system-status-selected-scheduler-job");
  await expect(selectedJob).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(selectedJob).toContainText(
    "Pool factual closed-quarter reconcile",
  );
  await expect(selectedJob).toContainText("0 2 * * *");
  await expect.poll(() => counts.runtimeControlCatalogReads).toBeGreaterThan(0);
  await expect.poll(() => counts.runtimeControlRuntimeReads).toBeGreaterThan(0);

  await selectedJob.getByRole("button", { name: "Open cadence" }).click();

  await expect(page).toHaveURL(
    /\/settings\/runtime\?setting=runtime\.scheduler\.job\.pool_factual_closed_quarter_reconcile\.schedule$/,
  );
});

test("Runtime control: /system-status restart action uses a reason-gated modal flow inside diagnostics workspace", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, {
    isStaff: true,
    canManageRuntimeControls: true,
    counts,
  });

  await page.goto(
    "/system-status?service=orchestrator&tab=controls&poll=paused",
    {
      waitUntil: "domcontentloaded",
    },
  );

  await expect(
    page.getByRole("heading", { name: "System status", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(
    page.getByRole("button", { name: "Restart runtime" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Restart runtime" }).click();

  const restartDialog = page.getByRole("dialog");
  await expect(restartDialog).toContainText(
    "Restart is a dangerous action and requires an explicit operator reason.",
  );
  await expect(
    restartDialog.getByRole("button", { name: "Restart" }),
  ).toBeDisabled();

  await restartDialog
    .getByPlaceholder("Explain why this runtime needs a restart")
    .fill("Rotate runtime after factual scheduler drift");
  await expect(
    restartDialog.getByRole("button", { name: "Restart" }),
  ).toBeEnabled();
  await restartDialog.getByRole("button", { name: "Restart" }).click();

  await expect(restartDialog).toHaveCount(0);
  await expect.poll(() => counts.runtimeControlActionWrites).toBeGreaterThan(0);
});

test("Runtime control: /system-status hands off to /service-mesh with canonical runtime keys even when diagnostics labels are title-cased", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, {
    isStaff: true,
    canManageRuntimeControls: true,
    counts,
  });

  await page.goto(
    "/system-status?service=orchestrator&tab=controls&poll=paused",
    {
      waitUntil: "domcontentloaded",
    },
  );

  await expect(
    page.getByRole("heading", { name: "System status", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(
    page.getByRole("button", { name: "Restart runtime" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Open service mesh" }).click();

  await expect(page).toHaveURL(/\/service-mesh\?service=orchestrator$/);
  await expect(
    page.getByRole("heading", { name: "Service mesh", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(page.getByTestId("service-mesh-service-drawer")).toBeVisible();
  await expect.poll(() => counts.serviceHistoryReads).toBeGreaterThan(0);
});

test("Runtime control: /system-status surfaces scheduler run correlation in runtime action history", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, {
    isStaff: true,
    canManageRuntimeControls: true,
    counts,
  });

  await page.goto(
    "/system-status?service=worker-workflows&tab=scheduler&job=pool_factual_active_sync&poll=paused",
    {
      waitUntil: "domcontentloaded",
    },
  );

  const selectedJob = page.getByTestId("system-status-selected-scheduler-job");
  await expect(selectedJob).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await selectedJob.getByRole("button", { name: "Trigger now" }).click();
  await expect.poll(() => counts.runtimeControlActionWrites).toBeGreaterThan(0);

  await page.getByText("Controls", { exact: true }).click();
  await expect(page.getByText("Scheduler run: #6001")).toBeVisible();
  await expect(page.getByText("pool_factual_active_sync")).toBeVisible();
});

test("Runtime control: /system-status keeps diagnostics-only workspace without runtime-control capability", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, {
    isStaff: true,
    canManageRuntimeControls: false,
    counts,
  });

  await page.goto(
    "/system-status?service=orchestrator&tab=controls&poll=paused",
    {
      waitUntil: "domcontentloaded",
    },
  );

  await expect(
    page.getByRole("heading", { name: "System status", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(page.getByText("Delayed queue drain")).toBeVisible();
  await expect(page.getByRole("button", { name: "Controls" })).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Restart runtime" }),
  ).toHaveCount(0);
  await expect(page.getByText("Runtime control summary")).toHaveCount(0);
  await expect.poll(() => counts.systemHealthReads).toBeGreaterThan(0);
});

test("UI platform: /service-mesh restores selected service context in a mobile-safe drawer", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto("/service-mesh?service=orchestrator", {
    waitUntil: "domcontentloaded",
  });

  await expect(
    page.getByRole("heading", { name: "Service mesh", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  const serviceDrawer = page.getByTestId("service-mesh-service-drawer");
  await expect(serviceDrawer).toBeVisible();
  await expect(page.locator(".ant-drawer-content-wrapper:visible")).toHaveCount(
    1,
  );
  await expect(serviceDrawer.getByText("Historical Metrics")).toBeVisible();
  await expect(
    serviceDrawer
      .locator(".ant-statistic-title")
      .filter({ hasText: "Ops/min" })
      .first(),
  ).toBeVisible();
  await expect.poll(() => counts.serviceHistoryReads).toBeGreaterThan(0);
  await expectNoHorizontalOverflow(page);
  await expectNoScopedHorizontalOverflow(
    serviceDrawer,
    "Service mesh service drawer",
  );
});

test("UI platform: /service-mesh restores realtime context in a mobile-safe timeline drawer", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto(
    `/service-mesh?service=orchestrator&operation=${WORKFLOW_OPERATION.id}`,
    {
      waitUntil: "domcontentloaded",
    },
  );

  await expect(
    page.getByRole("heading", { name: "Service mesh", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(
    page.getByText("Operation timeline context restored from the route state."),
  ).toBeVisible();
  const timelineDrawer = page.getByTestId(
    "service-mesh-operation-timeline-drawer",
  );
  await expect(timelineDrawer).toBeVisible();
  await expect(page.locator(".ant-drawer-content-wrapper:visible")).toHaveCount(
    1,
  );
  await expect(timelineDrawer.getByText("Operation Timeline")).toBeVisible();
  await expect(timelineDrawer.getByText(WORKFLOW_OPERATION.id)).toBeVisible();
  await expect.poll(() => counts.operationsList).toBeGreaterThan(0);
  await expectNoHorizontalOverflow(page);
  await expectNoScopedHorizontalOverflow(
    timelineDrawer,
    "Service mesh timeline drawer",
  );
});

test("Runtime contract: /service-mesh ignores same-route menu re-entry and keeps selected service context stable", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto("/service-mesh?service=orchestrator", {
    waitUntil: "domcontentloaded",
  });

  const serviceMeshMenuItem = page.getByRole("menuitem", {
    name: /Service mesh/i,
  });
  const serviceDrawer = page.getByTestId("service-mesh-service-drawer");

  await expect(serviceDrawer).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(serviceDrawer.getByText("Historical Metrics")).toBeVisible();
  await expect.poll(() => counts.serviceHistoryReads).toBeGreaterThan(0);

  const initialUrl = page.url();
  const initialServiceHistoryReads = counts.serviceHistoryReads;

  await serviceMeshMenuItem.dispatchEvent("click");
  await page.waitForTimeout(750);

  await expect(page).toHaveURL(initialUrl);
  await expect(serviceDrawer).toBeVisible();
  await expect(serviceDrawer.getByText("Historical Metrics")).toBeVisible();
  await expect(counts.bootstrap).toBe(1);
  await expect(counts.serviceHistoryReads).toBe(initialServiceHistoryReads);
  await expect(page.getByText("Request Error")).toHaveCount(0);
});

test("Runtime contract: /service-mesh hands off to /pools/master-data without leaving stale diagnostics content mounted", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto("/service-mesh", {
    waitUntil: "domcontentloaded",
  });

  const serviceMeshHeading = page.getByRole("heading", {
    name: "Service mesh",
    level: 2,
  });
  const poolMasterDataMenuItem = page.getByRole("menuitem", {
    name: /Pool Master Data/i,
  });

  await expect(serviceMeshHeading).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(page.getByText("Recent operations")).toBeVisible();
  await expect.poll(() => counts.operationsList).toBeGreaterThan(0);

  await poolMasterDataMenuItem.click();

  await expect(page).toHaveURL(/\/pools\/master-data(?:\?.*)?$/);
  await expect(
    page.getByRole("heading", { name: "Pool Master Data", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(serviceMeshHeading).toHaveCount(0);
  await expect(page.getByTestId("service-mesh-service-drawer")).toHaveCount(0);
  await expect(counts.bootstrap).toBe(1);
  await expect(counts.meReads).toBe(0);
  await expect(counts.myTenantsReads).toBe(0);
});

test("Runtime contract: /service-mesh ignores same-route menu re-entry and keeps realtime context stable", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto(
    `/service-mesh?service=orchestrator&operation=${WORKFLOW_OPERATION.id}`,
    {
      waitUntil: "domcontentloaded",
    },
  );

  const serviceMeshMenuItem = page.getByRole("menuitem", {
    name: /Service mesh/i,
  });
  const timelineDrawer = page.getByTestId(
    "service-mesh-operation-timeline-drawer",
  );

  await expect(timelineDrawer).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(
    page.getByText("Operation timeline context restored from the route state."),
  ).toBeVisible();
  await expect.poll(() => counts.operationsList).toBeGreaterThan(0);

  const initialUrl = page.url();
  const initialOperationsListReads = counts.operationsList;

  await serviceMeshMenuItem.dispatchEvent("click");
  await page.waitForTimeout(750);

  await expect(page).toHaveURL(initialUrl);
  await expect(timelineDrawer).toBeVisible();
  await expect(
    page.getByText("Operation timeline context restored from the route state."),
  ).toBeVisible();
  await expect(counts.bootstrap).toBe(1);
  await expect(counts.operationsList).toBe(initialOperationsListReads);
  await expect(page.getByText("Request Error")).toHaveCount(0);
});

test("Runtime contract: /service-mesh exports websocket owner diagnostics through the UI journal bundle", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page);

  await page.goto("/service-mesh?service=orchestrator", {
    waitUntil: "domcontentloaded",
  });

  await expect(
    page.getByRole("heading", { name: "Service mesh", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });

  await expect
    .poll(
      async () =>
        page.evaluate(() => {
          const bundle = (
            window as Window & {
              __CC1C_UI_JOURNAL__?: {
                exportBundle: () => {
                  events: Array<Record<string, unknown>>;
                  active_websockets_by_owner: Record<
                    string,
                    Record<string, unknown>
                  >;
                };
              };
            }
          ).__CC1C_UI_JOURNAL__?.exportBundle();

          if (!bundle) {
            return null;
          }

          return {
            lifecycleEvents: bundle.events.filter(
              (event) =>
                event.event_type === "websocket.lifecycle" &&
                event.owner === "serviceMeshManager",
            ),
            ownerSummary:
              bundle.active_websockets_by_owner.serviceMeshManager ?? null,
          };
        }),
      {
        timeout: ROUTE_MOUNT_TIMEOUT_MS,
      },
    )
    .toEqual(
      expect.objectContaining({
        lifecycleEvents: expect.arrayContaining([
          expect.objectContaining({
            owner: "serviceMeshManager",
            reuse_key: "service-mesh:global",
            channel_kind: "shared",
            outcome: "connect",
          }),
        ]),
        ownerSummary: expect.objectContaining({
          active_connection_count: 1,
        }),
      }),
    );
});

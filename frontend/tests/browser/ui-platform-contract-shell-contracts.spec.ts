import { expect, test } from "@playwright/test";
import {
  DATABASE_ID,
  ROUTE_MOUNT_TIMEOUT_MS,
  DATABASE_RECORD,
  DECISION,
  FALLBACK_DECISION,
  BINDING_PROFILE_DETAIL,
  LEGACY_BINDING_PROFILE_DETAIL,
  POOL_WITH_ATTACHMENT,
  POOL_RUN,
  WORKFLOW_OPERATION,
  setupAuth,
  setupPersistentDatabaseStream,
  setupUiPlatformMocks,
  fillTopologyTemplateCreateForm,
  fillTopologyTemplateReviseForm,
  selectVisibleAntdOption,
  expectContrastAtLeast,
  createRequestCounts,
} from "./ui-platform-contract.helpers";

test("Runtime contract: /decisions avoids mount-time waterfall and duplicate notifications on the default path", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto("/decisions", { waitUntil: "domcontentloaded" });

  await expect(page.getByText("Decision Policy Library")).toBeVisible();
  await expect(
    page.getByText("Services publication policy").first(),
  ).toBeVisible();

  await expect.poll(() => counts.bootstrap).toBe(1);
  await expect.poll(() => counts.streamTickets).toBe(1);
  await expect.poll(() => counts.databaseLists).toBe(1);
  await expect.poll(() => counts.metadataManagementReads).toBe(1);
  await expect.poll(() => counts.decisionsScoped).toBe(1);
  await expect.poll(() => counts.decisionsUnscoped).toBe(0);
  await expect.poll(() => counts.organizationPools).toBe(0);
  await expect(page.getByText("Request Error")).toHaveCount(0);
});

test("Runtime contract: /pools/execution-packs keeps usage scoped without broad pool scans", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto("/pools/execution-packs", {
    waitUntil: "domcontentloaded",
  });

  await expect(page.getByText("Execution Packs")).toBeVisible();
  await expect.poll(() => counts.bindingProfileDetails).toBe(1);
  await expect.poll(() => counts.organizationPools).toBe(0);

  await page.getByRole("button", { name: "Load attachment usage" }).click();

  await expect.poll(() => counts.organizationPools).toBe(0);
  await expect(counts.bindingProfileDetails).toBe(1);
  await expect(page.getByText("Main Pool")).toBeVisible();
  await expect(page.getByText("Request Error")).toHaveCount(0);
});

test("Runtime contract: /pools/catalog keeps the default mount within a single initial read budget", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto("/pools/catalog", { waitUntil: "domcontentloaded" });

  await expect(
    page.getByRole("heading", { name: "Pool Catalog", level: 2 }),
  ).toBeVisible();
  await expect(page.getByRole("tab", { name: "Pools" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page).toHaveURL(
    /\/pools\/catalog\?pool_id=.*&tab=pools&date=2026-01-01$/,
  );

  await expect.poll(() => counts.poolOrganizations).toBe(1);
  await expect.poll(() => counts.poolOrganizationDetails).toBe(1);
  await expect.poll(() => counts.organizationPools).toBe(1);
  await expect.poll(() => counts.poolTopologySnapshots).toBe(1);
  await expect.poll(() => counts.poolGraphs).toBe(1);
  await expect(page.getByText("Request Error")).toHaveCount(0);
});

test("Runtime contract: /pools/execution-packs hands off to /pools/catalog without replaying shell reads", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto("/pools/execution-packs", {
    waitUntil: "domcontentloaded",
  });

  await expect(page.getByText("Execution Packs")).toBeVisible();
  await expect.poll(() => counts.bootstrap).toBe(1);
  await expect(counts.meReads).toBe(0);
  await expect(counts.myTenantsReads).toBe(0);

  await page.getByRole("button", { name: "Load attachment usage" }).click();
  await page.getByRole("button", { name: "Open pool attachment" }).click();

  await expect(page).toHaveURL(
    /\/pools\/catalog\?pool_id=pool-1&tab=bindings(?:&date=2026-01-01)?$/,
  );
  await expect(
    page.getByRole("heading", { name: "Pool Catalog", level: 2 }),
  ).toBeVisible();
  await expect(page.getByTestId("pool-catalog-context-pool")).toHaveText(
    "pool-main - Main Pool",
  );
  await expect(page.getByTestId("pool-catalog-bindings-drawer")).toBeVisible();

  await expect(counts.bootstrap).toBe(1);
  await expect(counts.meReads).toBe(0);
  await expect(counts.myTenantsReads).toBe(0);
  await expect.poll(() => counts.organizationPools).toBe(1);
  await expect(page.getByText("Request Error")).toHaveCount(0);
});

test("Runtime contract: /pools/catalog creates a reusable topology template through handoff and restores the same topology task without replaying shell reads", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto(
    "/pools/catalog?pool_id=pool-1&tab=topology&date=2026-01-01",
    { waitUntil: "domcontentloaded" },
  );

  await expect(
    page.getByRole("heading", { name: "Pool Catalog", level: 2 }),
  ).toBeVisible();
  await expect.poll(() => counts.bootstrap).toBe(1);
  await expect(counts.meReads).toBe(0);
  await expect(counts.myTenantsReads).toBe(0);
  await expect(
    page.getByTestId("pool-catalog-open-topology-template-workspace"),
  ).toBeVisible();

  await page
    .getByTestId("pool-catalog-open-topology-template-workspace")
    .click();

  await expect(page).toHaveURL(/\/pools\/topology-templates\?/);
  await expect
    .poll(() => {
      const url = new URL(page.url());
      return {
        return_pool_id: url.searchParams.get("return_pool_id"),
        return_tab: url.searchParams.get("return_tab"),
        return_date: url.searchParams.get("return_date"),
        template: url.searchParams.get("template"),
        compose: url.searchParams.get("compose"),
      };
    })
    .toEqual({
      return_pool_id: "pool-1",
      return_tab: "topology",
      return_date: "2026-01-01",
      template: "template-top-down",
      compose: null,
    });
  await expect(
    page.getByRole("heading", { name: "Topology Templates", level: 2 }),
  ).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", { name: "Create template" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();

  const createRequestPromise = page.waitForRequest(
    (request) =>
      request.method() === "POST" &&
      request.url().endsWith("/api/v2/pools/topology-templates/"),
  );
  await fillTopologyTemplateCreateForm(page);
  await page.getByTestId("pool-topology-templates-create-submit").click();
  const createRequest = await createRequestPromise;
  const createPayload = createRequest.postDataJSON() as Record<string, unknown>;

  expect(createPayload.code).toBe("new-template");
  await expect(
    page.getByTestId("pool-topology-templates-selected-code"),
  ).toHaveText("new-template");

  await page.getByRole("button", { name: "Return to pool topology" }).click();

  await expect(page).toHaveURL(
    /\/pools\/catalog\?pool_id=pool-1&tab=topology&date=2026-01-01$/,
  );
  await expect(
    page.getByRole("heading", { name: "Pool Catalog", level: 2 }),
  ).toBeVisible();
  await expect(page.getByTestId("pool-catalog-context-pool")).toHaveText(
    "pool-main - Main Pool",
  );
  await expect(
    page.getByRole("tab", { name: "Topology Editor" }),
  ).toHaveAttribute("aria-selected", "true");
  await page.getByTestId("pool-catalog-topology-authoring-mode").click();
  await selectVisibleAntdOption(page, "Template-based instantiation");
  await expect(
    page.getByTestId("pool-catalog-topology-authoring-mode"),
  ).toContainText("Template-based instantiation");
  await expect(
    page.getByText("Template-based path is the preferred reuse flow"),
  ).toBeVisible();
  await expect(
    page.getByTestId("pool-catalog-topology-template-revision"),
  ).toBeVisible();
  await page.getByTestId("pool-catalog-topology-template-revision").click();
  await expect(
    page
      .locator(".ant-select-dropdown:visible .ant-select-item-option-content", {
        hasText: "New Template · r1",
      })
      .first(),
  ).toBeVisible();

  await expect(counts.bootstrap).toBe(1);
  await expect(counts.meReads).toBe(0);
  await expect(counts.myTenantsReads).toBe(0);
  await expect(page.getByText("Request Error")).toHaveCount(0);
});

test("Runtime contract: /pools/catalog generic Open topology templates CTA preserves topology return context", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto(
    "/pools/catalog?pool_id=pool-1&tab=topology&date=2026-01-01",
    { waitUntil: "domcontentloaded" },
  );

  await expect(
    page.getByRole("heading", { name: "Pool Catalog", level: 2 }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Open topology templates" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Open topology templates" }).click();

  await expect(page).toHaveURL(
    /\/pools\/topology-templates\?return_pool_id=pool-1&return_tab=topology&return_date=2026-01-01$/,
  );
  await expect(
    page.getByRole("heading", { name: "Topology Templates", level: 2 }),
  ).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Return to pool topology" }),
  ).toBeVisible();
  await expect(counts.bootstrap).toBe(1);
  await expect(counts.meReads).toBe(0);
  await expect(counts.myTenantsReads).toBe(0);
});

test("Runtime contract: /pools/catalog publishes a topology template revision through handoff and exposes it in consumer selection", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto(
    "/pools/catalog?pool_id=pool-1&tab=topology&date=2026-01-01",
    { waitUntil: "domcontentloaded" },
  );

  await expect(
    page.getByRole("heading", { name: "Pool Catalog", level: 2 }),
  ).toBeVisible();
  await page.getByTestId("pool-catalog-topology-authoring-mode").click();
  await selectVisibleAntdOption(page, "Template-based instantiation");
  await expect(
    page.getByTestId("pool-catalog-topology-authoring-mode"),
  ).toContainText("Template-based instantiation");
  await page.getByTestId("pool-catalog-topology-template-revision").click();
  await selectVisibleAntdOption(page, "Top Down Template · r3");
  await page.getByTestId("pool-catalog-revise-topology-template").click();

  await expect(page).toHaveURL(
    /\/pools\/topology-templates\?template=template-top-down&detail=1&compose=revise&return_pool_id=pool-1&return_tab=topology&return_date=2026-01-01$/,
  );
  await expect(
    page.getByTestId("pool-topology-templates-revise-drawer"),
  ).toBeVisible();

  const reviseRequestPromise = page.waitForRequest(
    (request) =>
      request.method() === "POST" &&
      request
        .url()
        .endsWith(
          "/api/v2/pools/topology-templates/template-top-down/revisions/",
        ),
  );
  await fillTopologyTemplateReviseForm(page);
  await page.getByTestId("pool-topology-templates-revise-submit").click();
  const reviseRequest = await reviseRequestPromise;
  const revisePayload = reviseRequest.postDataJSON() as Record<string, unknown>;

  expect(
    Array.isArray((revisePayload.revision as Record<string, unknown>).nodes),
  ).toBe(true);
  await expect(
    page
      .locator(
        'table:has(th:has-text("Created at")) tbody tr:not(.ant-table-measure-row)',
      )
      .first(),
  ).toContainText("r4");

  await page.getByRole("button", { name: "Return to pool topology" }).click();

  await expect(page).toHaveURL(
    /\/pools\/catalog\?pool_id=pool-1&tab=topology&date=2026-01-01$/,
  );
  await expect(
    page.getByRole("tab", { name: "Topology Editor" }),
  ).toHaveAttribute("aria-selected", "true");
  await page.getByTestId("pool-catalog-topology-authoring-mode").click();
  await selectVisibleAntdOption(page, "Template-based instantiation");
  await expect(
    page.getByTestId("pool-catalog-topology-authoring-mode"),
  ).toContainText("Template-based instantiation");
  await expect(
    page.getByText("Template-based path is the preferred reuse flow"),
  ).toBeVisible();
  await expect(
    page.getByTestId("pool-catalog-topology-template-revision"),
  ).toBeVisible();
  await page.getByTestId("pool-catalog-topology-template-revision").click();
  await expect(
    page
      .locator(".ant-select-dropdown:visible .ant-select-item-option-content", {
        hasText: "Top Down Template · r4",
      })
      .first(),
  ).toBeVisible();

  await expect(counts.bootstrap).toBe(1);
  await expect(counts.meReads).toBe(0);
  await expect(counts.myTenantsReads).toBe(0);
  await expect(page.getByText("Request Error")).toHaveCount(0);
});

test("Runtime contract: /pools/runs hands off to workflow diagnostics without replaying shell reads", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto(
    `/pools/runs?pool=${POOL_WITH_ATTACHMENT.id}&run=${POOL_RUN.id}&stage=inspect&detail=1`,
    {
      waitUntil: "domcontentloaded",
    },
  );

  await expect(
    page.getByRole("heading", { name: "Pool Runs", level: 2 }),
  ).toBeVisible();
  await expect.poll(() => counts.bootstrap).toBe(1);
  await expect(counts.meReads).toBe(0);
  await expect(counts.myTenantsReads).toBe(0);

  await page.getByRole("button", { name: "Open Workflow Diagnostics" }).click();

  await expect(page).toHaveURL(
    `/workflows/executions/${POOL_RUN.workflow_execution_id}`,
  );
  await expect(page.getByText("Workflow Execution")).toBeVisible();
  await expect(page.getByText("Execution Info")).toBeVisible();
  await expect(counts.bootstrap).toBe(1);
  await expect(counts.meReads).toBe(0);
  await expect(counts.myTenantsReads).toBe(0);
});

test("Runtime contract: /databases hands off to /operations without replaying shell reads", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto(`/databases?database=${DATABASE_ID}&context=inspect`, {
    waitUntil: "domcontentloaded",
  });

  await expect(
    page.getByRole("heading", { name: "Databases", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect.poll(() => counts.bootstrap).toBe(1);
  await expect.poll(() => counts.databaseLists).toBe(1);
  await expect(counts.meReads).toBe(0);
  await expect(counts.myTenantsReads).toBe(0);

  await page.getByTestId("database-workspace-open-operations").click();

  await expect(page).toHaveURL(
    new RegExp(`\\/operations\\?wizard=true&databases=${DATABASE_ID}$`),
  );
  await expect(
    page.getByRole("heading", { name: "Operations Monitor", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(counts.bootstrap).toBe(1);
  await expect(counts.meReads).toBe(0);
  await expect(counts.myTenantsReads).toBe(0);
});

test("Runtime contract: /operations hands off to workflow diagnostics without replaying shell reads", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto(
    `/operations?operation=${WORKFLOW_OPERATION.id}&tab=inspect`,
    {
      waitUntil: "domcontentloaded",
    },
  );

  await expect(
    page.getByRole("heading", { name: "Operations Monitor", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect.poll(() => counts.bootstrap).toBe(1);
  await expect.poll(() => counts.operationsList).toBe(1);
  await expect.poll(() => counts.operationDetails).toBe(1);
  await expect(counts.meReads).toBe(0);
  await expect(counts.myTenantsReads).toBe(0);

  await page.getByRole("button", { name: "Open workflow diagnostics" }).click();

  await expect(page).toHaveURL(
    `/workflows/executions/${POOL_RUN.workflow_execution_id}`,
  );
  await expect(counts.bootstrap).toBe(1);
  await expect(counts.meReads).toBe(0);
  await expect(counts.myTenantsReads).toBe(0);
});

test("Runtime contract: /operations ignores same-route menu re-entry and keeps inspect context stable", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto(
    `/operations?operation=${WORKFLOW_OPERATION.id}&tab=inspect`,
    {
      waitUntil: "domcontentloaded",
    },
  );

  const operationsMenuItem = page.getByRole("menuitem", {
    name: /Operations/i,
  });

  await expect(
    page.getByText(`Operation Details: ${WORKFLOW_OPERATION.name}`),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect.poll(() => counts.operationsList).toBe(1);
  await expect.poll(() => counts.operationDetails).toBe(1);

  await operationsMenuItem.click();
  await page.waitForTimeout(750);

  await expect(page).toHaveURL(
    new RegExp(
      `\\/operations\\?operation=${WORKFLOW_OPERATION.id}&tab=inspect$`,
    ),
  );
  await expect(
    page.getByText(`Operation Details: ${WORKFLOW_OPERATION.name}`),
  ).toBeVisible();
  await expect(counts.bootstrap).toBe(1);
  await expect(counts.operationsList).toBe(1);
  await expect(counts.operationDetails).toBe(1);
  await expect(page.getByText("Request Error")).toHaveCount(0);
});

test("Runtime contract: / ignores same-route menu re-entry and keeps dashboard shell stable", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto("/", { waitUntil: "domcontentloaded" });

  const dashboardMenuItem = page.getByRole("menuitem", {
    name: /Dashboard/i,
  });

  await expect(
    page.getByRole("heading", { name: "Dashboard", level: 2 }),
  ).toBeVisible();
  await expect.poll(() => counts.bootstrap).toBe(1);
  await expect.poll(() => counts.operationsList).toBeGreaterThan(0);
  await expect.poll(() => counts.databaseLists).toBeGreaterThan(0);
  await expect.poll(() => counts.clusterLists).toBeGreaterThan(0);

  const initialOperationsList = counts.operationsList;
  const initialDatabaseLists = counts.databaseLists;
  const initialClusterLists = counts.clusterLists;

  await dashboardMenuItem.click();
  await page.waitForTimeout(750);

  await expect(page).toHaveURL(/\/$/);
  await expect(
    page.getByRole("heading", { name: "Dashboard", level: 2 }),
  ).toBeVisible();
  await expect(counts.bootstrap).toBe(1);
  await expect(counts.operationsList).toBe(initialOperationsList);
  await expect(counts.databaseLists).toBe(initialDatabaseLists);
  await expect(counts.clusterLists).toBe(initialClusterLists);
  await expect(counts.meReads).toBe(0);
  await expect(counts.myTenantsReads).toBe(0);
  await expect(page.getByText("Request Error")).toHaveCount(0);
});

test("Runtime contract: /databases ignores same-route menu re-entry and keeps management context stable", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto(`/databases?database=${DATABASE_ID}&context=inspect`, {
    waitUntil: "domcontentloaded",
  });

  const databasesMenuItem = page.getByRole("menuitem", {
    name: /Databases/i,
  });

  await expect(
    page.getByText(`Database Workspace: ${DATABASE_RECORD.name}`),
  ).toBeVisible({ timeout: 15000 });
  await expect(page.getByTestId("database-workspace-selected-id")).toHaveText(
    DATABASE_ID,
    { timeout: 15000 },
  );
  await expect.poll(() => counts.databaseLists).toBe(1);
  await expect.poll(() => counts.clusterLists).toBe(1);
  await expect(counts.metadataManagementReads).toBe(0);

  await databasesMenuItem.click();
  await page.waitForTimeout(750);

  await expect(page).toHaveURL(
    new RegExp(`\\/databases\\?database=${DATABASE_ID}&context=inspect$`),
  );
  await expect(page.getByTestId("database-workspace-selected-id")).toHaveText(
    DATABASE_ID,
  );
  await expect(
    page.getByText(`Database Workspace: ${DATABASE_RECORD.name}`),
  ).toBeVisible();
  await expect(counts.bootstrap).toBe(1);
  await expect(counts.databaseLists).toBe(1);
  await expect(counts.clusterLists).toBe(1);
  await expect(counts.metadataManagementReads).toBe(0);
  await expect(counts.meReads).toBe(0);
  await expect(counts.myTenantsReads).toBe(0);
  await expect(page.getByText("Request Error")).toHaveCount(0);
});

test("Runtime contract: /pools/catalog ignores same-route menu re-entry and keeps attachment context stable", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto(
    `/pools/catalog?pool_id=${POOL_WITH_ATTACHMENT.id}&tab=pools&date=2026-01-01`,
    {
      waitUntil: "domcontentloaded",
    },
  );

  const poolCatalogMenuItem = page.getByRole("menuitem", {
    name: /Pool Catalog/i,
  });

  await expect(page.getByTestId("pool-catalog-context-pool")).toHaveText(
    "pool-main - Main Pool",
  );
  await expect(page.getByRole("tab", { name: "Pools" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect.poll(() => counts.organizationPools).toBe(1);
  await expect.poll(() => counts.poolOrganizations).toBe(1);
  await expect.poll(() => counts.poolOrganizationDetails).toBe(1);
  await expect.poll(() => counts.poolTopologySnapshots).toBe(1);
  await expect.poll(() => counts.poolGraphs).toBe(1);

  await poolCatalogMenuItem.click();
  await page.waitForTimeout(750);

  await expect(page).toHaveURL(
    new RegExp(
      `\\/pools\\/catalog\\?pool_id=${POOL_WITH_ATTACHMENT.id}&tab=pools&date=2026-01-01$`,
    ),
  );
  await expect(page.getByTestId("pool-catalog-context-pool")).toHaveText(
    "pool-main - Main Pool",
  );
  await expect(page.getByRole("tab", { name: "Pools" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(counts.bootstrap).toBe(1);
  await expect(counts.organizationPools).toBe(1);
  await expect(counts.poolOrganizations).toBe(1);
  await expect(counts.poolOrganizationDetails).toBe(1);
  await expect(counts.poolTopologySnapshots).toBe(1);
  await expect(counts.poolGraphs).toBe(1);
  await expect(counts.meReads).toBe(0);
  await expect(counts.myTenantsReads).toBe(0);
  await expect(page.getByText("Request Error")).toHaveCount(0);
});

test("Runtime contract: /pools/runs ignores same-route menu re-entry and keeps inspect context stable", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto(
    `/pools/runs?pool=${POOL_WITH_ATTACHMENT.id}&run=${POOL_RUN.id}&stage=inspect&detail=1`,
    {
      waitUntil: "domcontentloaded",
    },
  );

  const poolRunsMenuItem = page.getByRole("menuitem", { name: /Pool Runs/i });

  await expect(page.getByRole("tab", { name: "Inspect" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page.getByTestId("pool-runs-lineage-binding-id")).toHaveText(
    "binding-top-down",
  );
  await expect.poll(() => counts.organizationPools).toBe(1);
  await expect.poll(() => counts.poolGraphs).toBeGreaterThan(0);
  await expect.poll(() => counts.poolRuns).toBeGreaterThan(0);
  await expect.poll(() => counts.poolRunReports).toBeGreaterThan(0);

  const initialUrl = page.url();
  const initialPoolGraphs = counts.poolGraphs;
  const initialPoolRuns = counts.poolRuns;
  const initialPoolRunReports = counts.poolRunReports;

  await poolRunsMenuItem.click();
  await page.waitForTimeout(750);

  await expect(page).toHaveURL(initialUrl);
  await expect(page.getByRole("tab", { name: "Inspect" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page.getByTestId("pool-runs-lineage-binding-id")).toHaveText(
    "binding-top-down",
  );
  await expect(counts.bootstrap).toBe(1);
  await expect(counts.organizationPools).toBe(1);
  await expect(counts.poolGraphs).toBe(initialPoolGraphs);
  await expect(counts.poolRuns).toBe(initialPoolRuns);
  await expect(counts.poolRunReports).toBe(initialPoolRunReports);
  await expect(counts.meReads).toBe(0);
  await expect(counts.myTenantsReads).toBe(0);
  await expect(page.getByText("Request Error")).toHaveCount(0);
});

test("Runtime contract: /decisions hands off to /pools/execution-packs without replaying shell reads", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto(
    `/decisions?database=${DATABASE_ID}&decision=${DECISION.id}`,
    {
      waitUntil: "domcontentloaded",
    },
  );

  await expect(page.getByText("Decision Policy Library")).toBeVisible();
  await expect.poll(() => counts.bootstrap).toBe(1);
  await expect(counts.meReads).toBe(0);
  await expect(counts.myTenantsReads).toBe(0);

  await page.getByRole("button", { name: "Open execution packs" }).click();

  await expect(page).toHaveURL(/\/pools\/execution-packs$/);
  await expect(
    page.getByRole("heading", { name: "Execution Packs" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Create execution pack" }),
  ).toBeVisible();

  await expect(counts.bootstrap).toBe(1);
  await expect(counts.meReads).toBe(0);
  await expect(counts.myTenantsReads).toBe(0);
  await expect(page.getByText("Request Error")).toHaveCount(0);
});

test("UI platform: /decisions restores deep-link context and keeps diagnostics behind disclosure", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page);

  await page.goto(
    `/decisions?database=${DATABASE_ID}&decision=${FALLBACK_DECISION.id}&snapshot=all`,
    {
      waitUntil: "domcontentloaded",
    },
  );

  await expect(
    page.getByRole("combobox", { name: "Target database" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", {
      name: "Open decision Fallback services publication policy",
    }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(
    page.getByRole("button", { name: "Show matching configuration only" }),
  ).toBeVisible();
  await expect(page.getByText("shared_scope")).toHaveCount(0);

  await page.getByRole("button", { name: /Target metadata context/i }).click();

  await expect(page.getByText("shared_scope")).toBeVisible();
  await expect(page.getByText("snapshot-shared-services")).toBeVisible();
});

test("UI platform: /decisions keeps selected revision on browser back and forward", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page);

  await page.goto(
    `/decisions?database=${DATABASE_ID}&decision=${DECISION.id}`,
    {
      waitUntil: "domcontentloaded",
    },
  );

  const primaryDecisionButton = page.getByRole("button", {
    name: `Open decision ${DECISION.name}`,
  });
  const fallbackDecisionButton = page.getByRole("button", {
    name: `Open decision ${FALLBACK_DECISION.name}`,
  });

  await expect(primaryDecisionButton).toHaveAttribute("aria-pressed", "true");

  await fallbackDecisionButton.click();

  await expect(page).toHaveURL(
    new RegExp(`\\?database=${DATABASE_ID}&decision=${FALLBACK_DECISION.id}$`),
  );
  await expect(fallbackDecisionButton).toHaveAttribute("aria-pressed", "true");

  await page.goBack();

  await expect(page).toHaveURL(
    new RegExp(`\\?database=${DATABASE_ID}&decision=${DECISION.id}$`),
  );
  await expect(primaryDecisionButton).toHaveAttribute("aria-pressed", "true");

  await page.goForward();

  await expect(page).toHaveURL(
    new RegExp(`\\?database=${DATABASE_ID}&decision=${FALLBACK_DECISION.id}$`),
  );
  await expect(fallbackDecisionButton).toHaveAttribute("aria-pressed", "true");
});

test("Runtime contract: /decisions ignores same-route menu re-entry and keeps catalog state stable", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto(
    `/decisions?database=${DATABASE_ID}&decision=${DECISION.id}`,
    {
      waitUntil: "domcontentloaded",
    },
  );

  const decisionsMenuItem = page.getByRole("menuitem", {
    name: /Decisions/i,
  });
  const primaryDecisionButton = page.getByRole("button", {
    name: `Open decision ${DECISION.name}`,
  });

  await expect(primaryDecisionButton).toHaveAttribute("aria-pressed", "true");
  await expect.poll(() => counts.databaseLists).toBe(1);
  await expect.poll(() => counts.metadataManagementReads).toBe(1);
  await expect.poll(() => counts.decisionsScoped).toBe(1);

  await decisionsMenuItem.click();
  await page.waitForTimeout(750);

  await expect(page).toHaveURL(
    new RegExp(`\\?database=${DATABASE_ID}&decision=${DECISION.id}$`),
  );
  await expect(primaryDecisionButton).toHaveAttribute("aria-pressed", "true");
  await expect(counts.databaseLists).toBe(1);
  await expect(counts.metadataManagementReads).toBe(1);
  await expect(counts.decisionsScoped).toBe(1);
  await expect(counts.decisionsUnscoped).toBe(0);
  await expect(page.getByText("Request Error")).toHaveCount(0);
});

test("UI platform: /pools/execution-packs restores catalog context and keeps selection keyboard-first", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page);

  await page.goto(
    "/pools/execution-packs?q=legacy&profile=bp-legacy&detail=1",
    { waitUntil: "domcontentloaded" },
  );

  await expect(
    page.getByRole("heading", { name: "Execution Packs", level: 2 }),
  ).toBeVisible({ timeout: 15000 });
  await expect(page.getByLabel("Search execution packs")).toHaveValue(
    "legacy",
    { timeout: 15000 },
  );
  await expect(
    page.getByTestId("pool-binding-profiles-selected-code"),
  ).toHaveText("legacy-archive", { timeout: 15000 });
  await expect(page.getByText("legacy_archive · r1")).toBeVisible();
  await expect(page.getByText("Workflow definition key")).toHaveCount(0);

  await page.goto("/pools/execution-packs", {
    waitUntil: "domcontentloaded",
  });

  const legacyProfileButton = page.getByRole("button", {
    name: "Open execution pack legacy-archive",
  });
  await legacyProfileButton.focus();
  await page.keyboard.press("Enter");

  await expect(
    page.getByTestId("pool-binding-profiles-selected-code"),
  ).toHaveText("legacy-archive");
  await expect(legacyProfileButton).toHaveAttribute("aria-pressed", "true");
});

test("UI platform: /pools/execution-packs keeps selected profile on browser back and forward", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page);

  await page.goto(
    `/pools/execution-packs?profile=${BINDING_PROFILE_DETAIL.binding_profile_id}`,
    {
      waitUntil: "domcontentloaded",
    },
  );

  const servicesProfileButton = page.getByRole("button", {
    name: "Open execution pack services-publication",
  });
  const legacyProfileButton = page.getByRole("button", {
    name: "Open execution pack legacy-archive",
  });

  await expect(
    page.getByTestId("pool-binding-profiles-selected-code"),
  ).toHaveText("services-publication");
  await expect(servicesProfileButton).toHaveAttribute("aria-pressed", "true");

  await legacyProfileButton.click();

  await expect(page).toHaveURL(
    new RegExp(
      `\\?profile=${LEGACY_BINDING_PROFILE_DETAIL.binding_profile_id}&detail=1$`,
    ),
  );
  await expect(
    page.getByTestId("pool-binding-profiles-selected-code"),
  ).toHaveText("legacy-archive");
  await expect(legacyProfileButton).toHaveAttribute("aria-pressed", "true");

  await page.goBack();

  await expect(page).toHaveURL(
    new RegExp(`\\?profile=${BINDING_PROFILE_DETAIL.binding_profile_id}$`),
  );
  await expect(
    page.getByTestId("pool-binding-profiles-selected-code"),
  ).toHaveText("services-publication");
  await expect(servicesProfileButton).toHaveAttribute("aria-pressed", "true");

  await page.goForward();

  await expect(page).toHaveURL(
    new RegExp(
      `\\?profile=${LEGACY_BINDING_PROFILE_DETAIL.binding_profile_id}&detail=1$`,
    ),
  );
  await expect(
    page.getByTestId("pool-binding-profiles-selected-code"),
  ).toHaveText("legacy-archive");
  await expect(legacyProfileButton).toHaveAttribute("aria-pressed", "true");
});

test("UI platform: /pools/execution-packs keeps shell labels accessible and primary states above contrast floor", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true });

  await page.goto("/pools/execution-packs", {
    waitUntil: "domcontentloaded",
  });

  const streamStatusButton = page.getByRole("button", {
    name: "Stream: Connected",
  });
  const selectedMenuItem = page.getByRole("menuitem", {
    name: /Pool Execution Packs/i,
  });
  const subtitle = page
    .getByText(
      /Reusable execution-pack workspace for selecting an execution pack/i,
    )
    .first();
  const createProfileButton = page.getByRole("button", {
    name: "Create execution pack",
  });
  const deactivateProfileButton = page.getByRole("button", {
    name: "Deactivate execution pack",
  });
  const activeStatusBadge = page
    .getByTestId("pool-binding-profiles-status")
    .locator(".ant-tag");

  await expect(streamStatusButton).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "Where this execution pack is used",
      level: 3,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("columnheader", { name: "Opaque pin" }),
  ).toHaveCount(0);

  await page
    .getByRole("button", { name: /Advanced payload and immutable pins/i })
    .click();

  await expect(
    page.getByRole("columnheader", { name: "Opaque pin" }),
  ).toBeVisible();
  await expect(page.getByText("Latest immutable revision")).toBeVisible();

  await expectContrastAtLeast(selectedMenuItem, 4.5);
  await expectContrastAtLeast(streamStatusButton.locator(".ant-tag"), 4.5);
  await expectContrastAtLeast(subtitle, 4.5);
  await expectContrastAtLeast(createProfileButton, 4.5);
  await expectContrastAtLeast(deactivateProfileButton, 4.5);
  await expectContrastAtLeast(activeStatusBadge, 4.5);
});

test("UI platform: /pools/execution-packs keeps fallback stream labels and deactivated states above contrast floor", async ({
  page,
}) => {
  await setupAuth(page);
  await setupUiPlatformMocks(page, { isStaff: false });

  await page.goto(
    `/pools/execution-packs?profile=${LEGACY_BINDING_PROFILE_DETAIL.binding_profile_id}&detail=1`,
    { waitUntil: "domcontentloaded" },
  );

  const streamStatusButton = page.getByRole("button", {
    name: "Stream: Fallback",
  });
  const deactivatedStatusBadge = page
    .getByTestId("pool-binding-profiles-status")
    .locator(".ant-tag");

  await expect(streamStatusButton).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "Where this execution pack is used",
      level: 3,
    }),
  ).toBeVisible();
  await expect(
    page.getByTestId("pool-binding-profiles-selected-code"),
  ).toHaveText("legacy-archive");
  await expect(deactivatedStatusBadge).toContainText("Deactivated");

  await expectContrastAtLeast(streamStatusButton.locator(".ant-tag"), 4.5);
  await expectContrastAtLeast(deactivatedStatusBadge, 4.5);
});

test("Runtime contract: one browser instance keeps a single database stream owner across tabs", async ({
  context,
}) => {
  const counts = createRequestCounts();
  const firstPage = await context.newPage();

  await setupAuth(firstPage);
  await setupPersistentDatabaseStream(firstPage);
  await setupUiPlatformMocks(firstPage, { isStaff: true, counts });

  await firstPage.goto("/decisions", { waitUntil: "domcontentloaded" });
  await expect(firstPage.getByText("Decision Policy Library")).toBeVisible();
  await expect.poll(() => counts.streamTickets).toBe(1);

  const secondPage = await context.newPage();
  await setupAuth(secondPage);
  await setupPersistentDatabaseStream(secondPage);
  await setupUiPlatformMocks(secondPage, { isStaff: true, counts });

  await secondPage.goto("/pools/execution-packs", {
    waitUntil: "domcontentloaded",
  });
  await expect(secondPage.getByText("Execution Packs")).toBeVisible();
  await expect.poll(() => counts.streamTickets).toBe(1);
  await expect(firstPage.getByText("Request Error")).toHaveCount(0);
  await expect(secondPage.getByText("Request Error")).toHaveCount(0);
});

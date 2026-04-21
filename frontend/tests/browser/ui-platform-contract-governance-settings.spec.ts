import { expect, test } from "@playwright/test";
import {
  DATABASE_ID,
  ROUTE_MOUNT_TIMEOUT_MS,
  DATABASE_RECORD,
  WORKFLOW_OPERATION,
  ADMIN_USER,
  DLQ_MESSAGE,
  DELETED_ARTIFACT,
  setupAuth,
  setupPersistentDatabaseStream,
  setupUiPlatformMocks,
  expectNoHorizontalOverflow,
  expectNoScopedHorizontalOverflow,
  createRequestCounts,
} from "./ui-platform-contract.helpers";

test("UI platform: /rbac restores selected mode and tab from URL-backed governance workspace state", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true });

  await page.goto("/rbac?mode=roles&tab=audit", {
    waitUntil: "domcontentloaded",
  });

  await expect(
    page.getByRole("heading", { name: "RBAC", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(page.getByTestId("rbac-tab-roles")).toBeVisible();
  await expect(page.getByTestId("rbac-tab-audit")).toBeVisible();
  await expect(page.getByTestId("rbac-tab-permissions")).toHaveCount(0);
  await expect(page.getByTestId("rbac-audit-panel")).toBeVisible();
  await expectNoHorizontalOverflow(page);
});

test("UI platform: /users restores selected user context outside the current catalog slice and opens edit flow in a canonical modal shell", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, {
    isStaff: true,
    counts,
    selectedUserOutsideCatalogSlice: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto(`/users?user=${ADMIN_USER.id}&context=edit`, {
    waitUntil: "domcontentloaded",
  });

  await expect(
    page.getByRole("heading", { name: "Users", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(page.getByTestId("users-selected-username")).toContainText(
    ADMIN_USER.username,
  );
  const editModal = page.getByRole("dialog");
  await expect(editModal).toBeVisible();
  await expect(editModal.getByLabel("Username")).toHaveValue(
    ADMIN_USER.username,
  );
  await expect(editModal.getByRole("button", { name: "Save" })).toBeVisible();
  await expect.poll(() => counts.usersDetail).toBe(1);
  await expectNoHorizontalOverflow(page);
});

test("UI platform: /dlq preserves selected message context outside the current catalog slice and hands off to /operations without leaving the SPA shell", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, {
    isStaff: true,
    counts,
    selectedDlqOutsideCatalogSlice: true,
  });

  await page.goto(`/dlq?message=${DLQ_MESSAGE.dlq_message_id}`, {
    waitUntil: "domcontentloaded",
  });

  await expect(
    page.getByRole("heading", { name: "DLQ", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  const detailDrawer = page.getByTestId("dlq-message-detail-drawer");
  await expect(detailDrawer).toBeVisible();
  await expect(detailDrawer.getByText(DLQ_MESSAGE.error_message)).toBeVisible();
  await expect.poll(() => counts.dlqDetail).toBe(1);
  await detailDrawer
    .getByRole("button", { name: "Open in Operations" })
    .click();

  await expect(page).toHaveURL(
    new RegExp(
      `\\/operations\\?tab=monitor&operation=${WORKFLOW_OPERATION.id}$`,
    ),
  );
  await expect(
    page.getByRole("heading", { name: "Operations Monitor", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
});

test("UI platform: /artifacts restores deleted catalog tab and selected artifact detail outside the current catalog slice in a mobile-safe drawer", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, {
    isStaff: true,
    counts,
    selectedArtifactOutsideCatalogSlice: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto(
    `/artifacts?tab=deleted&artifact=${DELETED_ARTIFACT.id}&context=inspect`,
    {
      waitUntil: "domcontentloaded",
    },
  );

  await expect(
    page.getByRole("heading", { name: "Artifacts", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(page.getByText("tab=deleted")).toBeVisible();
  const detailDrawer = page.getByRole("dialog");
  await expect(detailDrawer).toBeVisible();
  await expect(detailDrawer.getByText(DELETED_ARTIFACT.name)).toBeVisible();
  await expect(
    detailDrawer.getByRole("button", { name: "Delete permanently" }),
  ).toBeVisible();
  await expect.poll(() => counts.artifactDetail).toBe(1);
  await expect(page.locator(".ant-drawer-content-wrapper:visible")).toHaveCount(
    1,
  );
  await expectNoHorizontalOverflow(page);
});

test("UI platform: /extensions restores selected extension context in a mobile-safe secondary drawer", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true });
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto(
    `/extensions?extension=ServicePublisher&database=${DATABASE_ID}`,
    {
      waitUntil: "domcontentloaded",
    },
  );

  await expect(
    page.getByRole("heading", { name: "Extensions", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  const detailDrawer = page.getByTestId("extensions-management-drawer");
  await expect(detailDrawer).toBeVisible();
  await expect(detailDrawer.getByTestId("extensions-selected-name")).toHaveText(
    "ServicePublisher",
  );
  await expect(
    detailDrawer.getByTestId("extensions-selected-database"),
  ).toHaveText(DATABASE_RECORD.name);
  await expect(page.locator(".ant-drawer-content-wrapper:visible")).toHaveCount(
    1,
  );
  await expectNoHorizontalOverflow(page);
  await expectNoScopedHorizontalOverflow(
    detailDrawer,
    "Extensions management drawer",
  );
});

test("UI platform: /settings/runtime restores selected setting context in a canonical settings drawer", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true });
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto(
    "/settings/runtime?setting=runtime.concurrency.max_workers&context=setting",
    {
      waitUntil: "domcontentloaded",
    },
  );

  await expect(
    page.getByRole("heading", { name: "Runtime Settings", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(page.getByTestId("runtime-settings-page")).toBeVisible();
  const detailDrawer = page.getByTestId("runtime-settings-detail-drawer");
  await expect(detailDrawer).toBeVisible();
  await expect(
    detailDrawer.getByText("runtime.concurrency.max_workers"),
  ).toBeVisible();
  await expect(
    detailDrawer.getByRole("button", { name: "Save" }),
  ).toBeVisible();
  await expect(page.locator(".ant-drawer-content-wrapper:visible")).toHaveCount(
    1,
  );
  await expectNoHorizontalOverflow(page);
});

test("UI platform: /settings/timeline keeps diagnostics in a single mobile-safe secondary drawer", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true });
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto("/settings/timeline?context=diagnostics", {
    waitUntil: "domcontentloaded",
  });

  await expect(
    page.getByRole("heading", { name: "Timeline Settings", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(page.getByTestId("timeline-settings-page")).toBeVisible();
  const diagnosticsDrawer = page.getByTestId(
    "timeline-settings-diagnostics-drawer",
  );
  await expect(diagnosticsDrawer).toBeVisible();
  await expect(
    diagnosticsDrawer.getByText("Active mux streams: 2/16"),
  ).toBeVisible();
  await expect(page.locator(".ant-drawer-content-wrapper:visible")).toHaveCount(
    1,
  );
  await expectNoHorizontalOverflow(page);
  await expectNoScopedHorizontalOverflow(
    diagnosticsDrawer,
    "Timeline settings diagnostics drawer",
  );
});

test("UI platform: /settings/command-schemas restores driver, mode, and selected command in a mobile-safe detail drawer", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true });
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto(
    "/settings/command-schemas?driver=ibcmd&mode=guided&command=ibcmd.publish",
    {
      waitUntil: "domcontentloaded",
    },
  );

  await expect(
    page.getByRole("heading", { name: "Command Schemas", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(page.getByTestId("command-schemas-page")).toBeVisible();
  await expect(
    page.getByTestId("command-schemas-command-ibcmd.publish"),
  ).toHaveAttribute("aria-current", "true");
  const detailDrawer = page.getByRole("dialog");
  await expect(detailDrawer).toBeVisible();
  await expect(detailDrawer.getByText("Publish infobase")).toBeVisible();
  await expect(page.locator(".ant-drawer-content-wrapper:visible")).toHaveCount(
    1,
  );
  await expectNoHorizontalOverflow(page);
});

test("Runtime contract: /extensions ignores same-route menu re-entry and keeps selected extension context stable", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto(
    `/extensions?extension=ServicePublisher&database=${DATABASE_ID}`,
    {
      waitUntil: "domcontentloaded",
    },
  );

  const extensionsMenuItem = page.getByRole("menuitem", {
    name: /Extensions/i,
  });
  const detailDrawer = page.getByTestId("extensions-management-drawer");

  await expect(detailDrawer).toBeVisible({ timeout: ROUTE_MOUNT_TIMEOUT_MS });
  await expect(detailDrawer.getByTestId("extensions-selected-name")).toHaveText(
    "ServicePublisher",
  );
  await expect.poll(() => counts.extensionsOverview).toBeGreaterThan(0);
  await expect
    .poll(() => counts.extensionsOverviewDatabases)
    .toBeGreaterThan(0);
  await expect.poll(() => counts.extensionsManualBindings).toBeGreaterThan(0);

  const initialUrl = page.url();
  const initialOverviewReads = counts.extensionsOverview;
  const initialOverviewDatabasesReads = counts.extensionsOverviewDatabases;
  const initialManualBindingsReads = counts.extensionsManualBindings;

  await extensionsMenuItem.dispatchEvent("click");
  await page.waitForTimeout(750);

  await expect(page).toHaveURL(initialUrl);
  await expect(detailDrawer).toBeVisible();
  await expect(detailDrawer.getByTestId("extensions-selected-name")).toHaveText(
    "ServicePublisher",
  );
  await expect(counts.bootstrap).toBe(1);
  await expect(counts.extensionsOverview).toBe(initialOverviewReads);
  await expect(counts.extensionsOverviewDatabases).toBe(
    initialOverviewDatabasesReads,
  );
  await expect(counts.extensionsManualBindings).toBe(
    initialManualBindingsReads,
  );
  await expect(page.getByText("Request Error")).toHaveCount(0);
});

test("Runtime contract: /settings/runtime ignores same-route menu re-entry and keeps selected setting context stable", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto(
    "/settings/runtime?setting=runtime.concurrency.max_workers&context=setting",
    {
      waitUntil: "domcontentloaded",
    },
  );

  const runtimeSettingsMenuItem = page.getByRole("menuitem", {
    name: /Runtime Settings/i,
  });
  const detailDrawer = page.getByTestId("runtime-settings-detail-drawer");

  await expect(detailDrawer).toBeVisible({ timeout: ROUTE_MOUNT_TIMEOUT_MS });
  await expect(
    detailDrawer.getByText("runtime.concurrency.max_workers"),
  ).toBeVisible();
  await expect.poll(() => counts.runtimeSettingsReads).toBeGreaterThan(0);

  const initialUrl = page.url();
  const initialRuntimeSettingsReads = counts.runtimeSettingsReads;

  await runtimeSettingsMenuItem.dispatchEvent("click");
  await page.waitForTimeout(750);

  await expect(page).toHaveURL(initialUrl);
  await expect(detailDrawer).toBeVisible();
  await expect(
    detailDrawer.getByText("runtime.concurrency.max_workers"),
  ).toBeVisible();
  await expect(counts.bootstrap).toBe(1);
  await expect(counts.runtimeSettingsReads).toBe(initialRuntimeSettingsReads);
  await expect(page.getByText("Request Error")).toHaveCount(0);
});

test("Runtime contract: /settings/timeline ignores same-route menu re-entry and keeps diagnostics context stable", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto("/settings/timeline?context=diagnostics", {
    waitUntil: "domcontentloaded",
  });

  const timelineSettingsMenuItem = page.getByRole("menuitem", {
    name: /Timeline Settings/i,
  });
  const diagnosticsDrawer = page.getByTestId(
    "timeline-settings-diagnostics-drawer",
  );

  await expect(diagnosticsDrawer).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(
    diagnosticsDrawer.getByText("Active mux streams: 2/16"),
  ).toBeVisible();
  await expect.poll(() => counts.runtimeSettingsReads).toBeGreaterThan(0);
  await expect.poll(() => counts.streamMuxStatusReads).toBeGreaterThan(0);

  const initialUrl = page.url();
  const initialRuntimeSettingsReads = counts.runtimeSettingsReads;
  const initialStreamMuxStatusReads = counts.streamMuxStatusReads;

  await timelineSettingsMenuItem.dispatchEvent("click");
  await page.waitForTimeout(750);

  await expect(page).toHaveURL(initialUrl);
  await expect(diagnosticsDrawer).toBeVisible();
  await expect(
    diagnosticsDrawer.getByText("Active mux streams: 2/16"),
  ).toBeVisible();
  await expect(counts.bootstrap).toBe(1);
  await expect(counts.runtimeSettingsReads).toBe(initialRuntimeSettingsReads);
  await expect(counts.streamMuxStatusReads).toBe(initialStreamMuxStatusReads);
  await expect(page.getByText("Request Error")).toHaveCount(0);
});

test("Runtime contract: /settings/command-schemas ignores same-route menu re-entry and keeps selected command context stable", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto(
    "/settings/command-schemas?driver=ibcmd&mode=guided&command=ibcmd.publish",
    {
      waitUntil: "domcontentloaded",
    },
  );

  const commandSchemasMenuItem = page.getByRole("menuitem", {
    name: /Command Schemas/i,
  });
  const selectedCommand = page.getByTestId(
    "command-schemas-command-ibcmd.publish",
  );

  await expect(selectedCommand).toHaveAttribute("aria-current", "true", {
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(page.getByText("Publish infobase")).toBeVisible();
  await expect.poll(() => counts.commandSchemasEditorReads).toBeGreaterThan(0);

  const initialUrl = page.url();
  const initialCommandSchemasReads = counts.commandSchemasEditorReads;

  await commandSchemasMenuItem.dispatchEvent("click");
  await page.waitForTimeout(750);

  await expect(page).toHaveURL(initialUrl);
  await expect(selectedCommand).toHaveAttribute("aria-current", "true");
  await expect(page.getByText("Publish infobase")).toBeVisible();
  await expect(counts.bootstrap).toBe(1);
  await expect(counts.commandSchemasEditorReads).toBe(
    initialCommandSchemasReads,
  );
  await expect(page.getByText("Request Error")).toHaveCount(0);
});

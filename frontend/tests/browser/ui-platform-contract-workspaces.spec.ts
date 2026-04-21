import { expect, test } from "@playwright/test";
import {
  DATABASE_ID,
  ROUTE_MOUNT_TIMEOUT_MS,
  DATABASE_RECORD,
  WORKFLOW,
  POOL_WITH_ATTACHMENT,
  POOL_RUN,
  WORKFLOW_EXECUTION_DETAIL,
  WORKFLOW_OPERATION,
  ZERO_TASK_OPERATION,
  setupAuth,
  setupPersistentDatabaseStream,
  setupUiPlatformMocks,
  switchShellLocaleToEnglish,
  expectNoHorizontalOverflow,
  expectNoScopedHorizontalOverflow,
  fillTopologyTemplateCreateForm,
  fillTopologyTemplateReviseForm,
  expectVisibleWithinContainer,
  createRequestCounts,
} from "./ui-platform-contract.helpers";

test("UI platform: /decisions keeps mobile list stable and opens detail in a drawer", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page);
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto("/decisions", { waitUntil: "domcontentloaded" });

  await expect(page.getByText("Decision Policy Library")).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expectNoHorizontalOverflow(page);

  await page.getByText("Services publication policy").first().click();

  const detailDrawer = page.getByRole("dialog");
  await expect(detailDrawer).toBeVisible();
  await expect(
    detailDrawer.getByText("Compiled document_policy JSON"),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
});

test("UI platform: /decisions opens authoring in a mobile-safe drawer with labeled fields", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page);
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto("/decisions", { waitUntil: "domcontentloaded" });

  await page.getByRole("button", { name: "New policy" }).click();

  const authoringDrawer = page.getByRole("dialog");
  await expect(authoringDrawer).toBeVisible();
  await expect(authoringDrawer.getByLabel("Decision table ID")).toBeVisible();
  await expect(authoringDrawer.getByLabel("Decision name")).toBeVisible();
  await expect(
    authoringDrawer.getByRole("button", { name: "Save decision" }),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
});

test("UI platform: /pools/execution-packs keeps mobile catalog readable and opens detail in a drawer", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page);
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto("/pools/execution-packs", {
    waitUntil: "domcontentloaded",
  });

  await expect(page.getByText("Execution Packs")).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expectNoHorizontalOverflow(page);

  await page
    .getByRole("button", { name: "Open execution pack services-publication" })
    .click();

  const detailDrawer = page.getByRole("dialog");
  await expect(detailDrawer).toBeVisible();
  await expect(
    detailDrawer.getByTestId("pool-binding-profiles-selected-code"),
  ).toHaveText("services-publication");
  await expect(
    detailDrawer.getByRole("heading", {
      name: "Where this execution pack is used",
      level: 3,
    }),
  ).toBeVisible();
  await expect(
    detailDrawer.getByRole("button", { name: "Publish new revision" }),
  ).toBeVisible();
  await expect(
    detailDrawer.getByRole("button", { name: "Deactivate execution pack" }),
  ).toBeVisible();
  await expect(
    detailDrawer.getByRole("columnheader", { name: "Opaque pin" }),
  ).toHaveCount(0);
  await expect(
    detailDrawer.getByRole("button", {
      name: /Advanced payload and immutable pins/i,
    }),
  ).toBeVisible();
  await expectVisibleWithinContainer(
    detailDrawer.getByRole("button", { name: "Publish new revision" }),
    detailDrawer,
  );
  await expectVisibleWithinContainer(
    detailDrawer.getByRole("button", { name: "Deactivate execution pack" }),
    detailDrawer,
  );
  await expectNoHorizontalOverflow(page);
});

test("UI platform: /pools/execution-packs opens create-execution-pack authoring in a mobile-safe modal shell", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page);
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto("/pools/execution-packs", {
    waitUntil: "domcontentloaded",
  });

  await page.getByRole("button", { name: "Create execution pack" }).click();

  const authoringModal = page.getByRole("dialog");
  await expect(authoringModal).toBeVisible();
  await expect(authoringModal.getByLabel("Execution Pack code")).toBeVisible();
  await expect(authoringModal.getByLabel("Execution Pack name")).toBeVisible();
  await expect(
    authoringModal.getByTestId(
      "pool-binding-profiles-create-workflow-revision-select",
    ),
  ).toBeVisible();
  await expect(
    authoringModal.getByRole("button", { name: "Create execution pack" }),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
});

test("UI platform: /pools/execution-packs keeps publication slots compact in the publish revision modal", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page);

  await page.goto(
    "/pools/execution-packs?profile=e54257e5-c587-4467-bb7c-4eb53ee05293&detail=1",
    {
      waitUntil: "domcontentloaded",
    },
  );

  await page.getByRole("button", { name: "Publish new revision" }).click();

  const authoringModal = page.getByRole("dialog");
  await expect(authoringModal).toBeVisible();

  await authoringModal
    .getByTestId("pool-binding-profiles-revise-add-slot")
    .click();
  await authoringModal
    .getByTestId("pool-binding-profiles-revise-add-slot")
    .click();

  const slotRows = [0, 1, 2].map((slotIndex) =>
    authoringModal.getByTestId(
      `pool-binding-profiles-revise-slot-row-${slotIndex}`,
    ),
  );

  const boxes = await Promise.all(
    slotRows.map(async (locator) => locator.boundingBox()),
  );
  const [firstRow, secondRow, thirdRow] = boxes;

  if (!firstRow || !secondRow || !thirdRow) {
    throw new Error(
      "Expected publication slot rows to have measurable bounding boxes.",
    );
  }

  const firstGap = secondRow.y - (firstRow.y + firstRow.height);
  const secondGap = thirdRow.y - (secondRow.y + secondRow.height);

  expect(firstGap).toBeLessThanOrEqual(24);
  expect(secondGap).toBeLessThanOrEqual(24);
  await expectVisibleWithinContainer(slotRows[2], authoringModal);
});

test("UI platform: /pools/topology-templates keeps mobile catalog readable and opens detail in a drawer", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page);
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto("/pools/topology-templates", {
    waitUntil: "domcontentloaded",
  });

  await expect(page.getByText("Topology Templates")).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expectNoHorizontalOverflow(page);

  await page
    .getByRole("button", { name: "Open topology template top-down-template" })
    .click();

  const detailDrawer = page.getByRole("dialog");
  await expect(detailDrawer).toBeVisible();
  await expect(
    detailDrawer.getByTestId("pool-topology-templates-selected-code"),
  ).toHaveText("top-down-template");
  await expect(
    detailDrawer.getByRole("button", { name: "Publish new revision" }),
  ).toBeVisible();
  await expect(detailDrawer.getByText("Root · root")).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await expectNoScopedHorizontalOverflow(
    detailDrawer,
    "Topology template detail drawer",
  );
});

test("UI platform: /pools/topology-templates opens create-template authoring in a mobile-safe drawer shell", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page);
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto("/pools/topology-templates", {
    waitUntil: "domcontentloaded",
  });

  await page.getByRole("button", { name: "Create template" }).click();

  const authoringDrawer = page.getByRole("dialog");
  await expect(authoringDrawer).toBeVisible();
  await expect(authoringDrawer.getByLabel("Template code")).toBeVisible();
  await expect(authoringDrawer.getByLabel("Template name")).toBeVisible();
  await expect(
    authoringDrawer.getByRole("button", { name: "Create template" }),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await expectNoScopedHorizontalOverflow(
    authoringDrawer,
    "Topology template create drawer",
  );
});

test("UI platform: /pools/topology-templates opens revise-template authoring in a mobile-safe drawer shell", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page);
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto(
    "/pools/topology-templates?template=template-top-down&detail=1",
    {
      waitUntil: "domcontentloaded",
    },
  );

  await page.getByRole("button", { name: "Publish new revision" }).click();

  const reviseDrawer = page.getByTestId(
    "pool-topology-templates-revise-drawer",
  );
  await expect(reviseDrawer).toBeVisible();
  await expect(page.locator(".ant-drawer-content-wrapper:visible")).toHaveCount(
    1,
  );
  await expect(
    reviseDrawer.getByTestId("pool-topology-templates-revise-node-label-0"),
  ).toBeVisible();
  await expect(
    reviseDrawer.getByRole("button", { name: "Publish revision" }),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await expectNoScopedHorizontalOverflow(
    reviseDrawer,
    "Topology template revise drawer",
  );
});

test("UI platform: /workflows restores selected workflow detail from URL-backed workspace state", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto(`/workflows?workflow=${WORKFLOW.id}&detail=1`, {
    waitUntil: "domcontentloaded",
  });

  await expect(
    page.getByRole("heading", { name: "Workflow Scheme Library", level: 2 }),
  ).toBeVisible();
  await expect(page.getByTestId("workflow-list-selected-id")).toHaveText(
    WORKFLOW.id,
  );
  await expect(page.getByTestId("workflow-list-selected-dag")).toContainText(
    '"start"',
  );
  await expect(page.getByTestId("workflow-list-detail-open")).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await expect.poll(() => counts.bootstrap).toBe(1);
});

test("UI platform: /templates restores selected template detail from URL-backed workspace state", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto("/templates?template=tpl-sync-extension&detail=1", {
    waitUntil: "domcontentloaded",
  });

  await expect(
    page.getByRole("heading", { name: "Operation Templates", level: 2 }),
  ).toBeVisible();
  await expect(page.getByTestId("templates-selected-id")).toHaveText(
    "tpl-sync-extension",
  );
  await expect(
    page.getByRole("button", { name: "Edit", exact: true }),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await expect.poll(() => counts.bootstrap).toBe(1);
});

test("UI platform: /templates keeps mobile catalog readable and opens detail in a drawer", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true });
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto("/templates", { waitUntil: "domcontentloaded" });

  await expect(
    page.getByRole("heading", { name: "Operation Templates", level: 2 }),
  ).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expectNoHorizontalOverflow(page);

  await page.getByTestId("templates-catalog-item-tpl-sync-extension").click();

  const detailDrawer = page.getByRole("dialog");
  await expect(detailDrawer).toBeVisible();
  await expect(detailDrawer.getByTestId("templates-selected-id")).toHaveText(
    "tpl-sync-extension",
  );
  await expect(
    detailDrawer.getByRole("button", { name: "Edit", exact: true }),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
});

test("UI platform: /workflows keeps mobile catalog readable and opens detail in a drawer", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true });
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto("/workflows", { waitUntil: "domcontentloaded" });

  await expect(
    page.getByRole("heading", { name: "Workflow Scheme Library", level: 2 }),
  ).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expectNoHorizontalOverflow(page);

  await page.getByTestId(`workflow-list-catalog-item-${WORKFLOW.id}`).click();

  const detailDrawer = page.getByRole("dialog");
  await expect(detailDrawer).toBeVisible();
  await expect(
    detailDrawer.getByTestId("workflow-list-selected-id"),
  ).toHaveText(WORKFLOW.id);
  await expect(
    detailDrawer.getByTestId("workflow-list-detail-open"),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
});

test("UI platform: /workflows returns from designer to the same URL-backed workspace context", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true });

  const workflowParams = new URLSearchParams();
  workflowParams.set("q", "Services");
  workflowParams.set("filters", JSON.stringify({ workflow_type: "complex" }));
  workflowParams.set(
    "sort",
    JSON.stringify({ key: "updated_at", order: "desc" }),
  );
  workflowParams.set("workflow", WORKFLOW.id);
  workflowParams.set("detail", "1");

  await page.goto(`/workflows?${workflowParams.toString()}`, {
    waitUntil: "domcontentloaded",
  });

  await page.getByTestId("workflow-list-detail-open").click();
  await expect(page).toHaveURL(new RegExp(`/workflows/${WORKFLOW.id}`));
  await page.getByRole("button", { name: "Back" }).click();

  await expect
    .poll(() => {
      const url = new URL(page.url());
      return JSON.stringify({
        pathname: url.pathname,
        q: url.searchParams.get("q"),
        filters: url.searchParams.get("filters"),
        sort: url.searchParams.get("sort"),
        workflow: url.searchParams.get("workflow"),
        detail: url.searchParams.get("detail"),
      });
    })
    .toBe(
      JSON.stringify({
        pathname: "/workflows",
        q: "Services",
        filters: JSON.stringify({ workflow_type: "complex" }),
        sort: JSON.stringify({ key: "updated_at", order: "desc" }),
        workflow: WORKFLOW.id,
        detail: "1",
      }),
    );
  await expect(page.getByTestId("workflow-list-selected-id")).toHaveText(
    WORKFLOW.id,
  );
});

test("UI platform: /workflows/executions restores selected execution detail from URL-backed workspace state", async ({
  page,
}) => {
  const counts = createRequestCounts();

  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true, counts });

  await page.goto(
    `/workflows/executions?status=pending&execution=${WORKFLOW_EXECUTION_DETAIL.id}&detail=1`,
    {
      waitUntil: "domcontentloaded",
    },
  );

  await expect(
    page.getByRole("heading", { name: "Workflow Executions", level: 2 }),
  ).toBeVisible();
  await expect(page.getByTestId("workflow-executions-selected-id")).toHaveText(
    WORKFLOW_EXECUTION_DETAIL.id,
  );
  await expect(
    page.getByTestId("workflow-executions-selected-input-context"),
  ).toContainText(`"${POOL_RUN.pool_id}"`);
  await expect(
    page.getByTestId("workflow-executions-detail-open"),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await expect.poll(() => counts.bootstrap).toBe(1);
});

test("UI platform: /workflows/executions keeps mobile catalog readable and opens detail in a drawer", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true });
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto("/workflows/executions", { waitUntil: "domcontentloaded" });

  await expect(
    page.getByRole("heading", { name: "Workflow Executions", level: 2 }),
  ).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expectNoHorizontalOverflow(page);

  await page
    .getByTestId(
      `workflow-executions-catalog-item-${WORKFLOW_EXECUTION_DETAIL.id}`,
    )
    .click();

  const detailDrawer = page.getByRole("dialog");
  await expect(detailDrawer).toBeVisible();
  await expect(
    detailDrawer.getByTestId("workflow-executions-selected-id"),
  ).toHaveText(WORKFLOW_EXECUTION_DETAIL.id);
  await expect(
    detailDrawer.getByTestId("workflow-executions-detail-open"),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
});

test("UI platform: /workflows/executions returns from monitor to the same URL-backed diagnostics context", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true });

  const executionParams = new URLSearchParams();
  executionParams.set("status", "pending");
  executionParams.set("workflow_id", WORKFLOW.id);
  executionParams.set("execution", WORKFLOW_EXECUTION_DETAIL.id);
  executionParams.set("detail", "1");

  await page.goto(`/workflows/executions?${executionParams.toString()}`, {
    waitUntil: "domcontentloaded",
  });

  await page.getByTestId("workflow-executions-detail-open").click();
  await expect(page).toHaveURL(
    new RegExp(`/workflows/executions/${WORKFLOW_EXECUTION_DETAIL.id}`),
  );
  await page.getByRole("button", { name: "Back" }).click();

  await expect
    .poll(() => {
      const url = new URL(page.url());
      return JSON.stringify({
        pathname: url.pathname,
        status: url.searchParams.get("status"),
        workflow_id: url.searchParams.get("workflow_id"),
        execution: url.searchParams.get("execution"),
        detail: url.searchParams.get("detail"),
      });
    })
    .toBe(
      JSON.stringify({
        pathname: "/workflows/executions",
        status: "pending",
        workflow_id: WORKFLOW.id,
        execution: WORKFLOW_EXECUTION_DETAIL.id,
        detail: "1",
      }),
    );
  await expect(page.getByTestId("workflow-executions-selected-id")).toHaveText(
    WORKFLOW_EXECUTION_DETAIL.id,
  );
});

test("UI platform: /workflows/:id restores selected node context from URL-backed authoring state", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true });

  await page.goto(`/workflows/${WORKFLOW.id}?node=start`, {
    waitUntil: "domcontentloaded",
  });

  await expect(
    page.getByRole("heading", { name: WORKFLOW.name, level: 2 }),
  ).toBeVisible();
  await expect(page.getByTestId("workflow-designer-selected-node")).toHaveText(
    "Selected node: Start",
  );
  await expectNoHorizontalOverflow(page);
});

test("UI platform: /workflows/:id keeps mobile authoring readable and opens platform-owned drawers", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true });
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto(`/workflows/${WORKFLOW.id}`, {
    waitUntil: "domcontentloaded",
  });

  await expect(
    page.getByRole("heading", { name: WORKFLOW.name, level: 2 }),
  ).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Node palette" }),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await page.getByRole("button", { name: "Node palette" }).click();
  await expect(
    page.getByTestId("workflow-designer-palette-drawer"),
  ).toBeVisible();
  await expect(page.getByText("Scheme Building Blocks")).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(
    page.getByTestId("workflow-designer-palette-drawer"),
  ).toBeHidden();

  await page
    .getByTestId("rf__node-start")
    .evaluate((element: HTMLElement) => element.click());

  const nodeDrawer = page.getByTestId("workflow-designer-node-drawer");
  await expect(nodeDrawer).toBeVisible();
  await expect(page.getByTestId("workflow-designer-selected-node")).toHaveText(
    "Selected node: Start",
  );
  await expectNoHorizontalOverflow(page);
});

test("UI platform: /workflows/executions/:executionId restores selected node diagnostics from URL-backed workspace state", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true });

  await page.goto(
    `/workflows/executions/${WORKFLOW_EXECUTION_DETAIL.id}?node=start`,
    {
      waitUntil: "domcontentloaded",
    },
  );

  await expect(
    page.getByRole("heading", { name: "Workflow Execution", level: 2 }),
  ).toBeVisible();
  await expect(page.getByTestId("workflow-monitor-selected-node")).toHaveText(
    "Selected node: Start",
  );
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(
    page.getByRole("dialog").getByText("start", { exact: true }),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
});

test("UI platform: /workflows/executions/:executionId keeps diagnostics readable on mobile and opens node details in a drawer", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true });
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto(`/workflows/executions/${WORKFLOW_EXECUTION_DETAIL.id}`, {
    waitUntil: "domcontentloaded",
  });

  await expect(
    page.getByRole("heading", { name: "Workflow Execution", level: 2 }),
  ).toBeVisible();
  await expect(page.getByText("Execution Info")).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expectNoHorizontalOverflow(page);

  await page
    .getByTestId("rf__node-start")
    .evaluate((element: HTMLElement) => element.click());

  const nodeDrawer = page.getByRole("dialog");
  await expect(nodeDrawer).toBeVisible();
  await expect(page.getByTestId("workflow-monitor-selected-node")).toHaveText(
    "Selected node: Start",
  );
  await expect(nodeDrawer.getByText("start", { exact: true })).toBeVisible();
  await expectNoHorizontalOverflow(page);
});

test("UI platform: /pools/topology-templates submits create-template authoring and surfaces the created template in the detail drawer", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page);

  await page.goto("/pools/topology-templates", {
    waitUntil: "domcontentloaded",
  });

  await page.getByRole("button", { name: "Create template" }).click();
  await fillTopologyTemplateCreateForm(page);

  const createRequestPromise = page.waitForRequest(
    (request) =>
      request.method() === "POST" &&
      request.url().endsWith("/api/v2/pools/topology-templates/"),
  );
  await page.getByTestId("pool-topology-templates-create-submit").click();

  const createRequest = await createRequestPromise;
  const createPayload = createRequest.postDataJSON() as Record<string, unknown>;

  expect(createPayload.code).toBe("new-template");
  expect(createPayload.name).toBe("New Template");
  expect(createPayload.description).toBe("Reusable topology authoring surface");
  await expect(
    page.getByTestId("pool-topology-templates-selected-code"),
  ).toHaveText("new-template");
  await expect(page).toHaveURL(
    /\/pools\/topology-templates\?template=template-\d+&detail=1$/,
  );
  await expect(
    page.getByRole("button", { name: "Publish new revision" }),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
});

test("UI platform: /pools/topology-templates submits revise-template authoring and refreshes the selected revision evidence", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page);

  await page.goto(
    "/pools/topology-templates?template=template-top-down&detail=1",
    {
      waitUntil: "domcontentloaded",
    },
  );

  await page.getByRole("button", { name: "Publish new revision" }).click();
  await fillTopologyTemplateReviseForm(page);

  const reviseRequestPromise = page.waitForRequest(
    (request) =>
      request.method() === "POST" &&
      request
        .url()
        .endsWith(
          "/api/v2/pools/topology-templates/template-top-down/revisions/",
        ),
  );
  await page.getByTestId("pool-topology-templates-revise-submit").click();

  const reviseRequest = await reviseRequestPromise;
  const revisePayload = reviseRequest.postDataJSON() as Record<string, unknown>;
  const revision = revisePayload.revision as Record<string, unknown>;

  expect(Array.isArray(revision.nodes)).toBe(true);
  expect(Array.isArray(revision.edges)).toBe(true);
  await expect(page).toHaveURL(
    /\/pools\/topology-templates\?template=template-top-down&detail=1$/,
  );
  await expect(
    page.getByTestId("pool-topology-templates-selected-code"),
  ).toHaveText("top-down-template");
  await expect(page.getByText("Updated Root")).toBeVisible();
  await expect(
    page
      .locator(
        'table:has(th:has-text("Created at")) tbody tr:not(.ant-table-measure-row)',
      )
      .first(),
  ).toContainText("r4");
  await expectNoHorizontalOverflow(page);
  await expectNoScopedHorizontalOverflow(
    page.getByTestId("pool-topology-templates-detail-surface"),
    "Topology template detail surface",
  );
});

test("UI platform: /pools/catalog restores attachment workspace in a mobile-safe drawer", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page);
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto(
    `/pools/catalog?pool_id=${POOL_WITH_ATTACHMENT.id}&tab=bindings`,
    {
      waitUntil: "domcontentloaded",
    },
  );

  await expect(
    page.getByRole("heading", { name: "Pool Catalog", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(page.getByTestId("pool-catalog-context-pool")).toHaveText(
    "pool-main - Main Pool",
  );
  const detailDrawer = page.getByTestId("pool-catalog-bindings-drawer");
  await expect(detailDrawer).toBeVisible();
  await expect(
    detailDrawer.getByTestId("pool-catalog-save-bindings"),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
});

test("UI platform: /databases restores selected database and management context from a deep-link", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true });

  await page.goto(
    `/databases?cluster=cluster-1&database=${DATABASE_ID}&context=metadata`,
    {
      waitUntil: "domcontentloaded",
    },
  );

  await expect(
    page.getByRole("heading", { name: "Databases", level: 2 }),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(
    page.getByRole("combobox", { name: "Cluster filter" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", {
      name: `Open database ${DATABASE_RECORD.name}`,
    }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("database-workspace-selected-id")).toHaveText(
    DATABASE_ID,
    {
      timeout: ROUTE_MOUNT_TIMEOUT_MS,
    },
  );
  await expect(
    page.getByTestId("database-metadata-management-drawer"),
  ).toBeVisible();
  await expect(page).toHaveURL(
    new RegExp(
      `\\/databases\\?cluster=cluster-1&database=${DATABASE_ID}&context=metadata$`,
    ),
  );
  await expectNoHorizontalOverflow(page);
});

test("UI platform: /databases keeps selected management context on browser back and forward", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true });

  await page.goto(`/databases?database=${DATABASE_ID}&context=inspect`, {
    waitUntil: "domcontentloaded",
  });

  await expect(page.getByTestId("database-workspace-selected-id")).toHaveText(
    DATABASE_ID,
    {
      timeout: ROUTE_MOUNT_TIMEOUT_MS,
    },
  );

  await page.getByTestId("database-workspace-open-credentials").click();
  await expect(page).toHaveURL(
    new RegExp(`\\/databases\\?database=${DATABASE_ID}&context=credentials$`),
  );
  await expect(
    page.getByText(`Credentials: ${DATABASE_RECORD.name}`),
  ).toBeVisible();

  await page.goBack();
  await expect(page).toHaveURL(
    new RegExp(`\\/databases\\?database=${DATABASE_ID}&context=inspect$`),
  );
  await expect(
    page.getByText(`Database Workspace: ${DATABASE_RECORD.name}`),
  ).toBeVisible();

  await page.goForward();
  await expect(page).toHaveURL(
    new RegExp(`\\/databases\\?database=${DATABASE_ID}&context=credentials$`),
  );
  await expect(
    page.getByText(`Credentials: ${DATABASE_RECORD.name}`),
  ).toBeVisible();
});

test("UI platform: /databases opens mobile management context without stacked overlays", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true });
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto(`/databases?database=${DATABASE_ID}&context=metadata`, {
    waitUntil: "domcontentloaded",
  });

  const metadataDrawer = page.getByTestId(
    "database-metadata-management-drawer",
  );
  await expect(metadataDrawer).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(page.locator(".ant-drawer-content-wrapper:visible")).toHaveCount(
    1,
  );
  await expectNoHorizontalOverflow(page);
  await expectNoScopedHorizontalOverflow(
    metadataDrawer,
    "Database metadata management drawer",
  );
});

test("UI platform: /pools/runs restores selected run and stage from a deep-link", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page);

  await page.goto(
    `/pools/runs?pool=${POOL_WITH_ATTACHMENT.id}&run=${POOL_RUN.id}&stage=inspect&detail=1`,
    {
      waitUntil: "domcontentloaded",
    },
  );

  await expect(
    page.getByRole("heading", { name: "Pool Runs", level: 2 }),
  ).toBeVisible();
  await expect(page.getByRole("tab", { name: "Inspect" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page.getByTestId("pool-runs-lineage-pool")).toHaveText(
    "pool-main - Main Pool",
  );
  await expect(page.getByTestId("pool-runs-lineage-binding-id")).toHaveText(
    "binding-top-down",
  );
  await expect(
    page.getByTestId("pool-runs-lineage-slot-coverage"),
  ).toContainText("resolved: 1");
  await expect(
    page.getByRole("button", { name: "Open Workflow Diagnostics" }),
  ).toBeVisible();
});

test("UI platform: /pools/runs keeps selected stage on browser back and forward", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page);

  await page.goto(
    `/pools/runs?pool=${POOL_WITH_ATTACHMENT.id}&run=${POOL_RUN.id}&stage=inspect&detail=1`,
    {
      waitUntil: "domcontentloaded",
    },
  );

  await expect(page.getByRole("tab", { name: "Inspect" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page.getByTestId("pool-runs-lineage-binding-id")).toHaveText(
    "binding-top-down",
    { timeout: 15000 },
  );

  await page.getByRole("tab", { name: "Retry Failed" }).click();
  await expect(page).toHaveURL(
    new RegExp(
      `\\/pools\\/runs\\?pool=${POOL_WITH_ATTACHMENT.id}&run=${POOL_RUN.id}&stage=retry&detail=1$`,
    ),
  );
  await expect(page.getByRole("tab", { name: "Retry Failed" })).toHaveAttribute(
    "aria-selected",
    "true",
  );

  await page.goBack();
  await expect(page).toHaveURL(
    new RegExp(
      `\\/pools\\/runs\\?pool=${POOL_WITH_ATTACHMENT.id}&run=${POOL_RUN.id}&stage=inspect&detail=1$`,
    ),
  );
  await expect(page.getByRole("tab", { name: "Inspect" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page.getByTestId("pool-runs-lineage-binding-id")).toHaveText(
    "binding-top-down",
  );

  await page.goForward();
  await expect(page).toHaveURL(
    new RegExp(
      `\\/pools\\/runs\\?pool=${POOL_WITH_ATTACHMENT.id}&run=${POOL_RUN.id}&stage=retry&detail=1$`,
    ),
  );
  await expect(page.getByRole("tab", { name: "Retry Failed" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
});

test("UI platform: /pools/runs opens inspect detail in a mobile-safe drawer without page-wide overflow", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page);
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto(
    `/pools/runs?pool=${POOL_WITH_ATTACHMENT.id}&run=${POOL_RUN.id}&stage=inspect&detail=1`,
    {
      waitUntil: "domcontentloaded",
    },
  );

  const detailDrawer = page.getByRole("dialog");
  await expect(detailDrawer).toBeVisible();
  await expect(detailDrawer.getByTestId("pool-runs-lineage-pool")).toHaveText(
    "pool-main - Main Pool",
  );
  await expect(
    detailDrawer.getByRole("button", { name: "Open Workflow Diagnostics" }),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
});

test("UI platform: /pools/factual restores compact selection and detail workspace from a deep-link", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page);

  await page.goto(
    `/pools/factual?pool=${POOL_WITH_ATTACHMENT.id}&run=${POOL_RUN.id}&quarter_start=2026-01-01&focus=settlement&detail=1`,
    {
      waitUntil: "domcontentloaded",
    },
  );

  await expect(
    page.getByRole("heading", { name: "Pool Factual Monitoring", level: 2 }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", {
      name: "Open factual workspace for Main Pool",
    }),
  ).toBeVisible();
  await expect(page.getByText("Factual operator workspace")).toBeVisible();
  const overallState = page.getByText("Overall state");
  const poolMovement = page.getByText("Pool movement");
  const runLinkedHandoff = page.getByText("Run-linked settlement handoff");
  const syncDiagnostics = page.getByText("Sync diagnostics");
  const executionControls = page.getByText(
    "Execution controls stay in Pool Runs",
  );

  await expect(overallState).toBeVisible();
  await expect(poolMovement).toBeVisible();
  await expect(runLinkedHandoff).toBeVisible();
  await expect(
    page.getByText("Manual review queue", { exact: true }).last(),
  ).toBeVisible();
  await expect(
    page.getByText(
      "Read backlog has 2 overdue checkpoint(s) on the default sync lane.",
    ),
  ).toBeVisible();
  await expect(page.getByText("focus=settlement")).toBeVisible();

  const [
    overallStateBox,
    poolMovementBox,
    runLinkedHandoffBox,
    syncDiagnosticsBox,
    executionControlsBox,
  ] = await Promise.all([
    overallState.boundingBox(),
    poolMovement.boundingBox(),
    runLinkedHandoff.boundingBox(),
    syncDiagnostics.boundingBox(),
    executionControls.boundingBox(),
  ]);

  if (
    !overallStateBox ||
    !poolMovementBox ||
    !runLinkedHandoffBox ||
    !syncDiagnosticsBox ||
    !executionControlsBox
  ) {
    throw new Error(
      "Expected factual workspace sections to have visible bounding boxes.",
    );
  }

  expect(overallStateBox.y).toBeLessThan(syncDiagnosticsBox.y);
  expect(overallStateBox.y).toBeLessThan(poolMovementBox.y);
  expect(poolMovementBox.y).toBeLessThan(syncDiagnosticsBox.y);
  expect(poolMovementBox.y).toBeLessThan(runLinkedHandoffBox.y);
  expect(runLinkedHandoffBox.y).toBeLessThan(syncDiagnosticsBox.y);
  expect(overallStateBox.y).toBeLessThan(executionControlsBox.y);

  await expectNoHorizontalOverflow(page);
});

test("UI platform: /pools/runs handoff to factual workspace preserves quarter_start", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page);

  await page.goto(
    `/pools/runs?pool=${POOL_WITH_ATTACHMENT.id}&run=${POOL_RUN.id}&stage=inspect&detail=1`,
    {
      waitUntil: "domcontentloaded",
    },
  );

  await expect(page.getByText("Run Lineage / Operator Report")).toBeVisible({
    timeout: 15000,
  });
  await expect(
    page.getByRole("button", { name: "Open factual workspace" }),
  ).toBeVisible({ timeout: 15000 });
  await page.getByRole("button", { name: "Open factual workspace" }).click();

  await expect(page).toHaveURL(
    new RegExp(
      `\\/pools\\/factual\\?pool=${POOL_WITH_ATTACHMENT.id}&run=${POOL_RUN.id}&quarter_start=2026-01-01&focus=settlement&detail=1$`,
    ),
  );
  await expect(
    page.getByRole("heading", { name: "Pool Factual Monitoring", level: 2 }),
  ).toBeVisible();
  await expect(page.getByText("Run-linked settlement handoff")).toBeVisible();
});

test("UI platform: /pools/factual opens review detail in a mobile-safe drawer without page-wide overflow", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page);
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto(
    `/pools/factual?pool=${POOL_WITH_ATTACHMENT.id}&run=${POOL_RUN.id}&focus=review&detail=1`,
    {
      waitUntil: "domcontentloaded",
    },
  );

  const detailDrawer = page
    .getByRole("dialog")
    .filter({ hasText: "Factual operator workspace" })
    .first();
  await expect(detailDrawer).toBeVisible();
  await expect(
    detailDrawer.getByText("Factual operator workspace"),
  ).toBeVisible();
  await expect(detailDrawer.getByText("Overall state")).toBeVisible();
  await expect(
    detailDrawer.getByText("Manual review queue", { exact: true }).last(),
  ).toBeVisible();
  await expect(detailDrawer.getByText("review focus")).toBeVisible();
  await expect(
    detailDrawer.getByRole("button", {
      name: "Attribute review item unattributed-pool-main",
    }),
  ).toBeVisible();
  await detailDrawer
    .getByRole("button", {
      name: "Attribute review item unattributed-pool-main",
    })
    .click();
  await expect(
    page.getByText("Choose or confirm attribution targets"),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
});

test("UI platform: /pools/factual keeps locale switch, reload, and review modal copy aligned with shell i18n", async ({
  page,
}) => {
  const observedLocaleHeaders: string[] = [];
  const localeSelect = page.getByTestId("shell-locale-select");

  await setupAuth(page, { localeOverride: "ru" });
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { observedLocaleHeaders });

  await page.goto(
    `/pools/factual?pool=${POOL_WITH_ATTACHMENT.id}&run=${POOL_RUN.id}&focus=review&detail=1`,
    {
      waitUntil: "domcontentloaded",
    },
  );

  await expect(localeSelect).toBeVisible({ timeout: ROUTE_MOUNT_TIMEOUT_MS });
  await expect(localeSelect).toHaveAttribute("aria-label", "Язык");
  await expect(
    page.getByRole("menuitem", { name: "Факты пулов" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "Фактический мониторинг пулов",
      level: 2,
    }),
  ).toBeVisible();
  await expect(page.getByText("Операторский factual workspace")).toBeVisible();
  await expect(
    page.getByText("Ручной review", { exact: true }).last(),
  ).toBeVisible();
  await expect(page.getByText("Фокус review", { exact: true })).toBeVisible();
  await expect.poll(() => observedLocaleHeaders[0]).toBe("ru");

  await page
    .getByRole("button", {
      name: "Атрибутировать review item unattributed-pool-main",
    })
    .click();
  const reviewDialogRu = page.getByRole("dialog");
  await expect(reviewDialogRu).toBeVisible();
  await expect(reviewDialogRu.locator(".ant-modal-title")).toContainText(
    "Подтвердить атрибуцию",
  );
  await expect(
    reviewDialogRu.getByRole("button", { name: "Подтвердить атрибуцию" }),
  ).toBeVisible();
  await reviewDialogRu.locator(".ant-modal-close").click();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  await switchShellLocaleToEnglish(page);

  await expect(localeSelect).toHaveAttribute("aria-label", "Language");
  await expect(
    page.getByRole("menuitem", { name: "Pool Factual" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Pool Factual Monitoring", level: 2 }),
  ).toBeVisible();
  await expect(page.getByText("Factual operator workspace")).toBeVisible();
  await expect(
    page.getByText("Manual review queue", { exact: true }).last(),
  ).toBeVisible();
  await expect(page.getByText("Focus review", { exact: true })).toBeVisible();
  await expect.poll(() => observedLocaleHeaders.at(-1)).toBe("en");

  await page
    .getByRole("button", {
      name: "Attribute review item unattributed-pool-main",
    })
    .click();
  const reviewDialogEn = page.getByRole("dialog");
  await expect(reviewDialogEn).toBeVisible();
  await expect(reviewDialogEn.locator(".ant-modal-title")).toContainText(
    "Confirm attribution",
  );
  await expect(
    reviewDialogEn.getByRole("button", { name: "Confirm attribution" }),
  ).toBeVisible();
  await reviewDialogEn.locator(".ant-modal-close").click();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  await page.reload({ waitUntil: "domcontentloaded" });

  await expect(localeSelect).toBeVisible({ timeout: ROUTE_MOUNT_TIMEOUT_MS });
  await expect(localeSelect).toHaveAttribute("aria-label", "Language");
  await expect(
    page.getByRole("menuitem", { name: "Pool Factual" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Pool Factual Monitoring", level: 2 }),
  ).toBeVisible();
  await expect(page.getByText("Factual operator workspace")).toBeVisible();
  await expect(
    page.getByText("Manual review queue", { exact: true }).last(),
  ).toBeVisible();
  await expect(page.getByText("Focus review", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", {
      name: "Attribute review item unattributed-pool-main",
    }),
  ).toBeVisible();
  await expect(page.getByText("Ручной review", { exact: true })).toHaveCount(0);
  await expect.poll(() => observedLocaleHeaders.at(-1)).toBe("en");
});

test("UI platform: /operations restores selected operation and inspect context from a deep-link", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true });

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
  await expect(
    page.getByRole("button", {
      name: "Open operation workflow root execute",
    }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(
    page.getByText(`Operation Details: ${WORKFLOW_OPERATION.name}`),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(page.getByRole("button", { name: "Timeline" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Open workflow diagnostics" }),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await expectNoScopedHorizontalOverflow(
    page.getByTestId("operation-inspect-surface"),
    "Operation inspect surface",
  );
});

test("UI platform: /operations keeps selected operation view on browser back and forward", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true });

  await page.goto(
    `/operations?operation=${WORKFLOW_OPERATION.id}&tab=inspect`,
    {
      waitUntil: "domcontentloaded",
    },
  );

  await expect(
    page.getByText(`Operation Details: ${WORKFLOW_OPERATION.name}`),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });

  await page.getByRole("button", { name: "Timeline" }).click();
  await expect(page).toHaveURL(
    new RegExp(
      `\\/operations\\?operation=${WORKFLOW_OPERATION.id}&tab=monitor$`,
    ),
  );

  await page.goBack();
  await expect(page).toHaveURL(
    new RegExp(
      `\\/operations\\?operation=${WORKFLOW_OPERATION.id}&tab=inspect$`,
    ),
  );
  await expect(
    page.getByText(`Operation Details: ${WORKFLOW_OPERATION.name}`),
  ).toBeVisible();

  await page.goForward();
  await expect(page).toHaveURL(
    new RegExp(
      `\\/operations\\?operation=${WORKFLOW_OPERATION.id}&tab=monitor$`,
    ),
  );
});

test("UI platform: /operations opens inspect detail in a mobile-safe drawer without page-wide overflow", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true });
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto(
    `/operations?operation=${WORKFLOW_OPERATION.id}&tab=inspect`,
    {
      waitUntil: "domcontentloaded",
    },
  );

  await expect(
    page.getByText(`Operation Details: ${WORKFLOW_OPERATION.name}`),
  ).toBeVisible({ timeout: 15000 });
  const detailDrawer = page.getByRole("dialog");
  await expect(detailDrawer).toBeVisible();
  await expect(page.locator(".ant-drawer-content-wrapper:visible")).toHaveCount(
    1,
  );
  await expect(
    detailDrawer.getByText(`Operation Details: ${WORKFLOW_OPERATION.name}`),
  ).toBeVisible();
  await expect(
    detailDrawer.getByRole("button", { name: "Timeline" }),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await expectNoScopedHorizontalOverflow(
    page.getByTestId("operation-inspect-surface"),
    "Operation inspect drawer surface",
  );
});

test("UI platform: /operations renders zero-task diagnostics as empty state instead of completed workload", async ({
  page,
}) => {
  await setupAuth(page);
  await setupPersistentDatabaseStream(page);
  await setupUiPlatformMocks(page, { isStaff: true });

  await page.goto(
    `/operations?operation=${ZERO_TASK_OPERATION.id}&tab=inspect`,
    {
      waitUntil: "domcontentloaded",
    },
  );

  await expect(
    page.getByText(`Operation Details: ${ZERO_TASK_OPERATION.name}`),
  ).toBeVisible({
    timeout: ROUTE_MOUNT_TIMEOUT_MS,
  });
  await expect(
    page.getByTestId("operation-inspect-no-task-telemetry"),
  ).toBeVisible();
  await expect(
    page.getByText(
      "Task list will appear when runtime reports a task workset for this operation.",
    ),
  ).toBeVisible();
  await expect(page.locator(".ant-progress")).toHaveCount(0);
  await expectNoHorizontalOverflow(page);
});

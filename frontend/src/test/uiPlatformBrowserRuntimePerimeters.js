export const UI_PLATFORM_BROWSER_CONTRACT_SHARDS = Object.freeze([
  Object.freeze({
    family: "workspaces",
    label: "workspace restore, mobile detail, and authoring surfaces",
    path: "tests/browser/ui-platform-contract-workspaces.spec.ts",
  }),
  Object.freeze({
    family: "runtime-surfaces",
    label: "runtime-facing clusters, system-status, and service-mesh surfaces",
    path: "tests/browser/ui-platform-contract-runtime-surfaces.spec.ts",
  }),
  Object.freeze({
    family: "governance-settings",
    label: "governance, catalog outliers, and settings detail surfaces",
    path: "tests/browser/ui-platform-contract-governance-settings.spec.ts",
  }),
  Object.freeze({
    family: "shell-contracts",
    label:
      "mount budgets, handoffs, same-route re-entry, and shell-level runtime contracts",
    path: "tests/browser/ui-platform-contract-shell-contracts.spec.ts",
  }),
]);

export const UI_PLATFORM_BROWSER_CONTRACT_FAMILIES = Object.freeze(
  UI_PLATFORM_BROWSER_CONTRACT_SHARDS.map((shard) => shard.family),
);

export const UI_PLATFORM_BROWSER_CONTRACT_FILES = Object.freeze(
  UI_PLATFORM_BROWSER_CONTRACT_SHARDS.map((shard) => shard.path),
);

export const UI_PLATFORM_BROWSER_CONTRACT_FAMILY_FILES = Object.freeze(
  Object.fromEntries(
    UI_PLATFORM_BROWSER_CONTRACT_SHARDS.map((shard) => [
      shard.family,
      shard.path,
    ]),
  ),
);

export const UI_PLATFORM_BROWSER_CONTRACT_RUNNER =
  "node ./scripts/run-ui-platform-browser-suite.mjs";
export const UI_VALIDATION_MEASUREMENT_DEFAULT_SAMPLES = 3;
export const UI_VALIDATION_ARTIFACT_DIR =
  "docs/observability/artifacts/ui-validation-runtime";
export const UI_VALIDATION_VITEST_COMMAND = "npm run test:run";
export const UI_VALIDATION_BROWSER_COMMAND = "npm run test:browser:ui-platform";

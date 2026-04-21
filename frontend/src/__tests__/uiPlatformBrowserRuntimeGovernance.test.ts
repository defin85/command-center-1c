import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  UI_PLATFORM_BROWSER_CONTRACT_FAMILIES,
  UI_PLATFORM_BROWSER_CONTRACT_FILES,
  UI_PLATFORM_BROWSER_CONTRACT_RUNNER,
  UI_PLATFORM_BROWSER_CONTRACT_SHARDS,
  UI_VALIDATION_ARTIFACT_DIR,
  UI_VALIDATION_BROWSER_COMMAND,
  UI_VALIDATION_MEASUREMENT_DEFAULT_SAMPLES,
  UI_VALIDATION_VITEST_COMMAND,
} from "../test/uiPlatformBrowserRuntimePerimeters.js";

type PackageJson = {
  scripts: Record<string, string>;
};

const readJson = async <T>(relativePath: string): Promise<T> => {
  const file = await readFile(
    new URL(relativePath, import.meta.url).pathname,
    "utf8",
  );
  return JSON.parse(file) as T;
};

const readText = async (relativePath: string): Promise<string> =>
  readFile(new URL(relativePath, import.meta.url).pathname, "utf8");

describe("ui-platform browser runtime governance", () => {
  it("keeps the browser shard inventory explicit and unique", async () => {
    const browserDirPath = path.resolve(process.cwd(), "tests/browser");
    const actualFiles = (await readdir(browserDirPath))
      .filter(
        (fileName) =>
          fileName.startsWith("ui-platform-contract-") &&
          fileName.endsWith(".spec.ts"),
      )
      .map((fileName) => `tests/browser/${fileName}`)
      .sort();

    expect(new Set(UI_PLATFORM_BROWSER_CONTRACT_FAMILIES).size).toBe(
      UI_PLATFORM_BROWSER_CONTRACT_FAMILIES.length,
    );
    expect(new Set(UI_PLATFORM_BROWSER_CONTRACT_FILES).size).toBe(
      UI_PLATFORM_BROWSER_CONTRACT_FILES.length,
    );
    expect([...UI_PLATFORM_BROWSER_CONTRACT_FILES].sort()).toEqual(actualFiles);
    expect(
      UI_PLATFORM_BROWSER_CONTRACT_SHARDS.map((shard) => shard.path),
    ).toEqual(UI_PLATFORM_BROWSER_CONTRACT_FILES);
  });

  it("keeps browser scripts and measurement scripts aligned to repo-owned runtime surfaces", async () => {
    const packageJson = await readJson<PackageJson>("../../package.json");

    expect(packageJson.scripts["test:browser:ui-platform"]).toBe(
      UI_PLATFORM_BROWSER_CONTRACT_RUNNER,
    );

    for (const shard of UI_PLATFORM_BROWSER_CONTRACT_SHARDS) {
      expect(
        packageJson.scripts[`test:browser:ui-platform:${shard.family}`],
      ).toBe(`${UI_PLATFORM_BROWSER_CONTRACT_RUNNER} ${shard.family}`);
    }

    expect(packageJson.scripts["measure:ui-validation"]).toBe(
      `node ./scripts/measure-ui-validation-runtime.mjs --surface all --samples ${UI_VALIDATION_MEASUREMENT_DEFAULT_SAMPLES}`,
    );
    expect(packageJson.scripts["measure:ui-validation:vitest"]).toBe(
      `node ./scripts/measure-ui-validation-runtime.mjs --surface vitest --samples ${UI_VALIDATION_MEASUREMENT_DEFAULT_SAMPLES}`,
    );
    expect(packageJson.scripts["measure:ui-validation:browser"]).toBe(
      `node ./scripts/measure-ui-validation-runtime.mjs --surface browser --samples ${UI_VALIDATION_MEASUREMENT_DEFAULT_SAMPLES}`,
    );
    expect(packageJson.scripts["validate:ui-platform"]).toBe(
      "npm run generate:api && npm run lint && npm run test:run && npm run test:browser:ui-platform && npm run build:assets",
    );
  });

  it("keeps docs aligned with focused browser reruns and repeated measurement protocol", async () => {
    const verify = await readText("../../../docs/agent/VERIFY.md");
    const frontendAgents = await readText("../../../frontend/AGENTS.md");
    const runbook = await readText(
      "../../../docs/deployment/frontend-ui-platform-validation-runbook.md",
    );
    const artifactReadme = await readText(
      "../../../docs/observability/artifacts/ui-validation-runtime/README.md",
    );

    expect(verify).toContain(
      "cd frontend && npm run test:browser:ui-platform:workspaces",
    );
    expect(verify).toContain(
      "cd frontend && npm run test:browser:ui-platform:runtime-surfaces",
    );
    expect(verify).toContain(
      "cd frontend && npm run test:browser:ui-platform:governance-settings",
    );
    expect(verify).toContain(
      "cd frontend && npm run test:browser:ui-platform:shell-contracts",
    );
    expect(verify).toContain(
      `cd frontend && npm run measure:ui-validation -- --artifact ../${UI_VALIDATION_ARTIFACT_DIR}/<run-id>.json`,
    );
    expect(verify).toContain(UI_VALIDATION_BROWSER_COMMAND);
    expect(verify).toContain(UI_VALIDATION_VITEST_COMMAND);

    expect(frontendAgents).toContain(
      "focused browser reruns are wired through checked-in shard families",
    );
    expect(frontendAgents).toContain(
      `cd frontend && npm run measure:ui-validation -- --artifact ../${UI_VALIDATION_ARTIFACT_DIR}/<run-id>.json`,
    );

    expect(runbook).toContain(
      "cd frontend && npm run test:browser:ui-platform:workspaces",
    );
    expect(runbook).toContain(
      "cd frontend && npm run test:browser:ui-platform:runtime-surfaces",
    );
    expect(runbook).toContain(
      "cd frontend && npm run test:browser:ui-platform:governance-settings",
    );
    expect(runbook).toContain(
      "cd frontend && npm run test:browser:ui-platform:shell-contracts",
    );
    expect(runbook).toContain(
      `cd frontend && npm run measure:ui-validation -- --artifact ../${UI_VALIDATION_ARTIFACT_DIR}/<run-id>.json`,
    );
    expect(runbook).toContain("Keep the default `3` samples");

    expect(artifactReadme).toContain("738.50s total");
    expect(artifactReadme).toContain("337.31s total");
    expect(artifactReadme).toContain("461.49s");
    expect(artifactReadme).toContain("6414");
    expect(artifactReadme).toContain(UI_VALIDATION_ARTIFACT_DIR);
  });
});

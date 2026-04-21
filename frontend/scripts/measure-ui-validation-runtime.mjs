import { mkdirSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import {
  UI_PLATFORM_BROWSER_CONTRACT_SHARDS,
  UI_VALIDATION_ARTIFACT_DIR,
  UI_VALIDATION_BROWSER_COMMAND,
  UI_VALIDATION_MEASUREMENT_DEFAULT_SAMPLES,
  UI_VALIDATION_VITEST_COMMAND,
} from "../src/test/uiPlatformBrowserRuntimePerimeters.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendDir = path.resolve(__dirname, "..");
const repoRoot = path.resolve(frontendDir, "..");

function stripAnsi(text) {
  return text.replace(/\u001B\[[0-9;]*m/g, "");
}

function parseDurationSeconds(raw) {
  const match = raw.trim().match(/^([0-9]+(?:\.[0-9]+)?)(ms|s|m|h)$/);
  if (!match) {
    return null;
  }

  const value = Number(match[1]);
  const unit = match[2];

  if (unit === "ms") {
    return value / 1000;
  }
  if (unit === "s") {
    return value;
  }
  if (unit === "m") {
    return value * 60;
  }
  if (unit === "h") {
    return value * 3600;
  }

  return null;
}

function toSummaryStats(values) {
  if (values.length === 0) {
    return null;
  }

  const sorted = [...values].sort((left, right) => left - right);
  const middle = Math.floor(sorted.length / 2);
  const median =
    sorted.length % 2 === 0
      ? (sorted[middle - 1] + sorted[middle]) / 2
      : sorted[middle];

  return {
    min: sorted[0],
    median,
    max: sorted[sorted.length - 1],
  };
}

function parseVitestSummary(output) {
  const cleanOutput = stripAnsi(output);
  const testFiles = cleanOutput.match(/Test Files\s+(\d+)\s+passed/);
  const tests = cleanOutput.match(/Tests\s+(\d+)\s+passed/);
  const duration = cleanOutput.match(/Duration\s+([0-9.]+s)\s+\(([^)]+)\)/);
  const breakdown = {};

  if (duration) {
    for (const part of duration[2].split(",")) {
      const trimmed = part.trim();
      const breakdownMatch = trimmed.match(
        /^([a-zA-Z]+)\s+([0-9.]+(?:ms|s|m|h))$/,
      );
      if (!breakdownMatch) {
        continue;
      }
      breakdown[breakdownMatch[1]] = {
        raw: breakdownMatch[2],
        seconds: parseDurationSeconds(breakdownMatch[2]),
      };
    }
  }

  return {
    test_files: testFiles ? Number(testFiles[1]) : null,
    tests: tests ? Number(tests[1]) : null,
    duration: duration
      ? {
          raw: duration[1],
          seconds: parseDurationSeconds(duration[1]),
          breakdown,
        }
      : null,
  };
}

function parsePlaywrightSummary(output) {
  const cleanOutput = stripAnsi(output);
  const matches = [...cleanOutput.matchAll(/(\d+)\s+passed\s+\(([^)]+)\)/g)];
  const summary = matches.at(-1);

  return {
    tests: summary ? Number(summary[1]) : null,
    duration: summary
      ? {
          raw: summary[2],
          seconds: parseDurationSeconds(summary[2]),
        }
      : null,
  };
}

async function runShellCommand(command) {
  return await new Promise((resolve, reject) => {
    const runner = process.platform === "win32" ? "cmd.exe" : "bash";
    const runnerArgs =
      process.platform === "win32"
        ? ["/d", "/s", "/c", command]
        : ["-lc", command];
    const child = spawn(runner, runnerArgs, {
      cwd: frontendDir,
      stdio: ["ignore", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";
    const startedAt = process.hrtime.bigint();

    child.stdout.on("data", (chunk) => {
      const text = chunk.toString();
      stdout += text;
      process.stdout.write(text);
    });

    child.stderr.on("data", (chunk) => {
      const text = chunk.toString();
      stderr += text;
      process.stderr.write(text);
    });

    child.on("error", reject);
    child.on("close", (code) => {
      const finishedAt = process.hrtime.bigint();
      const wallClockSeconds = Number(finishedAt - startedAt) / 1_000_000_000;

      resolve({
        code: code ?? 1,
        stdout,
        stderr,
        wall_clock_seconds: wallClockSeconds,
      });
    });
  });
}

async function measureSurface(surface, samples) {
  const command =
    surface === "vitest"
      ? UI_VALIDATION_VITEST_COMMAND
      : UI_VALIDATION_BROWSER_COMMAND;
  const parser =
    surface === "vitest" ? parseVitestSummary : parsePlaywrightSummary;
  const entries = [];

  for (let index = 0; index < samples; index += 1) {
    console.log(
      `\n=== ${surface} sample ${index + 1}/${samples}: ${command} ===`,
    );
    const result = await runShellCommand(command);
    if (result.code !== 0) {
      throw new Error(
        `${command} failed on sample ${index + 1} with exit code ${result.code}`,
      );
    }

    entries.push({
      sample: index + 1,
      command,
      wall_clock_seconds: Number(result.wall_clock_seconds.toFixed(2)),
      parsed: parser(`${result.stdout}\n${result.stderr}`),
    });
  }

  const wallClockSummary = toSummaryStats(
    entries.map((entry) => entry.wall_clock_seconds),
  );
  const reportedDurationValues = entries
    .map((entry) => entry.parsed.duration?.seconds)
    .filter((value) => typeof value === "number");
  const reportedDurationSummary = toSummaryStats(reportedDurationValues);

  const componentNames = new Set(
    entries.flatMap((entry) =>
      Object.keys(entry.parsed.duration?.breakdown ?? {}),
    ),
  );

  const breakdownSummary = Object.fromEntries(
    [...componentNames].map((name) => {
      const values = entries
        .map((entry) => entry.parsed.duration?.breakdown?.[name]?.seconds)
        .filter((value) => typeof value === "number");

      return [name, toSummaryStats(values)];
    }),
  );

  return {
    command,
    samples: entries,
    summary: {
      wall_clock_seconds: wallClockSummary,
      reported_duration_seconds: reportedDurationSummary,
      reported_breakdown_seconds: breakdownSummary,
    },
  };
}

function parseArguments(argv) {
  const options = {
    surface: "all",
    samples: UI_VALIDATION_MEASUREMENT_DEFAULT_SAMPLES,
    artifact: null,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--surface") {
      options.surface = argv[index + 1] ?? options.surface;
      index += 1;
      continue;
    }
    if (arg === "--samples") {
      options.samples = Number(argv[index + 1] ?? options.samples);
      index += 1;
      continue;
    }
    if (arg === "--artifact") {
      options.artifact = argv[index + 1] ?? null;
      index += 1;
    }
  }

  return options;
}

const options = parseArguments(process.argv.slice(2));
if (!["all", "vitest", "browser"].includes(options.surface)) {
  console.error(
    `Unsupported surface "${options.surface}". Expected all, vitest, or browser.`,
  );
  process.exit(1);
}
if (!Number.isInteger(options.samples) || options.samples <= 0) {
  console.error(
    `Unsupported sample count "${options.samples}". Expected a positive integer.`,
  );
  process.exit(1);
}

const surfaces =
  options.surface === "all" ? ["vitest", "browser"] : [options.surface];
const surfaceResults = {};

for (const surface of surfaces) {
  surfaceResults[surface] = await measureSurface(surface, options.samples);
}

const payload = {
  recorded_at: new Date().toISOString(),
  measurement_protocol: {
    default_samples: UI_VALIDATION_MEASUREMENT_DEFAULT_SAMPLES,
    requested_samples: options.samples,
    artifact_directory: UI_VALIDATION_ARTIFACT_DIR,
    surfaces,
    browser_shards: UI_PLATFORM_BROWSER_CONTRACT_SHARDS,
  },
  environment: {
    repo_root: repoRoot,
    frontend_root: frontendDir,
    platform: process.platform,
    release: os.release(),
    cpus: os.cpus().length,
    node: process.version,
  },
  surfaces: surfaceResults,
};

if (options.artifact) {
  const artifactPath = path.isAbsolute(options.artifact)
    ? options.artifact
    : path.resolve(process.cwd(), options.artifact);
  mkdirSync(path.dirname(artifactPath), { recursive: true });
  writeFileSync(artifactPath, `${JSON.stringify(payload, null, 2)}\n`);
}

console.log("\n=== ui-validation-runtime summary ===");
console.log(JSON.stringify(payload, null, 2));

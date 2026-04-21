import { existsSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import {
  UI_PLATFORM_BROWSER_CONTRACT_FAMILIES,
  UI_PLATFORM_BROWSER_CONTRACT_SHARDS,
} from "../src/test/uiPlatformBrowserRuntimePerimeters.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendDir = path.resolve(__dirname, "..");

const args = process.argv.slice(2);
const passthroughIndex = args.indexOf("--");
const directArgs =
  passthroughIndex === -1 ? args : args.slice(0, passthroughIndex);
const passthroughArgs =
  passthroughIndex === -1 ? [] : args.slice(passthroughIndex + 1);
const requestedFamily = directArgs.find((arg) => !arg.startsWith("-")) ?? null;
const listFamilies = directArgs.includes("--list-families");

const duplicateFamilies = UI_PLATFORM_BROWSER_CONTRACT_FAMILIES.filter(
  (family, index, allFamilies) => allFamilies.indexOf(family) !== index,
);
if (duplicateFamilies.length > 0) {
  console.error(
    `Duplicate UI-platform browser families: ${duplicateFamilies.join(", ")}`,
  );
  process.exit(1);
}

const duplicatePaths = UI_PLATFORM_BROWSER_CONTRACT_SHARDS.map(
  (shard) => shard.path,
).filter((filePath, index, allPaths) => allPaths.indexOf(filePath) !== index);
if (duplicatePaths.length > 0) {
  console.error(
    `Duplicate UI-platform browser shard paths: ${duplicatePaths.join(", ")}`,
  );
  process.exit(1);
}

if (listFamilies) {
  for (const shard of UI_PLATFORM_BROWSER_CONTRACT_SHARDS) {
    console.log(`${shard.family}\t${shard.path}\t${shard.label}`);
  }
  process.exit(0);
}

const selectedShards = requestedFamily
  ? UI_PLATFORM_BROWSER_CONTRACT_SHARDS.filter(
      (shard) => shard.family === requestedFamily,
    )
  : UI_PLATFORM_BROWSER_CONTRACT_SHARDS;

if (requestedFamily && selectedShards.length === 0) {
  console.error(
    `Unknown UI-platform browser family "${requestedFamily}". Expected one of: ${UI_PLATFORM_BROWSER_CONTRACT_FAMILIES.join(", ")}`,
  );
  process.exit(1);
}

for (const shard of selectedShards) {
  const absolutePath = path.resolve(frontendDir, shard.path);
  if (!existsSync(absolutePath)) {
    console.error(`Missing UI-platform browser shard file: ${shard.path}`);
    process.exit(1);
  }
}

const command = process.platform === "win32" ? "npx.cmd" : "npx";
const commandArgs = [
  "playwright",
  "test",
  ...selectedShards.map((shard) => shard.path),
  "--workers=1",
  ...passthroughArgs,
];

const child = spawn(command, commandArgs, {
  cwd: frontendDir,
  stdio: "inherit",
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});

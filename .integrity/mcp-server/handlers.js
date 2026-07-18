// @ts-check
/**
 * Per-tool handler bodies for the MAI integrity MCP server.
 *
 * Each `handle*` function takes the tool `args` object and returns the
 * MCP `{ content: [...] }` envelope. server.js dispatches by name.
 */
import { execSync } from "node:child_process";
import {
  readFileSync,
  writeFileSync,
  mkdirSync,
  copyFileSync,
  statSync,
} from "node:fs";
import { dirname } from "node:path";
import { tmpdir } from "node:os";
import { randomUUID } from "node:crypto";

import { checkNullBytes, checkLineCount, validateFile } from "./validators.js";
import { log } from "./logger.js";

function text(obj, pretty = false) {
  return {
    content: [
      { type: "text", text: pretty ? JSON.stringify(obj, null, 2) : JSON.stringify(obj) },
    ],
  };
}

export function handleValidateFile(args) {
  const results = validateFile(args.path, args.expected_lines, args.expected_tail);
  const failed = results.filter((r) => !r.pass);
  const status = failed.length > 0 ? "FAIL" : "PASS";
  return text({ status, file: args.path, checks: results }, true);
}

export function handleSafeWrite(args) {
  const tmpPath = `${tmpdir()}/mai-safe-write-${Date.now()}-${randomUUID()}`;
  let content = args.content;
  if (!content.endsWith("\n")) content += "\n";

  writeFileSync(tmpPath, content, "utf-8");

  const tmpCheck = checkNullBytes(tmpPath);
  if (!tmpCheck.pass) {
    log.warn("safe_write tmp verification failed", { tmpPath });
    return text({ status: "FAIL", reason: "Null bytes in temp write" });
  }

  const actualLines = content.split("\n").length - 1;
  if (args.expected_lines && Math.abs(actualLines - args.expected_lines) > 2) {
    return text({
      status: "FAIL",
      reason: `Line count mismatch: expected ${args.expected_lines}, content has ${actualLines}`,
    });
  }

  mkdirSync(dirname(args.path), { recursive: true });
  copyFileSync(tmpPath, args.path);

  const targetCheck = checkNullBytes(args.path);
  const targetStat = statSync(args.path);
  const tmpStat = statSync(tmpPath);

  if (!targetCheck.pass || targetStat.size !== tmpStat.size) {
    log.error("safe_write target verification failed", {
      path: args.path,
      expected_bytes: tmpStat.size,
      actual_bytes: targetStat.size,
    });
    return text({
      status: "FAIL",
      reason: "Target verification failed after copy",
      expected_bytes: tmpStat.size,
      actual_bytes: targetStat.size,
    });
  }

  return text({
    status: "PASS",
    file: args.path,
    lines: actualLines,
    bytes: targetStat.size,
  });
}

export function handleVerifyBatch(args) {
  // Build the result array inside the loop, stringify ONCE after the loop.
  const results = [];
  for (const f of args.files) {
    results.push({
      file: f.path,
      checks: validateFile(f.path, f.expected_lines),
    });
  }
  const allPassed = results.every((r) => r.checks.every((c) => c.pass));
  return text({ status: allPassed ? "ALL_PASS" : "HAS_FAILURES", results }, true);
}

export function handleLineCountGuard(args) {
  const tolerance = args.tolerance || 2;
  const result = checkLineCount(args.path, args.expected, tolerance);
  return text({ status: result.pass ? "PASS" : "FAIL", ...result, file: args.path });
}

export function handlePreStageCheck(args) {
  try {
    const output = execSync(
      `cd "${args.repo_path}" && bash .integrity/scripts/verify-tree.sh 2>&1`,
      { encoding: "utf-8", timeout: 30000 },
    );
    const failed = output.includes("INTEGRITY CHECK FAILED");
    return text({ status: failed ? "FAIL" : "PASS", output });
  } catch (e) {
    log.error("pre_stage_check failed", { error: e.message });
    return text({ status: "FAIL", error: e.message, output: e.stdout || "" });
  }
}

export const handlers = {
  validate_file: handleValidateFile,
  safe_write: handleSafeWrite,
  verify_batch: handleVerifyBatch,
  line_count_guard: handleLineCountGuard,
  pre_stage_check: handlePreStageCheck,
};

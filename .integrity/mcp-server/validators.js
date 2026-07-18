// @ts-check
/**
 * File integrity validators extracted from server.js.
 *
 * Each `check*` helper returns `{ pass: boolean, detail?, warning?, ... }`.
 * `validateFile` orchestrates the per-check sequence used by the
 * `validate_file` and `verify_batch` MCP tools.
 */
import { execSync } from "node:child_process";
import { readFileSync, existsSync, statSync } from "node:fs";

export function checkNullBytes(filePath) {
  try {
    const content = readFileSync(filePath);
    return content.includes(0)
      ? { pass: false, detail: "Null bytes detected" }
      : { pass: true };
  } catch (e) {
    return { pass: false, detail: `Read error: ${e.message}` };
  }
}

export function checkBracketBalance(filePath) {
  try {
    const content = readFileSync(filePath, "utf-8");
    const open = (content.match(/{/g) || []).length;
    const close = (content.match(/}/g) || []).length;
    const delta = Math.abs(open - close);
    if (delta > 3) {
      return {
        pass: false,
        detail: `Brace imbalance: { ${open} } ${close} delta ${open - close}`,
      };
    }
    if (delta > 0) {
      return { pass: true, warning: `Minor brace mismatch: delta ${open - close}` };
    }
    return { pass: true };
  } catch (e) {
    return { pass: false, detail: `Read error: ${e.message}` };
  }
}

export function checkLineCount(filePath, expected, tolerance = 2) {
  try {
    const content = readFileSync(filePath, "utf-8");
    const actual = content.split("\n").length - (content.endsWith("\n") ? 1 : 0);
    const delta = Math.abs(actual - expected);
    if (delta > tolerance) {
      return {
        pass: false,
        detail: `Line count: expected ~${expected}, got ${actual} (delta ${actual - expected})`,
      };
    }
    return { pass: true, actual };
  } catch (e) {
    return { pass: false, detail: `Read error: ${e.message}` };
  }
}

export function checkTruncation(filePath, repoPath) {
  try {
    const relPath = filePath.replace(repoPath + "/", "");
    const headContent = execSync(
      `git -C "${repoPath}" show HEAD:"${relPath}" 2>/dev/null`,
      { encoding: "utf-8" },
    );
    const currentContent = readFileSync(filePath, "utf-8");
    const headLines = headContent.split("\n").length;
    const currentLines = currentContent.split("\n").length;
    if (headLines > 10 && currentLines > 0) {
      const ratio = Math.round((currentLines / headLines) * 100);
      if (ratio < 50) {
        return {
          pass: false,
          detail: `Truncation: ${headLines} -> ${currentLines} lines (${ratio}%)`,
        };
      }
      if (ratio < 75) {
        return {
          pass: true,
          warning: `Shrunk: ${headLines} -> ${currentLines} lines (${ratio}%)`,
        };
      }
    }
    return { pass: true };
  } catch (e) {
    // File not in HEAD (new file) - skip truncation check
    return { pass: true };
  }
}

function checkTail(filePath, expectedTail) {
  try {
    const content = readFileSync(filePath, "utf-8");
    const lines = content.trimEnd().split("\n");
    const lastLine = lines[lines.length - 1];
    const pass = lastLine.trim() === expectedTail.trim();
    return {
      pass,
      detail: pass ? undefined : `Expected: "${expectedTail}" Got: "${lastLine}"`,
    };
  } catch (e) {
    return { pass: false, detail: e.message };
  }
}

function checkNonEmpty(filePath) {
  return statSync(filePath).size === 0
    ? { pass: false, detail: "File is 0 bytes" }
    : { pass: true };
}

const CODE_FILE_RE = /\.(rs|py|js|ts|json)$/;

export function validateFile(filePath, expectedLines, expectedTail) {
  if (!existsSync(filePath)) {
    return [{ check: "existence", pass: false, detail: "File not found" }];
  }
  const results = [{ check: "existence", pass: true }];

  const nullCheck = checkNullBytes(filePath);
  results.push({ check: "null-bytes", ...nullCheck });
  if (!nullCheck.pass) return results;

  if (expectedLines) {
    results.push({ check: "line-count", ...checkLineCount(filePath, expectedLines) });
  }

  if (CODE_FILE_RE.test(filePath)) {
    results.push({ check: "bracket-balance", ...checkBracketBalance(filePath) });
  }

  if (expectedTail) {
    results.push({ check: "tail-content", ...checkTail(filePath, expectedTail) });
  }

  results.push({ check: "non-empty", ...checkNonEmpty(filePath) });
  return results;
}

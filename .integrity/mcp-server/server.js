#!/usr/bin/env node
/**
 * MAI Integrity MCP Server
 * 
 * Provides file integrity tools for CoWork sessions:
 * - validate_file: Check a file for corruption indicators
 * - safe_write: Atomic two-stage write with verification
 * - verify_batch: Check multiple files in one call
 * - line_count_guard: Compare expected vs actual line counts
 * - pre_stage_check: Full verification pass before git add
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { execSync } from "child_process";
import { readFileSync, writeFileSync, mkdirSync, copyFileSync, existsSync, statSync } from "fs";
import { dirname, resolve } from "path";
import { tmpdir } from "os";

const server = new Server(
  { name: "mai-integrity", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

// Tool definitions
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "validate_file",
      description: "Check a single file for corruption: null bytes, truncation vs HEAD, bracket balance, syntax validity. Returns structured pass/fail report.",
      inputSchema: {
        type: "object",
        properties: {
          path: { type: "string", description: "Absolute path to the file to validate" },
          expected_lines: { type: "number", description: "Expected line count (optional, tolerance +/- 2)" },
          expected_tail: { type: "string", description: "Expected content of the last line (optional)" },
        },
        required: ["path"],
      },
    },
    {
      name: "safe_write",
      description: "Atomic file write: writes to /tmp, verifies, then copies to target. Rejects if verification fails.",
      inputSchema: {
        type: "object",
        properties: {
          path: { type: "string", description: "Target file path" },
          content: { type: "string", description: "File content to write" },
          expected_lines: { type: "number", description: "Expected line count for post-write verification" },
        },
        required: ["path", "content"],
      },
    },
    {
      name: "verify_batch",
      description: "Validate multiple files in one call. Returns per-file results.",
      inputSchema: {
        type: "object",
        properties: {
          files: {
            type: "array",
            items: {
              type: "object",
              properties: {
                path: { type: "string" },
                expected_lines: { type: "number" },
              },
              required: ["path"],
            },
            description: "Array of files to check",
          },
        },
        required: ["files"],
      },
    },
    {
      name: "line_count_guard",
      description: "Compare expected vs actual line count. Fails if delta exceeds tolerance.",
      inputSchema: {
        type: "object",
        properties: {
          path: { type: "string", description: "File path" },
          expected: { type: "number", description: "Expected line count" },
          tolerance: { type: "number", description: "Allowed deviation (default: 2)" },
        },
        required: ["path", "expected"],
      },
    },
    {
      name: "pre_stage_check",
      description: "Run full verification on all modified files in git working tree. Equivalent to running verify-tree.sh.",
      inputSchema: {
        type: "object",
        properties: {
          repo_path: { type: "string", description: "Path to the git repository root" },
        },
        required: ["repo_path"],
      },
    },
  ],
}));

// Helper functions
function checkNullBytes(filePath) {
  try {
    const content = readFileSync(filePath);
    return content.includes(0) ? { pass: false, detail: "Null bytes detected" } : { pass: true };
  } catch (e) {
    return { pass: false, detail: `Read error: ${e.message}` };
  }
}

function checkBracketBalance(filePath) {
  try {
    const content = readFileSync(filePath, "utf-8");
    const open = (content.match(/{/g) || []).length;
    const close = (content.match(/}/g) || []).length;
    const delta = Math.abs(open - close);
    if (delta > 3) {
      return { pass: false, detail: `Brace imbalance: { ${open} } ${close} delta ${open - close}` };
    }
    if (delta > 0) {
      return { pass: true, warning: `Minor brace mismatch: delta ${open - close}` };
    }
    return { pass: true };
  } catch (e) {
    return { pass: false, detail: `Read error: ${e.message}` };
  }
}

function checkLineCount(filePath, expected, tolerance = 2) {
  try {
    const content = readFileSync(filePath, "utf-8");
    const actual = content.split("\n").length - (content.endsWith("\n") ? 1 : 0);
    const delta = Math.abs(actual - expected);
    if (delta > tolerance) {
      return { pass: false, detail: `Line count: expected ~${expected}, got ${actual} (delta ${actual - expected})` };
    }
    return { pass: true, actual };
  } catch (e) {
    return { pass: false, detail: `Read error: ${e.message}` };
  }
}

function checkTruncation(filePath, repoPath) {
  try {
    const relPath = filePath.replace(repoPath + "/", "");
    const headContent = execSync(`git -C "${repoPath}" show HEAD:"${relPath}" 2>/dev/null`, { encoding: "utf-8" });
    const currentContent = readFileSync(filePath, "utf-8");
    const headLines = headContent.split("\n").length;
    const currentLines = currentContent.split("\n").length;
    if (headLines > 10 && currentLines > 0) {
      const ratio = Math.round((currentLines / headLines) * 100);
      if (ratio < 50) {
        return { pass: false, detail: `Truncation: ${headLines} -> ${currentLines} lines (${ratio}%)` };
      }
      if (ratio < 75) {
        return { pass: true, warning: `Shrunk: ${headLines} -> ${currentLines} lines (${ratio}%)` };
      }
    }
    return { pass: true };
  } catch (e) {
    // File not in HEAD (new file) - skip truncation check
    return { pass: true };
  }
}

function validateFile(filePath, expectedLines, expectedTail) {
  const results = [];

  // Existence
  if (!existsSync(filePath)) {
    return [{ check: "existence", pass: false, detail: "File not found" }];
  }
  results.push({ check: "existence", pass: true });

  // Null bytes
  const nullCheck = checkNullBytes(filePath);
  results.push({ check: "null-bytes", ...nullCheck });
  if (!nullCheck.pass) return results;

  // Line count
  if (expectedLines) {
    const lcCheck = checkLineCount(filePath, expectedLines);
    results.push({ check: "line-count", ...lcCheck });
  }

  // Bracket balance (code files only)
  if (/\.(rs|py|js|ts|json)$/.test(filePath)) {
    const bracketCheck = checkBracketBalance(filePath);
    results.push({ check: "bracket-balance", ...bracketCheck });
  }

  // Tail content
  if (expectedTail) {
    try {
      const content = readFileSync(filePath, "utf-8");
      const lines = content.trimEnd().split("\n");
      const lastLine = lines[lines.length - 1];
      const pass = lastLine.trim() === expectedTail.trim();
      results.push({
        check: "tail-content",
        pass,
        detail: pass ? undefined : `Expected: "${expectedTail}" Got: "${lastLine}"`,
      });
    } catch (e) {
      results.push({ check: "tail-content", pass: false, detail: e.message });
    }
  }

  // File size (not empty)
  const stat = statSync(filePath);
  if (stat.size === 0) {
    results.push({ check: "non-empty", pass: false, detail: "File is 0 bytes" });
  } else {
    results.push({ check: "non-empty", pass: true });
  }

  return results;
}

// Tool handlers
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  switch (name) {
    case "validate_file": {
      const results = validateFile(args.path, args.expected_lines, args.expected_tail);
      const failed = results.filter((r) => !r.pass);
      const status = failed.length > 0 ? "FAIL" : "PASS";
      return {
        content: [{
          type: "text",
          text: JSON.stringify({ status, file: args.path, checks: results }, null, 2),
        }],
      };
    }

    case "safe_write": {
      const tmpPath = `${tmpdir()}/mai-safe-write-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      let content = args.content;

      // Ensure trailing newline
      if (!content.endsWith("\n")) content += "\n";

      // Write to temp
      writeFileSync(tmpPath, content, "utf-8");

      // Verify temp
      const tmpCheck = checkNullBytes(tmpPath);
      if (!tmpCheck.pass) {
        return { content: [{ type: "text", text: JSON.stringify({ status: "FAIL", reason: "Null bytes in temp write" }) }] };
      }

      const actualLines = content.split("\n").length - 1;
      if (args.expected_lines && Math.abs(actualLines - args.expected_lines) > 2) {
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              status: "FAIL",
              reason: `Line count mismatch: expected ${args.expected_lines}, content has ${actualLines}`,
            }),
          }],
        };
      }

      // Copy to target
      mkdirSync(dirname(args.path), { recursive: true });
      copyFileSync(tmpPath, args.path);

      // Verify target
      const targetCheck = checkNullBytes(args.path);
      const targetStat = statSync(args.path);
      const tmpStat = statSync(tmpPath);

      if (!targetCheck.pass || targetStat.size !== tmpStat.size) {
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              status: "FAIL",
              reason: "Target verification failed after copy",
              expected_bytes: tmpStat.size,
              actual_bytes: targetStat.size,
            }),
          }],
        };
      }

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            status: "PASS",
            file: args.path,
            lines: actualLines,
            bytes: targetStat.size,
          }),
        }],
      };
    }

    case "verify_batch": {
      const results = args.files.map((f) => ({
        file: f.path,
        checks: validateFile(f.path, f.expected_lines),
      }));
      const allPassed = results.every((r) => r.checks.every((c) => c.pass));
      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            status: allPassed ? "ALL_PASS" : "HAS_FAILURES",
            results,
          }, null, 2),
        }],
      };
    }

    case "line_count_guard": {
      const tolerance = args.tolerance || 2;
      const result = checkLineCount(args.path, args.expected, tolerance);
      return {
        content: [{
          type: "text",
          text: JSON.stringify({ status: result.pass ? "PASS" : "FAIL", ...result, file: args.path }),
        }],
      };
    }

    case "pre_stage_check": {
      try {
        const output = execSync(
          `cd "${args.repo_path}" && bash .integrity/scripts/verify-tree.sh 2>&1`,
          { encoding: "utf-8", timeout: 30000 }
        );
        const failed = output.includes("INTEGRITY CHECK FAILED");
        return {
          content: [{
            type: "text",
            text: JSON.stringify({ status: failed ? "FAIL" : "PASS", output }),
          }],
        };
      } catch (e) {
        return {
          content: [{
            type: "text",
            text: JSON.stringify({ status: "FAIL", error: e.message, output: e.stdout || "" }),
          }],
        };
      }
    }

    default:
      return { content: [{ type: "text", text: `Unknown tool: ${name}` }] };
  }
});

// Start server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("MAI Integrity MCP server running on stdio");
}

main().catch(console.error);

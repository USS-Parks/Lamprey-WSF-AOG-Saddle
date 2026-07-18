#!/usr/bin/env node
// @ts-check
/**
 * MAI Integrity MCP Server
 *
 * Provides file integrity tools for CoWork sessions:
 * - validate_file: Check a file for corruption indicators
 * - safe_write: Atomic two-stage write with verification
 * - verify_batch: Check multiple files in one call
 * - line_count_guard: Compare expected vs actual line counts
 * - pre_stage_check: Full verification pass before git add
 *
 * Refactored in J-11: handler bodies live in handlers.js, validators in
 * validators.js, logging in logger.js. This module owns bootstrap, tool
 * schema declarations, and dispatch only.
 */
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

import { handlers } from "./handlers.js";
import { log } from "./logger.js";

const TOOLS = [
  {
    name: "validate_file",
    description:
      "Check a single file for corruption: null bytes, truncation vs HEAD, bracket balance, syntax validity. Returns structured pass/fail report.",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Absolute path to the file to validate" },
        expected_lines: {
          type: "number",
          description: "Expected line count (optional, tolerance +/- 2)",
        },
        expected_tail: {
          type: "string",
          description: "Expected content of the last line (optional)",
        },
      },
      required: ["path"],
    },
  },
  {
    name: "safe_write",
    description:
      "Atomic file write: writes to /tmp, verifies, then copies to target. Rejects if verification fails.",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Target file path" },
        content: { type: "string", description: "File content to write" },
        expected_lines: {
          type: "number",
          description: "Expected line count for post-write verification",
        },
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
    description:
      "Run full verification on all modified files in git working tree. Equivalent to running verify-tree.sh.",
    inputSchema: {
      type: "object",
      properties: {
        repo_path: { type: "string", description: "Path to the git repository root" },
      },
      required: ["repo_path"],
    },
  },
];

const server = new Server(
  { name: "mai-integrity", version: "1.0.0" },
  { capabilities: { tools: {} } },
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOLS }));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  const handler = handlers[name];
  if (!handler) {
    log.warn("unknown tool requested", { tool: name });
    return { content: [{ type: "text", text: `Unknown tool: ${name}` }] };
  }
  try {
    return handler(args);
  } catch (e) {
    log.error("handler threw", { tool: name, error: e.message });
    return {
      content: [
        { type: "text", text: JSON.stringify({ status: "FAIL", error: e.message }) },
      ],
    };
  }
});

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  log.info("MAI Integrity MCP server running on stdio");
}

main().catch((e) => {
  log.error("server failed to start", { error: e.message });
  process.exit(1);
});

// @ts-check
/**
 * Thin pino wrapper for the MAI integrity MCP server.
 *
 * The server speaks JSON-RPC over stdio; stdout is reserved for protocol
 * frames, so every log line is routed to stderr (file descriptor 2) to
 * avoid corrupting the wire. Output is line-delimited JSON, suitable for
 * the integrity tooling's audit consumers.
 */
import pino from "pino";

const level = process.env.MAI_MCP_LOG_LEVEL || "info";

const logger = pino(
  {
    level,
    base: { component: "mai-integrity-mcp" },
    timestamp: pino.stdTimeFunctions.isoTime,
  },
  pino.destination({ dest: 2, sync: true }),
);

export const log = {
  info: (msg, extra) => logger.info(extra || {}, msg),
  warn: (msg, extra) => logger.warn(extra || {}, msg),
  error: (msg, extra) => logger.error(extra || {}, msg),
  debug: (msg, extra) => logger.debug(extra || {}, msg),
};

export default log;

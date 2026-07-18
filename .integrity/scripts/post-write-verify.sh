#!/usr/bin/env bash
# post-write-verify.sh - Verify a file after write operation
# Usage: post-write-verify.sh <file> <expected-lines> [expected-last-line-content]
# Returns 0 if file passes all checks, 1 if corruption detected.

set -uo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

FILE="$1"
EXPECTED_LINES="${2:-0}"
EXPECTED_TAIL="${3:-}"

if [ ! -f "$FILE" ]; then
    echo -e "${RED}FAIL${NC}: File does not exist: $FILE"
    exit 1
fi

ACTUAL_LINES=$(wc -l < "$FILE")
ACTUAL_BYTES=$(wc -c < "$FILE")

# Check 1: File not empty
if [ "$ACTUAL_BYTES" -eq 0 ]; then
    echo -e "${RED}FAIL${NC}: File is empty (0 bytes)"
    exit 1
fi

# Check 2: Null bytes
CLEAN_BYTES=$(tr -d '\0' < "$FILE" | wc -c)
if [ "$ACTUAL_BYTES" -ne "$CLEAN_BYTES" ]; then
    echo -e "${RED}FAIL${NC}: Null bytes detected"
    exit 1
fi

# Check 3: Line count within tolerance
if [ "$EXPECTED_LINES" -gt 0 ]; then
    DELTA=$((ACTUAL_LINES - EXPECTED_LINES))
    ABS_DELTA=${DELTA#-}

    if [ "$ABS_DELTA" -gt 2 ]; then
        echo -e "${RED}FAIL${NC}: Line count mismatch (expected ~${EXPECTED_LINES}, got ${ACTUAL_LINES}, delta ${DELTA})"
        exit 1
    fi
fi

# Check 4: Last line content match (if provided)
if [ -n "$EXPECTED_TAIL" ]; then
    ACTUAL_TAIL=$(tail -1 "$FILE")
    if [ "$ACTUAL_TAIL" != "$EXPECTED_TAIL" ]; then
        echo -e "${RED}FAIL${NC}: Last line mismatch"
        echo "  Expected: $EXPECTED_TAIL"
        echo "  Got:      $ACTUAL_TAIL"
        exit 1
    fi
fi

# Check 5: Trailing newline
if [ "$(tail -c 1 "$FILE" | wc -l)" -eq 0 ]; then
    echo -e "${YELLOW}WARN${NC}: No trailing newline (auto-fixable)"
fi

echo -e "${GREEN}PASS${NC}: $FILE ($ACTUAL_LINES lines, $ACTUAL_BYTES bytes)"
exit 0

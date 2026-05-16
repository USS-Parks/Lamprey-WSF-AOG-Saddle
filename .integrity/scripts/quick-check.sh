#!/usr/bin/env bash
# quick-check.sh - Fast single-file integrity check (no Node required)
# Usage: quick-check.sh <file> [expected-lines]
# Returns 0=pass, 1=fail, 2=warning

set -uo pipefail

FILE="$1"
EXPECTED="${2:-0}"

if [ ! -f "$FILE" ]; then
    echo "FAIL: File not found: $FILE"
    exit 1
fi

BYTES=$(wc -c < "$FILE")
LINES=$(wc -l < "$FILE")

# Empty check
if [ "$BYTES" -eq 0 ]; then
    echo "FAIL: Empty file (0 bytes)"
    exit 1
fi

# Null bytes (compare raw size vs size after stripping nulls)
CLEAN_BYTES=$(tr -d '\0' < "$FILE" | wc -c)
if [ "$BYTES" -ne "$CLEAN_BYTES" ]; then
    echo "FAIL: Null bytes detected ($((BYTES - CLEAN_BYTES)) null bytes found)"
    exit 1
fi

# Line count
if [ "$EXPECTED" -gt 0 ]; then
    DELTA=$((LINES - EXPECTED))
    ABS=${DELTA#-}
    if [ "$ABS" -gt 2 ]; then
        echo "FAIL: Line count ${LINES} vs expected ${EXPECTED} (delta ${DELTA})"
        exit 1
    fi
fi

# Bracket balance (code files only)
case "$FILE" in
    *.rs|*.py|*.js|*.ts|*.json)
        OPEN=$(grep -c '{' "$FILE" || true)
        CLOSE=$(grep -c '}' "$FILE" || true)
        DELTA=$((OPEN - CLOSE))
        ABS=${DELTA#-}
        if [ "$ABS" -gt 3 ]; then
            echo "FAIL: Brace imbalance ({:$OPEN }:$CLOSE delta:$DELTA)"
            exit 1
        elif [ "$ABS" -gt 0 ]; then
            echo "WARN: Minor brace mismatch (delta $DELTA)"
            echo "PASS: $FILE ($LINES lines, $BYTES bytes) [with warning]"
            exit 2
        fi
        ;;
esac

echo "PASS: $FILE ($LINES lines, $BYTES bytes)"
exit 0

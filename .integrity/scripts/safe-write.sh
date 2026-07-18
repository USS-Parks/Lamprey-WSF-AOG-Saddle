#!/usr/bin/env bash
# safe-write.sh - Atomic file write with verification
# Usage: safe-write.sh <target-path> < content
# Or:    safe-write.sh <target-path> <source-file>
# Writes to /tmp first, verifies, then copies to target atomically.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

TARGET="$1"
TMPFILE="/tmp/safe-write-$$-$(basename "$TARGET")"

# Write content to temp
if [ $# -ge 2 ] && [ -f "$2" ]; then
    cp "$2" "$TMPFILE"
else
    cat > "$TMPFILE"
fi

# Verify temp file
BYTES=$(wc -c < "$TMPFILE")
LINES=$(wc -l < "$TMPFILE")

if [ "$BYTES" -eq 0 ]; then
    echo -e "${RED}ABORT${NC}: Temp file is empty. Write failed silently."
    rm -f "$TMPFILE"
    exit 1
fi

# Check for null bytes
if grep -Pq '\x00' "$TMPFILE" 2>/dev/null; then
    echo -e "${RED}ABORT${NC}: Null bytes detected in temp file."
    rm -f "$TMPFILE"
    exit 1
fi

# Check last line is complete (has newline)
if [ "$(tail -c 1 "$TMPFILE" | wc -l)" -eq 0 ]; then
    echo "" >> "$TMPFILE"
fi

# Copy to target
mkdir -p "$(dirname "$TARGET")"
cp "$TMPFILE" "$TARGET"

# Verify target matches temp
TARGET_BYTES=$(wc -c < "$TARGET")
if [ "$TARGET_BYTES" -ne "$(wc -c < "$TMPFILE")" ]; then
    echo -e "${RED}ABORT${NC}: Target size mismatch after copy!"
    echo "  Expected: $(wc -c < "$TMPFILE") bytes"
    echo "  Got: $TARGET_BYTES bytes"
    rm -f "$TMPFILE"
    exit 1
fi

rm -f "$TMPFILE"
echo -e "${GREEN}OK${NC}: $TARGET ($LINES lines, $BYTES bytes)"
exit 0

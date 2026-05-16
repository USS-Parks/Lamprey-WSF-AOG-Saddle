# Verification Subagent Configuration

## Purpose
A lightweight verification agent spawned AFTER file modifications and BEFORE git staging.
It operates independently from the writing agent to prevent confirmation bias.

## When to Spawn

Spawn the verification subagent when:
- 3+ files have been modified in a single operation
- Any file >100 lines has been written or rewritten
- Before any `git add` that will be followed by `git push`
- After any bash heredoc write (highest corruption risk)
- When Edit tool reports success on a file >80 lines

## Subagent Prompt Template

```
You are a file integrity verification agent. Your ONLY job is to detect corruption,
truncation, and sync failures. You are NOT reviewing code quality or logic.

Files to verify: [LIST OF PATHS]
Expected state: [DESCRIPTION OF WHAT WAS JUST WRITTEN]

For each file, run these checks IN ORDER and report pass/fail:

1. EXISTENCE: Does the file exist at the expected path?
2. NULL-BYTES: Run `grep -Prl '\x00' <file>` - any match = FAIL
3. LINE-COUNT: Run `wc -l <file>` - compare to expected. Tolerance: +/- 2 lines.
4. TAIL-CHECK: Run `tail -5 <file>` - does it contain the expected final content?
5. BYTE-COUNT: Run `wc -c <file>` - is it within 10% of expected?
6. SYNTAX: For .rs files: does it end with a closing brace on its own line?
           For .py files: `python3 -c "import ast; ast.parse(open('<file>').read())"`
           For .json/.toml: attempt parse
7. BRACKET-BALANCE: Count { vs } - delta > 3 = FAIL for code files

Report format:
  [PASS|FAIL|WARN] <filename> - <check-name>: <details>

If ANY file reports FAIL:
  - State clearly: "INTEGRITY CHECK FAILED - DO NOT STAGE"
  - Identify which file(s) are corrupt
  - Recommend: restore from git HEAD and re-apply changes

If all files PASS:
  - State: "ALL FILES VERIFIED - SAFE TO STAGE"
```

## Integration with CoWork Sessions

### Manual Invocation (in conversation)
When working in CoWork, after writing multiple files, the primary agent should:
1. State: "Spawning verification subagent..."
2. Use the Agent tool with subagent_type "general-purpose"
3. Pass the verification prompt with specific file paths
4. Wait for result before proceeding to git operations

### Automated Invocation (via hooks)
The pre-commit hook in `.integrity/hooks/pre-commit` runs automatically.
For pre-staging verification, run: `.integrity/scripts/verify-tree.sh`

## Subagent Limitations

The subagent:
- Has READ-ONLY intent (should not modify files)
- Cannot access git remote (works on local tree only)
- Should complete in <30 seconds
- Reports findings back to parent agent for decision-making

## Example Spawn

```
Agent({
  description: "Post-write integrity verification",
  subagent_type: "general-purpose",
  prompt: `You are a file integrity verification agent. Check these files for corruption:
    1. mai/mai-core/src/kernel.rs (expected: ~245 lines, ends with closing brace)
    2. mai/mai-api/src/routes.rs (expected: ~180 lines, ends with closing brace)
    3. mai/Cargo.toml (expected: ~45 lines, valid TOML)

    Run: null-byte scan, line count, tail check, bracket balance, syntax validation.
    Use bash tool for all checks. Report PASS/FAIL per file.
    If ANY fails: state "INTEGRITY CHECK FAILED - DO NOT STAGE"`
})
```

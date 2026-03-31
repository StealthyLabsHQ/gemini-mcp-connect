#!/usr/bin/env bash
# gemini-bridge — Pre-edit hook
# Triggered before Claude applies file edits (Edit / Write / MultiEdit tools).
# Reads the tool input from stdin (JSON) and optionally runs a Gemini review.
#
# Registration (add to .claude/settings.json):
# {
#   "hooks": {
#     "PreToolUse": [
#       {
#         "matcher": "Edit|Write|MultiEdit",
#         "hooks": [
#           {
#             "type": "command",
#             "command": "bash /path/to/hooks/pre-edit-review.sh"
#           }
#         ]
#       }
#     ]
#   }
# }
#
# Environment variables set by Claude Code during hook execution:
#   CLAUDE_TOOL_NAME        — name of the tool being called
#   CLAUDE_PROJECT_DIR      — root directory of the current project

PLUGIN_SCRIPT="C:/Users/stealthy/.claude/plugins/gemini_bridge.py"

# Read tool input JSON from stdin
INPUT=$(cat)

# Extract file path from tool input
FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('file_path') or d.get('path') or 'unknown')
except Exception:
    print('unknown')
" 2>/dev/null)

# Extract new content (for Write tool) or diff (for Edit tool)
CONTENT=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    # Write tool uses 'content', Edit tool uses 'new_string'
    print(d.get('content') or d.get('new_string') or '')
except Exception:
    print('')
" 2>/dev/null)

# Skip review for trivial edits (< 10 lines changed)
LINE_COUNT=$(echo "$CONTENT" | wc -l)
if [ "$LINE_COUNT" -lt 10 ]; then
    exit 0
fi

echo "[gemini-bridge] Reviewing edit to: $FILE_PATH ($LINE_COUNT lines)" >&2

# Run Gemini review (non-blocking — exits 0 regardless of findings)
python3 "$PLUGIN_SCRIPT" --tier flash \
    "Quick pre-edit review. File: $FILE_PATH. Is this code change safe to apply? Flag only CRITICAL issues (security vulnerabilities, data loss risks, breaking changes). If none found, respond with 'OK'. Change:\n\n$CONTENT" \
    2>/dev/null || true

# Always exit 0 — this hook is advisory, not blocking
exit 0

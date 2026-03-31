---
description: Submit code to Gemini for expert critical review. Finds bugs, security issues, and optimizations. Usage: /review-code <code or file path>
---

Take the code provided in $ARGUMENTS (or read the file if a path is given) and submit it to Gemini for critical review:

```bash
python "C:/Users/stealthy/.claude/plugins/gemini_bridge.py" --tier flash "You are an expert code reviewer and security auditor. Analyze this code critically. For each issue found, specify: severity (CRITICAL/WARNING/SUGGESTION), location (line or function), problem description, and concrete fix. Code:\n\n$ARGUMENTS"
```

After receiving Gemini's response:
1. Present findings grouped by severity (CRITICAL first)
2. For CRITICAL issues: do not proceed with any edits until the user acknowledges
3. For WARNING/SUGGESTION: present them and ask if the user wants to address them
4. If no issues found: confirm the code passed review and proceed

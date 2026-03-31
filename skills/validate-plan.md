---
description: Submit an implementation plan to Gemini for validation before executing it. Usage: /validate-plan <plan description>
---

Take the implementation plan in $ARGUMENTS and submit it to Gemini for expert validation:

```bash
python "C:/Users/stealthy/.claude/plugins/gemini_bridge.py" --tier pro "You are a senior software architect. Critically review this implementation plan before it is executed. Find: 1) Missing or incorrect steps, 2) Wrong assumptions about the codebase or environment, 3) Security or data integrity risks, 4) Scalability or performance concerns, 5) Better alternative approaches. Be concise and actionable.\n\nPlan to validate:\n\n$ARGUMENTS"
```

After receiving Gemini's response:
1. Summarize what Gemini found in bullet points
2. Update the plan to address any CRITICAL or WARNING findings
3. Present the revised plan to the user for approval
4. Only proceed with execution after the user confirms the revised plan

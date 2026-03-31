"""
server.py — MCP Server entry point.

Launched by Claude Code via:
    uvx gemini-bridge
or:
    python -m gemini_bridge.server
"""

import sys

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("Error: mcp package not found. Run: pip install mcp", file=sys.stderr)
    sys.exit(1)

from .core import call_gemini, get_status, TIERS

# ── MCP server ────────────────────────────────────────────────────────────────

mcp = FastMCP(
    "gemini-bridge",
    instructions=(
        "Use these tools to get a second opinion from Google Gemini. "
        "Call review_code before writing or modifying significant code. "
        "Call validate_plan before executing any non-trivial implementation plan. "
        "Use query_gemini for open-ended questions or cross-checking reasoning."
    ),
)

# ── Tools ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def query_gemini(prompt: str, tier: str = "pro") -> str:
    """
    Send any prompt to Google Gemini and return the response.

    Use this tool to get a second opinion, cross-check your reasoning,
    or leverage Gemini's independent analysis on any topic.

    Args:
        prompt: The question, task, or content to send to Gemini.
        tier:   'lite' (fast/cheap), 'flash' (balanced), 'pro' (max reasoning, 100 req/day) [default: pro]
    """
    return call_gemini(prompt, tier)


@mcp.tool()
def review_code(code: str, language: str = "", tier: str = "flash") -> str:
    """
    Submit code to Gemini for critical expert review before applying it.

    Use this before writing or modifying important code. Gemini will
    independently check for bugs, security issues, and logic errors.

    Args:
        code:     The code to review (snippet, function, or full file).
        language: Programming language, e.g. 'python', 'typescript' (optional, for context).
        tier:     'flash' (default) or 'pro' (for security-critical code).
    """
    lang_hint = f"Language: {language}. " if language else ""
    prompt = (
        f"You are an expert code reviewer and security auditor. {lang_hint}"
        "Critically analyze this code. For each issue, specify:\n"
        "- Severity: CRITICAL / WARNING / SUGGESTION\n"
        "- Location: function name or line reference\n"
        "- Problem: clear description\n"
        "- Fix: concrete corrected snippet\n\n"
        "If no issues, respond with 'LGTM — no issues found.' and a brief rationale.\n\n"
        f"Code:\n\n```{language}\n{code}\n```"
    )
    return call_gemini(prompt, tier)


@mcp.tool()
def validate_plan(plan: str, tier: str = "pro") -> str:
    """
    Submit an implementation plan to Gemini for validation before executing it.

    Use this before starting any non-trivial task. Gemini will check for
    missing steps, wrong assumptions, and security risks.

    Args:
        plan: The implementation plan or approach to validate.
        tier: 'pro' (default, deep reasoning) or 'flash' (faster).
    """
    prompt = (
        "You are a senior software architect. Critically review this implementation plan "
        "before it is executed. Find:\n"
        "1. Missing or incorrect steps\n"
        "2. Wrong assumptions about the codebase, environment, or APIs\n"
        "3. Security or data integrity risks\n"
        "4. Scalability or performance concerns\n"
        "5. Better alternative approaches\n\n"
        "Rate each finding: CRITICAL / WARNING / SUGGESTION.\n"
        "End with a verdict: PROCEED / REVISE / DO NOT PROCEED.\n\n"
        f"Plan:\n\n{plan}"
    )
    return call_gemini(prompt, tier)


@mcp.tool()
def gemini_status() -> str:
    """
    Show remaining Gemini API quota for today and API key status.

    Use this to check how many 'pro' requests remain before switching to 'flash'.
    The pro tier is limited to 100 requests/day.
    """
    return get_status()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    mcp.run()  # stdio transport — required for Claude Code


if __name__ == "__main__":
    main()

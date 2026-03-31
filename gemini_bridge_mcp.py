#!/usr/bin/env python3
"""
gemini_bridge_mcp.py — MCP Server for Google Gemini

Install (Claude Code, user-scoped):
    claude mcp add --scope user gemini-bridge -- python /full/path/to/gemini_bridge_mcp.py

Requires:
    pip install mcp google-genai python-dotenv
    GEMINI_API_KEY in .env (same directory as this file)
"""

import os
import sys
import json
from pathlib import Path
from datetime import date

# ── All paths are absolute, relative to this file's directory ─────────────────
# Critical in MCP context: the working directory at runtime may differ.
BASE_DIR = Path(__file__).parent.resolve()

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("Error: mcp package not found. Run: pip install mcp", file=sys.stderr)
    sys.exit(1)

# ── Config ────────────────────────────────────────────────────────────────────

TIERS = {
    "lite":  "gemini-3.1-flash-lite-preview",
    "flash": "gemini-3-flash-preview",
    "pro":   "gemini-3.1-pro-preview",
}

RATE_LIMITS = {
    "pro": 100,  # requests per day
}

RATE_LIMIT_FILE = BASE_DIR / "rate_limit.json"

THINKING_BUDGETS = {
    "OFF":    0,
    "LOW":    1024,
    "MEDIUM": 4096,
    "HIGH":   8192,
}

# ── MCP server ────────────────────────────────────────────────────────────────

mcp = FastMCP(
    "gemini-bridge",
    instructions=(
        "Use these tools to get a second opinion from Google Gemini. "
        "Useful for validating plans, reviewing code, and cross-checking reasoning "
        "before applying changes. Always use review_code or validate_plan before "
        "making significant modifications to critical code."
    ),
)

# ── Rate limiting ─────────────────────────────────────────────────────────────

def _load_counter() -> dict:
    if RATE_LIMIT_FILE.exists():
        try:
            return json.loads(RATE_LIMIT_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}

def _save_counter(data: dict) -> None:
    try:
        RATE_LIMIT_FILE.write_text(json.dumps(data))
    except OSError as e:
        print(f"[gemini-bridge] Warning: could not save rate limit: {e}", file=sys.stderr)

def _check_and_increment(tier: str) -> tuple[int, int]:
    """Returns (used, limit). Raises RuntimeError if daily limit exceeded."""
    if tier not in RATE_LIMITS:
        return (0, 0)

    limit = RATE_LIMITS[tier]
    today = str(date.today())
    data  = _load_counter()

    entry = data.get(tier, {})
    if entry.get("date") != today:
        entry = {"date": today, "count": 0}

    if entry["count"] >= limit:
        raise RuntimeError(
            f"Daily limit reached for tier '{tier}': {entry['count']}/{limit} requests today. "
            f"Switch to --tier flash or --tier lite to continue."
        )

    entry["count"] += 1
    data[tier] = entry
    _save_counter(data)
    return (entry["count"], limit)

# ── Gemini API call ───────────────────────────────────────────────────────────

def _call_gemini(prompt: str, tier: str) -> str:
    """Core function: call Gemini API and return the text response."""
    if tier not in TIERS:
        return f"Error: unknown tier '{tier}'. Choose from: lite, flash, pro"

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return (
            "Error: GEMINI_API_KEY is not set. "
            f"Edit {BASE_DIR / '.env'} and add: GEMINI_API_KEY=your_key_here"
        )

    try:
        from google import genai
        from google.genai import types as genai_types
    except ImportError:
        return "Error: google-genai is not installed. Run: pip install google-genai"

    # Rate limit check
    try:
        used, limit = _check_and_increment(tier)
        if limit:
            print(f"[gemini-bridge] {tier}: {used}/{limit} requests today", file=sys.stderr)
    except RuntimeError as e:
        return f"Error: {e}"

    model  = TIERS[tier]
    client = genai.Client(api_key=api_key)

    # Build generation config
    temperature        = float(os.environ.get("GEMINI_TEMPERATURE", "1.0"))
    top_p              = float(os.environ.get("GEMINI_TOP_P", "0.95"))
    max_output_tokens  = int(os.environ.get("GEMINI_MAX_OUTPUT_TOKENS", "65536"))
    thinking_level     = os.environ.get("GEMINI_THINKING_LEVEL", "HIGH").upper()
    media_resolution   = os.environ.get("GEMINI_MEDIA_RESOLUTION", "MEDIUM").upper()

    cfg: dict = {
        "temperature":       temperature,
        "top_p":             top_p,
        "max_output_tokens": max_output_tokens,
    }

    if tier in ("flash", "pro"):
        budget = THINKING_BUDGETS.get(thinking_level, THINKING_BUDGETS["HIGH"])
        if budget > 0:
            cfg["thinking_config"] = genai_types.ThinkingConfig(
                thinking_budget=budget,
                include_thoughts=False,
            )

    res_map = {
        "LOW":    genai_types.MediaResolution.MEDIA_RESOLUTION_LOW,
        "MEDIUM": genai_types.MediaResolution.MEDIA_RESOLUTION_MEDIUM,
        "HIGH":   genai_types.MediaResolution.MEDIA_RESOLUTION_HIGH,
    }
    cfg["media_resolution"] = res_map.get(media_resolution, genai_types.MediaResolution.MEDIA_RESOLUTION_MEDIUM)

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=genai_types.GenerateContentConfig(**cfg),
        )
        return response.text
    except Exception as e:
        return f"Error [{model}]: {e}"

# ── MCP Tools ─────────────────────────────────────────────────────────────────

@mcp.tool()
def query_gemini(prompt: str, tier: str = "pro") -> str:
    """
    Send any prompt to Google Gemini and return the response.

    Use this tool to get a second opinion, cross-check reasoning, ask about
    recent information, or leverage Gemini's independent reasoning on any topic.

    Args:
        prompt: The question, task, or content to send to Gemini.
        tier:   Model tier to use:
                  'lite'  — gemini-3.1-flash-lite-preview (fast, cheap)
                  'flash' — gemini-3-flash-preview (balanced)
                  'pro'   — gemini-3.1-pro-preview (max reasoning, 100 req/day) [default]
    """
    return _call_gemini(prompt, tier)


@mcp.tool()
def review_code(code: str, language: str = "", tier: str = "flash") -> str:
    """
    Submit code to Gemini for critical expert review before applying it.

    Use this tool before writing or modifying critical code. Gemini will
    independently analyze for bugs, security vulnerabilities, logic errors,
    and optimizations that Claude might have missed.

    Args:
        code:     The code to review (snippet, function, or full file).
        language: Programming language for context (e.g. 'python', 'typescript').
                  Leave empty for auto-detection.
        tier:     'flash' (default, balanced) or 'pro' (deep reasoning for security-critical code).
    """
    lang_hint = f"Language: {language}. " if language else ""
    prompt = (
        f"You are an expert code reviewer and security auditor. {lang_hint}"
        "Critically analyze this code. For each issue found, specify:\n"
        "- Severity: CRITICAL / WARNING / SUGGESTION\n"
        "- Location: function name or line reference\n"
        "- Problem: clear description\n"
        "- Fix: concrete corrected code snippet\n\n"
        "If no issues are found, respond with 'LGTM — no issues found.' and a brief rationale.\n\n"
        f"Code to review:\n\n```{language}\n{code}\n```"
    )
    return _call_gemini(prompt, tier)


@mcp.tool()
def validate_plan(plan: str, tier: str = "pro") -> str:
    """
    Submit an implementation plan to Gemini for validation before executing it.

    Use this tool before starting any non-trivial implementation. Gemini will
    check for missing steps, wrong assumptions, security risks, and better
    alternatives. Only proceed after reviewing and integrating the feedback.

    Args:
        plan: The implementation plan, architecture description, or approach to validate.
        tier: 'pro' (default, max reasoning) or 'flash' (faster, less thorough).
    """
    prompt = (
        "You are a senior software architect. Critically review this implementation plan "
        "before it is executed. Find:\n"
        "1. Missing or incorrect steps\n"
        "2. Wrong assumptions about the codebase, environment, or APIs\n"
        "3. Security or data integrity risks\n"
        "4. Scalability or performance concerns\n"
        "5. Better alternative approaches\n\n"
        "Rate each finding: CRITICAL (blocks execution) / WARNING (should address) / SUGGESTION (optional).\n"
        "End with a verdict: PROCEED / REVISE / DO NOT PROCEED.\n\n"
        f"Plan to validate:\n\n{plan}"
    )
    return _call_gemini(prompt, tier)


@mcp.tool()
def gemini_status() -> str:
    """
    Show remaining Gemini API quota for today.

    Use this tool to check how many 'pro' tier requests remain before
    switching to 'flash' or 'lite'. The pro tier is limited to 100 req/day.
    """
    today = str(date.today())
    data  = _load_counter()
    lines = [f"Gemini Bridge quota — {today}"]

    for tier, limit in RATE_LIMITS.items():
        entry     = data.get(tier, {})
        count     = entry.get("count", 0) if entry.get("date") == today else 0
        remaining = limit - count
        lines.append(f"  {tier:6s} : {count:3d}/{limit} used  ({remaining} remaining)")

    for tier in TIERS:
        if tier not in RATE_LIMITS:
            lines.append(f"  {tier:6s} : unlimited")

    lines.append(f"\nAPI key configured: {'yes' if os.environ.get('GEMINI_API_KEY') else 'NO — set GEMINI_API_KEY in ' + str(BASE_DIR / '.env')}")
    return "\n".join(lines)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()  # defaults to stdio transport — required for Claude Code

#!/usr/bin/env python3
"""
gemini_bridge_mcp.py — MCP Server for Google Gemini

Install (Claude Code, user-scoped):
    claude mcp add --scope user gemini-bridge -- python /full/path/to/gemini_bridge_mcp.py

Requires:
    pip install "mcp>=1.27.0" "google-genai>=1.70.0" python-dotenv
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
            "Run /gemini:activate YOUR_KEY to activate, "
            "or get a free key at https://aistudio.google.com/apikey"
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

# ── Helpers ───────────────────────────────────────────────────────────────────

def _update_env_key(key_name: str, key_value: str) -> None:
    """Update or add a key in the .env file, preserving all other lines."""
    env_path = BASE_DIR / ".env"
    lines = []
    found = False
    if env_path.exists():
        lines = env_path.read_text().splitlines()
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{key_name}="):
                lines[i] = f"{key_name}={key_value}"
                found = True
                break
    if not found:
        lines.append(f"{key_name}={key_value}")
    env_path.write_text("\n".join(lines) + "\n")

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

    if os.environ.get("GEMINI_API_KEY"):
        lines.append("\nAPI key configured: yes")
    else:
        lines.append("\nAPI key configured: NO — run /gemini:activate YOUR_KEY to activate")
    return "\n".join(lines)


@mcp.tool()
def activate_gemini(api_key: str) -> str:
    """
    Activate Gemini by providing your API key. The key takes effect immediately
    (no restart needed) and is saved to .env for future sessions.

    Get a free key at https://aistudio.google.com/apikey

    Args:
        api_key: Your Gemini API key (starts with 'AI', ~39 characters).
    """
    api_key = api_key.strip()

    # Basic format validation
    if not api_key.startswith("AI") or len(api_key) < 30:
        return (
            "Error: That doesn't look like a valid Gemini API key. "
            "Keys start with 'AI' and are ~39 characters long. "
            "Get one free at https://aistudio.google.com/apikey"
        )

    # Set immediately in the running process
    os.environ["GEMINI_API_KEY"] = api_key

    # Persist to .env
    try:
        _update_env_key("GEMINI_API_KEY", api_key)
    except OSError as e:
        return f"Key activated for this session, but could not save to .env: {e}"

    # Quick verification call with the cheapest model
    try:
        from google import genai
        from google.genai import types as genai_types
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=TIERS["lite"],
            contents="Reply with exactly: OK",
            config=genai_types.GenerateContentConfig(max_output_tokens=8),
        )
        if response.text:
            return (
                f"Gemini activated successfully! Key saved to {BASE_DIR / '.env'}.\n"
                "All tools are now ready: /gemini:lite, /gemini:flash, /gemini:pro, /gemini:review, /gemini:validate"
            )
    except Exception as e:
        return (
            f"Key saved to {BASE_DIR / '.env'} but verification failed: {e}\n"
            "The key may be invalid or there may be a network issue. "
            "Try /gemini:status to check."
        )

    return f"Gemini activated. Key saved to {BASE_DIR / '.env'}."


@mcp.tool()
def security_audit(code: str, language: str = "", tier: str = "pro") -> str:
    """
    Run a security-focused audit on code using Gemini.

    Checks for OWASP Top 10 vulnerabilities, hardcoded secrets, injection
    flaws, insecure dependencies, and other security issues.

    Args:
        code:     Code to audit (snippet, function, or full file content).
        language: Programming language (e.g. 'python', 'typescript'). Auto-detected if empty.
        tier:     'pro' (default, deep reasoning) or 'flash' (faster).
    """
    lang_hint = f"Language: {language}. " if language else ""
    prompt = (
        f"You are a senior application security engineer. {lang_hint}"
        "Perform a thorough security audit of this code. Check for:\n"
        "1. OWASP Top 10 vulnerabilities (injection, broken auth, XSS, IDOR, etc.)\n"
        "2. Hardcoded secrets, API keys, passwords, or tokens\n"
        "3. Insecure cryptography or hashing (MD5, SHA1, weak keys)\n"
        "4. Command injection, path traversal, or unsafe deserialization\n"
        "5. Missing input validation or improper error handling that leaks info\n"
        "6. Insecure dependencies or dangerous function calls\n\n"
        "For each finding:\n"
        "- Severity: CRITICAL / HIGH / MEDIUM / LOW\n"
        "- Location: function or line reference\n"
        "- Vulnerability: clear description\n"
        "- Exploit scenario: how an attacker could abuse this\n"
        "- Fix: concrete corrected code\n\n"
        "If no issues found, respond with 'CLEAN — no security issues found.' and a brief rationale.\n\n"
        f"Code to audit:\n\n```{language}\n{code}\n```"
    )
    return _call_gemini(prompt, tier)


@mcp.tool()
def debug_error(error: str, context: str = "", tier: str = "flash") -> str:
    """
    Send an error or stack trace to Gemini for diagnosis and fix suggestions.

    Args:
        error:   The error message, exception, or stack trace to analyze.
        context: Optional: relevant code snippet or description of what you were doing.
        tier:    'flash' (default, fast) or 'pro' (deeper analysis for complex bugs).
    """
    ctx_section = f"\n\nContext / relevant code:\n{context}" if context else ""
    prompt = (
        "You are an expert debugger. Analyze this error and provide:\n"
        "1. Root cause — what exactly is failing and why\n"
        "2. Most likely fix — concrete code or command to resolve it\n"
        "3. Alternative causes — if ambiguous, list 2-3 other possibilities\n"
        "4. Prevention — how to avoid this class of error in the future\n\n"
        "Be direct and specific. Skip generic advice.\n\n"
        f"Error / stack trace:\n```\n{error}\n```"
        f"{ctx_section}"
    )
    return _call_gemini(prompt, tier)


@mcp.tool()
def configure_gemini(setting: str = "", value: str = "") -> str:
    """
    View or update Gemini Bridge configuration settings.

    Call with no arguments to view all current settings.
    Call with setting + value to update a specific setting immediately
    (takes effect for the current session and is saved to .env).

    Supported settings:
      thinking   → OFF / LOW / MEDIUM / HIGH  (thinking budget for pro & flash)
      temperature → 0.0 – 2.0                 (0=deterministic, 2=max creative)
      media      → LOW / MEDIUM / HIGH         (media resolution)
      tokens     → 1 – 65536                  (max output tokens)
      top_p      → 0.0 – 1.0                  (token sampling breadth)

    Args:
        setting: Setting name to update (thinking, temperature, media, tokens, top_p).
        value:   New value for the setting.
    """
    ENV_KEYS = {
        "thinking":    "GEMINI_THINKING_LEVEL",
        "temperature": "GEMINI_TEMPERATURE",
        "media":       "GEMINI_MEDIA_RESOLUTION",
        "tokens":      "GEMINI_MAX_OUTPUT_TOKENS",
        "top_p":       "GEMINI_TOP_P",
    }
    VALID_VALUES = {
        "thinking": ["OFF", "LOW", "MEDIUM", "HIGH"],
        "media":    ["LOW", "MEDIUM", "HIGH"],
    }
    DEFAULTS = {
        "GEMINI_THINKING_LEVEL":    "HIGH",
        "GEMINI_TEMPERATURE":       "1.0",
        "GEMINI_MEDIA_RESOLUTION":  "MEDIUM",
        "GEMINI_MAX_OUTPUT_TOKENS": "65536",
        "GEMINI_TOP_P":             "0.95",
    }

    # No args → show current config
    if not setting:
        lines = ["Gemini Bridge — current configuration\n"]
        for name, env_key in ENV_KEYS.items():
            current = os.environ.get(env_key, DEFAULTS[env_key])
            lines.append(f"  {name:<12} = {current}")
        lines.append(f"\n  Config file: {BASE_DIR / '.env'}")
        lines.append("  Use /gemini:config <setting> <value> to change a setting.")
        return "\n".join(lines)

    # Normalize
    setting = setting.lower().strip()
    value   = value.strip()

    if setting not in ENV_KEYS:
        return (
            f"Error: unknown setting '{setting}'. "
            f"Choose from: {', '.join(ENV_KEYS.keys())}"
        )
    if not value:
        env_key = ENV_KEYS[setting]
        current = os.environ.get(env_key, DEFAULTS[env_key])
        return f"Current value of '{setting}': {current}"

    env_key = ENV_KEYS[setting]

    # Validate allowed values
    if setting in VALID_VALUES:
        value_upper = value.upper()
        allowed = VALID_VALUES[setting]
        if value_upper not in allowed:
            return f"Error: '{value}' is not valid for '{setting}'. Choose from: {', '.join(allowed)}"
        value = value_upper

    # Validate numeric ranges
    if setting == "temperature":
        try:
            f = float(value)
            if not (0.0 <= f <= 2.0):
                return "Error: temperature must be between 0.0 and 2.0"
        except ValueError:
            return "Error: temperature must be a number (e.g. 0.7)"

    if setting == "top_p":
        try:
            f = float(value)
            if not (0.0 <= f <= 1.0):
                return "Error: top_p must be between 0.0 and 1.0"
        except ValueError:
            return "Error: top_p must be a number (e.g. 0.95)"

    if setting == "tokens":
        try:
            i = int(value)
            if not (1 <= i <= 65536):
                return "Error: tokens must be between 1 and 65536"
        except ValueError:
            return "Error: tokens must be an integer (e.g. 32768)"

    # Apply immediately
    os.environ[env_key] = value

    # Persist to .env
    try:
        _update_env_key(env_key, value)
    except OSError as e:
        return f"Setting applied for this session, but could not save to .env: {e}"

    return f"✓ {setting} = {value} (saved to {BASE_DIR / '.env'}, active immediately)"


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()  # defaults to stdio transport — required for Claude Code

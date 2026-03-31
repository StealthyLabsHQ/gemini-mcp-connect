"""
core.py — Shared logic: config, rate limiting, Gemini API call.
Used by both server.py (MCP) and cli.py (CLI).
"""

import os
import sys
import json
from datetime import date
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

TIERS = {
    "lite":  "gemini-3.1-flash-lite-preview",
    "flash": "gemini-3-flash-preview",
    "pro":   "gemini-3.1-pro-preview",
}

RATE_LIMITS = {
    "pro": 100,  # requests per day
}

THINKING_BUDGETS = {
    "OFF":    0,
    "LOW":    1024,
    "MEDIUM": 4096,
    "HIGH":   8192,
}

# ── Data directory (platformdirs) ─────────────────────────────────────────────
# ~/.local/share/gemini-bridge/  (Linux)
# ~/Library/Application Support/gemini-bridge/  (macOS)
# %APPDATA%/gemini-bridge/  (Windows)

def _get_data_dir() -> Path:
    try:
        from platformdirs import user_data_dir
        data_dir = Path(user_data_dir("gemini-bridge"))
    except ImportError:
        # Fallback to ~/.local/share/gemini-bridge
        data_dir = Path.home() / ".local" / "share" / "gemini-bridge"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir

RATE_LIMIT_FILE: Path = _get_data_dir() / "rate_limit.json"

# ── Rate limiting ─────────────────────────────────────────────────────────────

def load_counter() -> dict:
    if RATE_LIMIT_FILE.exists():
        try:
            return json.loads(RATE_LIMIT_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}

def save_counter(data: dict) -> None:
    try:
        RATE_LIMIT_FILE.write_text(json.dumps(data))
    except OSError as e:
        print(f"[gemini-bridge] Warning: could not save rate limit: {e}", file=sys.stderr)

def check_and_increment(tier: str) -> tuple[int, int]:
    """Returns (used, limit). Raises RuntimeError if daily limit exceeded."""
    if tier not in RATE_LIMITS:
        return (0, 0)

    limit = RATE_LIMITS[tier]
    today = str(date.today())
    data  = load_counter()

    entry = data.get(tier, {})
    if entry.get("date") != today:
        entry = {"date": today, "count": 0}

    if entry["count"] >= limit:
        raise RuntimeError(
            f"Daily limit reached for tier '{tier}': {entry['count']}/{limit} requests today. "
            f"Switch to 'flash' or 'lite' to continue."
        )

    entry["count"] += 1
    data[tier] = entry
    save_counter(data)
    return (entry["count"], limit)

def get_status() -> str:
    today = str(date.today())
    data  = load_counter()
    lines = [f"Gemini Bridge quota — {today}"]

    for tier, limit in RATE_LIMITS.items():
        entry     = data.get(tier, {})
        count     = entry.get("count", 0) if entry.get("date") == today else 0
        remaining = limit - count
        lines.append(f"  {tier:6s} : {count:3d}/{limit} used  ({remaining} remaining)")

    for tier in TIERS:
        if tier not in RATE_LIMITS:
            lines.append(f"  {tier:6s} : unlimited")

    api_key = os.environ.get("GEMINI_API_KEY")
    lines.append(f"\nAPI key: {'configured' if api_key else 'NOT SET — set GEMINI_API_KEY environment variable'}")
    lines.append(f"Data dir: {RATE_LIMIT_FILE.parent}")
    return "\n".join(lines)

# ── Gemini API call ───────────────────────────────────────────────────────────

def call_gemini(prompt: str, tier: str) -> str:
    """Call Gemini API and return the text response. Always returns a string (never raises)."""
    if tier not in TIERS:
        return f"Error: unknown tier '{tier}'. Choose from: {', '.join(TIERS)}"

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return (
            "Error: GEMINI_API_KEY is not set.\n"
            "Set it with: claude mcp add --scope user gemini-bridge -e GEMINI_API_KEY=your_key -- uvx gemini-bridge\n"
            "Get a free key at: https://aistudio.google.com/apikey"
        )

    try:
        from google import genai
        from google.genai import types as genai_types
    except ImportError:
        return "Error: google-genai is not installed. Run: pip install google-genai"

    try:
        used, limit = check_and_increment(tier)
        if limit:
            print(f"[gemini-bridge] {tier}: {used}/{limit} requests today", file=sys.stderr)
    except RuntimeError as e:
        return f"Error: {e}"

    model  = TIERS[tier]
    client = genai.Client(api_key=api_key)

    # Generation config from environment (with sensible defaults)
    temperature       = float(os.environ.get("GEMINI_TEMPERATURE", "1.0"))
    top_p             = float(os.environ.get("GEMINI_TOP_P", "0.95"))
    max_output_tokens = int(os.environ.get("GEMINI_MAX_OUTPUT_TOKENS", "65536"))
    thinking_level    = os.environ.get("GEMINI_THINKING_LEVEL", "HIGH").upper()
    media_resolution  = os.environ.get("GEMINI_MEDIA_RESOLUTION", "MEDIUM").upper()

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

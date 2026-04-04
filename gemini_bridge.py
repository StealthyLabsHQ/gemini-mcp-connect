#!/usr/bin/env python3
"""
gemini_bridge.py — Query Google Gemini from the command line.

Usage:
    python gemini_bridge.py "question"               # default: pro (deep)
    python gemini_bridge.py --tier lite "question"   # Gemini 3.1 Flash Lite Preview (light)
    python gemini_bridge.py --tier flash "question"  # Gemini 3 Flash Preview (medium)
    python gemini_bridge.py --tier pro "question"    # Gemini 3.1 Pro Preview (deep)
    python gemini_bridge.py --status                 # Show remaining pro quota

Tiers:
    lite   → gemini-3.1-flash-lite-preview   (lightweight, fast, cost-efficient)
    flash  → gemini-3-flash-preview          (balanced, speed + intelligence)
    pro    → gemini-3.1-pro-preview          (SOTA, max reasoning — 100 req/day)

Settings applied (pro & flash):
    temperature    = 2       (maximum creativity/exploration)
    thinking_level = high    (deep reasoning)
    media_resolution = high  (high media resolution)
    top_p          = 0.95
    max_output_tokens = 65536

Requires:
    pip install "google-genai>=1.70.0" python-dotenv
    GEMINI_API_KEY in .env or environment variable
"""

import sys
import os
import json
from datetime import date

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass

TIERS = {
    "lite":  "gemini-3.1-flash-lite-preview",
    "flash": "gemini-3-flash-preview",
    "pro":   "gemini-3.1-pro-preview",
}

RATE_LIMITS = {
    "pro": 100,  # requests per day
}

RATE_LIMIT_FILE = os.path.join(os.path.dirname(__file__), "rate_limit.json")

THINKING_BUDGETS = {
    "OFF":    0,
    "LOW":    1024,
    "MEDIUM": 4096,
    "HIGH":   8192,
}

def load_env_config() -> dict:
    """Read all GEMINI_* settings from environment variables."""
    return {
        "temperature":        float(os.environ.get("GEMINI_TEMPERATURE", "2.0")),
        "top_p":              float(os.environ.get("GEMINI_TOP_P", "0.95")),
        "max_output_tokens":  int(os.environ.get("GEMINI_MAX_OUTPUT_TOKENS", "65536")),
        "media_resolution":   os.environ.get("GEMINI_MEDIA_RESOLUTION", "HIGH").upper(),
        "thinking_level":     os.environ.get("GEMINI_THINKING_LEVEL", "HIGH").upper(),
        "tool_code_execution":          os.environ.get("GEMINI_TOOL_CODE_EXECUTION", "false").lower() == "true",
        "tool_grounding_google_search": os.environ.get("GEMINI_TOOL_GROUNDING_GOOGLE_SEARCH", "false").lower() == "true",
        "tool_grounding_google_maps":   os.environ.get("GEMINI_TOOL_GROUNDING_GOOGLE_MAPS", "false").lower() == "true",
        "tool_url_context":             os.environ.get("GEMINI_TOOL_URL_CONTEXT", "false").lower() == "true",
    }


# ── Rate limit ───────────────────────────────────────────────────────────────

def load_counter() -> dict:
    if os.path.exists(RATE_LIMIT_FILE):
        with open(RATE_LIMIT_FILE, "r") as f:
            return json.load(f)
    return {}

def save_counter(data: dict):
    with open(RATE_LIMIT_FILE, "w") as f:
        json.dump(data, f)

def check_and_increment(tier: str) -> tuple[int, int]:
    """Check quota and increment if allowed. Returns (used, limit). Raises RuntimeError if exceeded."""
    if tier not in RATE_LIMITS:
        return (0, 0)  # no limit for this tier

    limit = RATE_LIMITS[tier]
    today = str(date.today())
    data  = load_counter()

    entry = data.get(tier, {})
    if entry.get("date") != today:
        entry = {"date": today, "count": 0}

    if entry["count"] >= limit:
        raise RuntimeError(
            f"Rate limit reached for '{tier}': {entry['count']}/{limit} requests today ({today}).\n"
            f"Use --tier flash or --tier lite to continue."
        )

    entry["count"] += 1
    data[tier] = entry
    save_counter(data)
    return (entry["count"], limit)

def get_status() -> str:
    today = str(date.today())
    data  = load_counter()
    lines = ["Gemini Bridge quota — " + today]
    for tier, limit in RATE_LIMITS.items():
        entry = data.get(tier, {})
        count = entry.get("count", 0) if entry.get("date") == today else 0
        remaining = limit - count
        bar = ("█" * count + "░" * remaining)[:40] if limit <= 40 else f"{count}/{limit}"
        lines.append(f"  {tier:6s} : {count:3d}/{limit} used  ({remaining} remaining)  {bar}")
    for tier in TIERS:
        if tier not in RATE_LIMITS:
            lines.append(f"  {tier:6s} : unlimited")
    return "\n".join(lines)


# ── Model config ─────────────────────────────────────────────────────────────

def build_config(genai_types, tier: str):
    env = load_env_config()

    cfg = {
        "temperature":       env["temperature"],
        "top_p":             env["top_p"],
        "max_output_tokens": env["max_output_tokens"],
    }

    # Thinking (pro & flash only — lite does not support it)
    if tier in ("flash", "pro"):
        level  = env["thinking_level"]
        budget = THINKING_BUDGETS.get(level, THINKING_BUDGETS["HIGH"])
        if budget > 0:
            cfg["thinking_config"] = genai_types.ThinkingConfig(
                thinking_budget=budget,
                include_thoughts=False,
            )

    # Media resolution
    res_map = {
        "LOW":    genai_types.MediaResolution.MEDIA_RESOLUTION_LOW,
        "MEDIUM": genai_types.MediaResolution.MEDIA_RESOLUTION_MEDIUM,
        "HIGH":   genai_types.MediaResolution.MEDIA_RESOLUTION_HIGH,
    }
    cfg["media_resolution"] = res_map.get(env["media_resolution"], genai_types.MediaResolution.MEDIA_RESOLUTION_HIGH)

    # Tools
    tools = []
    if env["tool_code_execution"]:
        tools.append(genai_types.Tool(code_execution=genai_types.ToolCodeExecution()))
    if env["tool_grounding_google_search"]:
        tools.append(genai_types.Tool(google_search=genai_types.GoogleSearch()))
    if env["tool_url_context"]:
        tools.append(genai_types.Tool(url_context=genai_types.UrlContext()))
    if tools:
        cfg["tools"] = tools

    return genai_types.GenerateContentConfig(**cfg)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    # --status
    if "--status" in args:
        sys.stdout.buffer.write(get_status().encode("utf-8"))
        sys.stdout.buffer.write(b"\n")
        return

    # --tier
    tier = "pro"
    if "--tier" in args:
        idx = args.index("--tier")
        if idx + 1 >= len(args):
            print("Error: --tier requires a value: lite | flash | pro", file=sys.stderr)
            sys.exit(1)
        tier = args[idx + 1].lower()
        args = args[:idx] + args[idx + 2:]

    if tier not in TIERS:
        print(f"Error: unknown tier '{tier}'. Choose from: lite, flash, pro", file=sys.stderr)
        sys.exit(1)

    if not args:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    prompt = " ".join(args)

    # Check rate limit before calling the API
    try:
        used, limit = check_and_increment(tier)
        if limit:
            print(f"[gemini-bridge] {tier}: {used}/{limit} requests today", file=sys.stderr)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)

    try:
        from google import genai
        from google.genai import types as genai_types
    except ImportError:
        print("Error: google-genai is not installed. Run: pip install google-genai", file=sys.stderr)
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    model  = TIERS[tier]

    try:
        config   = build_config(genai_types, tier)
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )
        sys.stdout.buffer.write(response.text.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")
    except Exception as e:
        print(f"Error [{model}]: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

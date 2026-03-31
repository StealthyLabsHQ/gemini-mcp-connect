# Gemini Bridge

A Claude Code plugin that connects **Claude** to **Google Gemini** models, enabling dual-AI code review, reasoning validation, and critical analysis before applying any changes.

---

## Plugin Structure

```
gemini-bridge/
├── .claude-plugin/
│   └── plugin.json          # Plugin metadata & install manifest
├── commands/                # Slash commands
│   ├── gemini.md            # /gemini — query Gemini directly
│   └── gemini-status.md     # /gemini-status — check daily quota
├── agents/
│   └── gemini-reviewer.md   # Specialized dual-AI review agent
├── skills/                  # Focused task skills
│   ├── review-code.md       # /review-code — critical code review
│   └── validate-plan.md     # /validate-plan — plan validation
├── hooks/
│   ├── pre-edit-review.sh   # Pre-edit hook script
│   └── settings-snippet.json# Hook registration snippet
├── .mcp.json                # MCP config (placeholder)
├── gemini_bridge.py         # Core CLI script
└── README.md
```

---

## How it works

Before modifying any file, Claude automatically submits its plan or code to Gemini for a critical review (hallucinations, logic flaws, security issues, optimizations). Only after integrating Gemini's feedback does Claude apply the changes.

---

## Requirements

- Python 3.10+
- A Google Gemini API key → [aistudio.google.com](https://aistudio.google.com)
- Claude Code CLI

---

## Installation

### Quick install (recommended)

**macOS / Linux:**
```bash
git clone https://github.com/StealthyLabsHQ/gemini-mcp-connect
cd gemini-bridge
bash install.sh
```

**Windows (PowerShell):**
```powershell
git clone https://github.com/StealthyLabsHQ/gemini-mcp-connect
cd gemini-bridge
.\install.ps1
```

The installer will:
1. Check Python 3.10+
2. Install `google-genai` and `python-dotenv`
3. Copy `gemini_bridge.py` to `~/.claude/plugins/`
4. Ask for your Gemini API key and save it to `~/.claude/plugins/.env`
5. Install slash commands to `~/.claude/commands/`
6. Add the workflow instructions to `~/.claude/CLAUDE.md`
7. Run a connection test

Get your free API key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

---

### Manual install

<details>
<summary>Click to expand manual steps</summary>

```bash
# 1. Install dependencies
pip install google-genai python-dotenv

# 2. Copy core script
cp gemini_bridge.py ~/.claude/plugins/gemini_bridge.py

# 3. Set your API key
cp .env.example ~/.claude/plugins/.env
# then edit ~/.claude/plugins/.env and set GEMINI_API_KEY

# 4. Install slash commands
cp commands/gemini.md        ~/.claude/commands/gemini.md
cp commands/gemini-status.md ~/.claude/commands/gemini-status.md
cp skills/review-code.md     ~/.claude/commands/review-code.md
cp skills/validate-plan.md   ~/.claude/commands/validate-plan.md

# 5. Add workflow to CLAUDE.md (see CLAUDE.md section in Usage below)
```

</details>

### 3. Set your API key and configure settings

Copy the example file and fill in your key:

```bash
cp .env.example .env
```

Then edit `.env`:

```env
GEMINI_API_KEY=your_api_key_here

GEMINI_TEMPERATURE=1.0
GEMINI_MEDIA_RESOLUTION=MEDIUM
GEMINI_THINKING_LEVEL=HIGH
GEMINI_MAX_OUTPUT_TOKENS=65536
GEMINI_TOP_P=0.95

GEMINI_TOOL_CODE_EXECUTION=false
GEMINI_TOOL_GROUNDING_GOOGLE_SEARCH=false
GEMINI_TOOL_GROUNDING_GOOGLE_MAPS=false
GEMINI_TOOL_URL_CONTEXT=false
```

> Get your key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey) — free tier available.

### 4. Install globally (recommended)

Place the script in the Claude global plugins folder so it works across **all your projects** without copying anything:

```
C:/Users/<you>/.claude/plugins/gemini_bridge.py
C:/Users/<you>/.claude/plugins/.env
```

Then add the workflow instructions to your global `CLAUDE.md`:

```
C:/Users/<you>/.claude/CLAUDE.md
```

---

## Usage

```bash
# Default (pro tier)
python gemini_bridge.py "Your question or code here"

# Choose a tier
python gemini_bridge.py --tier lite  "question"   # fast & cheap
python gemini_bridge.py --tier flash "question"   # balanced
python gemini_bridge.py --tier pro   "question"   # max reasoning (default)

# Check your daily quota
python gemini_bridge.py --status
```

---

## Models

| Tier | Model | Description |
|------|-------|-------------|
| `lite` | `gemini-3.1-flash-lite-preview` | Lightweight, fast, cost-efficient |
| `flash` | `gemini-3-flash-preview` | Balanced — speed + intelligence |
| `pro` | `gemini-3.1-pro-preview` | SOTA reasoning, max depth (**default**) |

### Settings applied (pro & flash)

All settings are configurable via `.env`. Defaults from `.env.example`:

| Parameter | `.env.example` default | Effect |
|-----------|----------------------|--------|
| `GEMINI_TEMPERATURE` | `1.0` | `0.0` = deterministic → `2.0` = max creativity |
| `GEMINI_THINKING_LEVEL` | `HIGH` | `OFF` / `LOW` / `MEDIUM` / `HIGH` (pro & flash only) |
| `GEMINI_MEDIA_RESOLUTION` | `MEDIUM` | `LOW` / `MEDIUM` / `HIGH` |
| `GEMINI_TOP_P` | `0.95` | Token sampling breadth (`0.0` → `1.0`) |
| `GEMINI_MAX_OUTPUT_TOKENS` | `65536` | Max response length |

Thinking budget mapping:

| Level | `thinking_budget` |
|-------|------------------|
| `OFF` | `0` (disabled) |
| `LOW` | `1024` |
| `MEDIUM` | `4096` |
| `HIGH` | `8192` |

### Tools (disabled by default)

```env
GEMINI_TOOL_CODE_EXECUTION=false
GEMINI_TOOL_GROUNDING_GOOGLE_SEARCH=false
GEMINI_TOOL_GROUNDING_GOOGLE_MAPS=false
GEMINI_TOOL_URL_CONTEXT=false
```

Set any to `true` in your `.env` to enable it.

---

## Pricing & Cost Estimation

Pricing is per **1 million tokens** (input + output combined).

### Price table

| Model | Input | Output | Notes |
|-------|-------|--------|-------|
| `gemini-3.1-flash-lite-preview` | $0.25 / 1M | $1.50 / 1M | Text, image & video |
| `gemini-3-flash-preview` | $0.50 / 1M | $3.00 / 1M | All context lengths |
| `gemini-3.1-pro-preview` | $2.00 / 1M | $12.00 / 1M | ≤ 200K tokens |
| `gemini-3.1-pro-preview` | $4.00 / 1M | $18.00 / 1M | > 200K tokens |

---

### Real cost per request — worked example

Assume a typical Claude Code review request:

- **Input**: ~2,000 tokens (your plan/code + review prompt)
- **Output**: ~1,000 tokens (Gemini's critique)

#### `gemini-3.1-pro-preview` (pro tier)

```
Input cost  = 2,000 / 1,000,000 × $2.00  = $0.004000
Output cost = 1,000 / 1,000,000 × $12.00 = $0.012000
─────────────────────────────────────────────────────
Cost per request                          ≈ $0.016
```

**How many requests for $1.00?**
```
$1.00 / $0.016 = ~62 requests
```

**Daily budget at 100 requests/day:**
```
100 × $0.016 = $1.60 / day  →  ~$48 / month
```

---

#### `gemini-3-flash-preview` (flash tier)

```
Input cost  = 2,000 / 1,000,000 × $0.50 = $0.001000
Output cost = 1,000 / 1,000,000 × $3.00 = $0.003000
────────────────────────────────────────────────────
Cost per request                         ≈ $0.004
```

**How many requests for $1.00?**
```
$1.00 / $0.004 = ~250 requests
```

---

#### `gemini-3.1-flash-lite-preview` (lite tier)

```
Input cost  = 2,000 / 1,000,000 × $0.25 = $0.000500
Output cost = 1,000 / 1,000,000 × $1.50 = $0.001500
────────────────────────────────────────────────────
Cost per request                         ≈ $0.002
```

**How many requests for $1.00?**
```
$1.00 / $0.002 = ~500 requests
```

---

### Cost comparison summary

| Tier | Cost/request | Requests for $1 | Requests for $10 |
|------|-------------|-----------------|-----------------|
| `lite` | ~$0.002 | ~500 | ~5,000 |
| `flash` | ~$0.004 | ~250 | ~2,500 |
| `pro` | ~$0.016 | ~62 | ~625 |

> **Note:** Requests with longer inputs (large code blocks, full files) will cost proportionally more. The `pro` tier with `thinking_budget=8192` also consumes additional tokens for internal reasoning steps.

---

## Rate limit

The `pro` tier is rate-limited to **100 requests/day** by default to control costs (~$1.60/day max).

```bash
python gemini_bridge.py --status
# Gemini Bridge quota — 2026-03-31
#   pro    :   5/100 used  (95 remaining)
#   lite   : unlimited
#   flash  : unlimited
```

To change the limit, edit `RATE_LIMITS` in `gemini_bridge.py`:

```python
RATE_LIMITS = {
    "pro": 100,  # requests per day
}
```

---

## File structure

```
gemini-bridge/
├── gemini_bridge.py   # Main script
├── .env               # Your config & API key (never commit this)
├── .env.example       # Template — safe to commit
├── .gitignore         # Excludes .env
├── rate_limit.json    # Auto-generated daily counter
└── README.md
```

---

## License

MIT

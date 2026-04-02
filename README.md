# gemini-mcp-connect

A Claude Code plugin that connects **Claude** to **Google Gemini** as a native MCP tool — enabling dual-AI code review, plan validation, and critical second-opinion analysis.

[![PyPI](https://img.shields.io/pypi/v/gemini-mcp-connect)](https://pypi.org/project/gemini-mcp-connect/)
[![Python](https://img.shields.io/pypi/pyversions/gemini-mcp-connect)](https://pypi.org/project/gemini-mcp-connect/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## How it works

Before modifying any file, Claude automatically submits its plan or code to Gemini for a critical independent review — logic flaws, security issues, wrong assumptions, optimizations. Only after integrating Gemini's feedback does Claude apply the changes.

Gemini runs as a **native MCP tool**, not a bash script. Claude calls it directly, the same way it uses any other tool.

---

## Installation

### One-liner (no clone needed)

**macOS / Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/StealthyLabsHQ/gemini-mcp-connect/main/install.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/StealthyLabsHQ/gemini-mcp-connect/main/install.ps1 | iex
```

Both scripts will prompt for your Gemini API key. Get a free key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

---

### MCP only (no slash commands)

```bash
claude mcp add --scope user gemini-mcp-connect -e GEMINI_API_KEY=your_key_here -- uvx gemini-mcp-connect
```

---

### From clone

**macOS / Linux:**
```bash
git clone https://github.com/StealthyLabsHQ/gemini-mcp-connect
cd gemini-mcp-connect
bash install.sh
```

**Windows (PowerShell):**
```powershell
git clone https://github.com/StealthyLabsHQ/gemini-mcp-connect
cd gemini-mcp-connect
.\install.ps1
```

---

## Usage

### Tier prefix (fastest way)

Start any message with `pro,`, `flash,` or `lite,` to choose the Gemini model for that task:

```
pro, refactor this code
flash, search for information on X
lite, quick look at my code
```

No prefix → `pro` by default.

---

### MCP Tools

Claude calls these tools natively — no bash command needed.

| Tool | Default tier | Description |
|------|-------------|-------------|
| `query_gemini(prompt, tier)` | `pro` | Open-ended question to Gemini |
| `review_code(code, language, tier)` | `flash` | Critical code review |
| `validate_plan(plan, tier)` | `pro` | Validate a plan before executing |
| `gemini_status()` | — | Remaining quota for today |

---

## Models

| Tier | Model | Best for |
|------|-------|----------|
| `lite` | `gemini-3.1-flash-lite-preview` | Quick checks, fast & cheap |
| `flash` | `gemini-3-flash-preview` | Code review, balanced speed |
| `pro` | `gemini-3.1-pro-preview` | Architecture, security, deep reasoning (**default**) |

---

## Pricing

| Tier | Cost/request\* | Requests for $1 |
|------|---------------|-----------------|
| `lite` | ~$0.002 | ~500 |
| `flash` | ~$0.004 | ~250 |
| `pro` | ~$0.016 | ~62 |

\*Assumes ~2K input tokens + ~1K output tokens per request.

The `pro` tier is rate-limited to **100 requests/day** by default (~$1.60/day max). `flash` and `lite` are unlimited.

---

## Configuration

All settings are passed as environment variables via `claude mcp add -e`:

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | — | **Required.** Your Gemini API key |
| `GEMINI_TEMPERATURE` | `1.0` | `0.0` deterministic → `2.0` creative |
| `GEMINI_THINKING_LEVEL` | `HIGH` | `OFF` / `LOW` / `MEDIUM` / `HIGH` |
| `GEMINI_MAX_OUTPUT_TOKENS` | `65536` | Max response length |
| `GEMINI_TOP_P` | `0.95` | Token sampling breadth |
| `GEMINI_MEDIA_RESOLUTION` | `MEDIUM` | `LOW` / `MEDIUM` / `HIGH` |

---

## Plugin structure

```
gemini-mcp-connect/
├── gemini_bridge/           # Python package
│   ├── core.py              # Shared: API call, rate limiting, config
│   ├── server.py            # MCP server entry point
│   └── cli.py               # CLI entry point
├── .claude-plugin/
│   └── plugin.json          # Plugin metadata
├── commands/                # /gemini, /gemini-status slash commands
│   └── gemini/              # /gemini:lite, :flash, :pro, :status, :review, :validate
├── skills/                  # /review-code, /validate-plan
├── agents/                  # gemini-reviewer agent definition
├── hooks/                   # Pre-edit review hook (optional)
├── .mcp.json                # Project-scoped MCP config
├── pyproject.toml           # PyPI packaging
├── install.sh               # macOS/Linux installer
└── install.ps1              # Windows installer
```

---

## License

MIT — [StealthyLabsHQ](https://github.com/StealthyLabsHQ)

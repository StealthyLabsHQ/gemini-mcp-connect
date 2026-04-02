#!/usr/bin/env bash
# gemini-mcp-connect installer
# Local:  bash install.sh
# Remote: curl -fsSL https://raw.githubusercontent.com/StealthyLabsHQ/gemini-mcp-connect/main/install.sh | bash

set -e

REPO_RAW="https://raw.githubusercontent.com/StealthyLabsHQ/gemini-mcp-connect/main"
PLUGIN_DIR="$HOME/.claude/plugins"
COMMANDS_DIR="$HOME/.claude/commands"
CLAUDE_MD="$HOME/.claude/CLAUDE.md"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}!${NC} $1"; }
err()  { echo -e "${RED}✗${NC} $1"; exit 1; }

# Detect remote mode (script piped via curl — no local repo files)
if [ -f "gemini_bridge_mcp.py" ]; then
    REMOTE=false
else
    REMOTE=true
fi

fetch() {
    # fetch <remote_path> <dest_path>
    if command -v curl &>/dev/null; then
        curl -fsSL "$REPO_RAW/$1" -o "$2"
    elif command -v wget &>/dev/null; then
        wget -q "$REPO_RAW/$1" -O "$2"
    else
        err "curl or wget is required for remote install"
    fi
}

echo ""
echo "Installing gemini-mcp-connect plugin for Claude Code..."
$REMOTE && echo "(remote mode — downloading files from GitHub)" || echo "(local mode)"
echo ""

# ── 1. Check Python ───────────────────────────────────────────────────────────
python3 --version &>/dev/null || err "Python 3 is required. Install it from https://python.org"
ok "Python found: $(python3 --version)"

# ── 2. Install Python dependencies ────────────────────────────────────────────
echo "Installing Python dependencies..."
python3 -m pip install --quiet google-genai python-dotenv mcp
ok "google-genai, python-dotenv, mcp installed"

# ── 3. Create directories ─────────────────────────────────────────────────────
mkdir -p "$PLUGIN_DIR" "$COMMANDS_DIR" "$COMMANDS_DIR/gemini"
ok "Directories ready"

# ── 4. Install core scripts ───────────────────────────────────────────────────
if $REMOTE; then
    fetch "gemini_bridge.py"     "$PLUGIN_DIR/gemini_bridge.py"
    fetch "gemini_bridge_mcp.py" "$PLUGIN_DIR/gemini_bridge_mcp.py"
else
    cp gemini_bridge.py     "$PLUGIN_DIR/gemini_bridge.py"
    cp gemini_bridge_mcp.py "$PLUGIN_DIR/gemini_bridge_mcp.py"
fi
ok "Core scripts → $PLUGIN_DIR/"

# ── 5. API key setup ──────────────────────────────────────────────────────────
ENV_DEST="$PLUGIN_DIR/.env"

if [ -f "$ENV_DEST" ]; then
    warn ".env already exists at $ENV_DEST — skipping (won't overwrite your API key)"
else
    echo ""
    echo "Enter your Gemini API key (get one at https://aistudio.google.com/apikey):"
    # Use /dev/tty so this works even when piped via curl
    read -r -s API_KEY < /dev/tty
    if [ -z "$API_KEY" ]; then
        warn "No API key entered. Edit $ENV_DEST manually and set GEMINI_API_KEY."
        echo "GEMINI_API_KEY=your_key_here" > "$ENV_DEST"
    else
        echo "GEMINI_API_KEY=$API_KEY" > "$ENV_DEST"
        ok "API key saved to $ENV_DEST"
    fi
fi

# ── 6. Install slash commands ─────────────────────────────────────────────────
GEMINI_COMMANDS=(lite flash pro status review validate)

if $REMOTE; then
    for CMD in "${GEMINI_COMMANDS[@]}"; do
        fetch "commands/gemini/${CMD}.md" "$COMMANDS_DIR/gemini/${CMD}.md"
        ok "Installed /gemini:${CMD}"
    done
    for CMD in gemini gemini-status; do
        fetch "commands/${CMD}.md" "$COMMANDS_DIR/${CMD}.md" 2>/dev/null \
            && ok "Installed /${CMD}" || true
    done
else
    for FILE in commands/*.md skills/*.md; do
        [ -f "$FILE" ] || continue
        DEST="$COMMANDS_DIR/$(basename "$FILE")"
        sed "s|C:/Users/stealthy/.claude/plugins/gemini_bridge.py|$PLUGIN_DIR/gemini_bridge.py|g" "$FILE" > "$DEST"
        ok "Installed $(basename "$FILE")"
    done
    for FILE in commands/gemini/*.md; do
        [ -f "$FILE" ] || continue
        cp "$FILE" "$COMMANDS_DIR/gemini/$(basename "$FILE")"
        ok "Installed gemini/$(basename "$FILE")"
    done
fi

# ── 7. Add CLAUDE.md workflow instructions ────────────────────────────────────
MARKER="# Gemini Bridge — Plugin Global"

if grep -qF "$MARKER" "$CLAUDE_MD" 2>/dev/null; then
    warn "CLAUDE.md already contains Gemini Bridge instructions — skipping"
else
    cat >> "$CLAUDE_MD" << CLAUDEMD

$MARKER

## Ce que c'est
Un serveur MCP natif connecté à Google Gemini. Disponible dans **tous les projets** automatiquement.

- MCP server : \`gemini-mcp-connect\` (script Python)
- Tiers disponibles via le paramètre \`tier\` :
  - \`lite\`  → rapide, économique
  - \`flash\` → équilibré
  - \`pro\`   → défaut — raisonnement max (100 req/jour)

## Sélection du tier en début de message

Si le message commence par \`pro,\`, \`flash,\` ou \`lite,\`, utilise ce tier pour tous les appels Gemini de cette tâche.

## Tools disponibles (appel natif — PAS de Bash)
- \`query_gemini(prompt, tier)\` — question libre à Gemini
- \`review_code(code, language, tier)\` — review critique de code
- \`validate_plan(plan, tier)\` — validation de plan avant exécution
- \`gemini_status()\` — quota restant du jour

## Workflow obligatoire pour toute tâche complexe

1. **Analyser** la demande entièrement avant d'agir.
2. **Rédiger** le plan ou le code en mémoire — ne pas encore toucher les fichiers.
3. **OBLIGATOIRE — Soumettre à Gemini** via le tool MCP :
   - Pour un plan : appelle \`validate_plan(plan="[TON PLAN]")\`
   - Pour du code : appelle \`review_code(code="[TON CODE]", language="python")\`
4. **Lire la réponse Gemini** et corriger le plan.
5. **Exécuter** la tâche finale avec le plan corrigé et validé.

**Si le tool MCP échoue** : signaler à l'utilisateur et attendre ses instructions.
CLAUDEMD
    ok "Gemini Bridge workflow added to $CLAUDE_MD"
fi

# ── 8. Register MCP server with Claude Code ───────────────────────────────────
PYTHON_BIN=$(which python3)
MCP_SCRIPT="$PLUGIN_DIR/gemini_bridge_mcp.py"

echo ""
echo "Registering MCP server with Claude Code..."
if command -v claude &>/dev/null; then
    claude mcp add --scope user gemini-mcp-connect -- "$PYTHON_BIN" "$MCP_SCRIPT"
    ok "MCP server registered: gemini-mcp-connect"
else
    warn "'claude' CLI not found. Register manually with:"
    warn "  claude mcp add --scope user gemini-mcp-connect -- $PYTHON_BIN $MCP_SCRIPT"
fi

# ── 9. Verify dependencies ────────────────────────────────────────────────────
echo ""
if python3 -c "from mcp.server.fastmcp import FastMCP; from google import genai; print('OK')" 2>/dev/null | grep -q OK; then
    ok "All dependencies OK"
else
    warn "Dependency check failed. Run: pip install mcp google-genai python-dotenv"
fi

echo ""
echo "Available tools in Claude Code (via MCP):"
echo "  query_gemini(prompt, tier)     — query Gemini directly"
echo "  review_code(code, language)    — critical code review"
echo "  validate_plan(plan)            — validate implementation plan"
echo "  gemini_status()                — check daily quota"
echo ""
echo "Available slash commands:"
echo "  /gemini:lite <prompt>          — Gemini Lite (fast, economical)"
echo "  /gemini:flash <prompt>         — Gemini Flash (balanced)"
echo "  /gemini:pro <prompt>           — Gemini Pro (max reasoning, 100 req/day)"
echo "  /gemini:status                 — check daily quota"
echo "  /gemini:review <file|code>     — critical code review"
echo "  /gemini:validate <plan>        — validate plan before execution"
echo ""
echo "Done. Restart Claude Code to load the MCP server."

#!/usr/bin/env bash
# gemini-mcp-connect installer
# Usage: bash install.sh

set -e

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

echo ""
echo "Installing gemini-mcp-connect plugin for Claude Code..."
echo ""

# ── 1. Check Python ───────────────────────────────────────────────────────────
python3 --version &>/dev/null || err "Python 3 is required. Install it from https://python.org"
ok "Python found: $(python3 --version)"

# ── 2. Install Python dependencies ────────────────────────────────────────────
echo "Installing Python dependencies..."
python3 -m pip install --quiet google-genai python-dotenv mcp
ok "google-genai, python-dotenv, mcp installed"

# ── 3. Create directories ─────────────────────────────────────────────────────
mkdir -p "$PLUGIN_DIR" "$COMMANDS_DIR"
ok "Directories ready: $PLUGIN_DIR"

# ── 4. Copy core script ───────────────────────────────────────────────────────
cp gemini_bridge.py     "$PLUGIN_DIR/gemini_bridge.py"
cp gemini_bridge_mcp.py "$PLUGIN_DIR/gemini_bridge_mcp.py"
ok "Copied gemini_bridge.py and gemini_bridge_mcp.py → $PLUGIN_DIR/"

# ── 5. API key setup ──────────────────────────────────────────────────────────
ENV_DEST="$PLUGIN_DIR/.env"

if [ -f "$ENV_DEST" ]; then
    warn ".env already exists at $ENV_DEST — skipping (won't overwrite your API key)"
else
    if [ -f ".env" ]; then
        cp .env "$ENV_DEST"
        ok "Copied .env → $ENV_DEST"
    else
        echo ""
        echo "Enter your Gemini API key (get one at https://aistudio.google.com/apikey):"
        read -r -s API_KEY
        if [ -z "$API_KEY" ]; then
            warn "No API key entered. Edit $ENV_DEST manually and set GEMINI_API_KEY."
            cp .env.example "$ENV_DEST"
        else
            cp .env.example "$ENV_DEST"
            if [[ "$OSTYPE" == "darwin"* ]]; then
                sed -i '' "s/your_api_key_here/$API_KEY/" "$ENV_DEST"
            else
                sed -i "s/your_api_key_here/$API_KEY/" "$ENV_DEST"
            fi
            ok "API key saved to $ENV_DEST"
        fi
    fi
fi

# ── 6. Install slash commands ─────────────────────────────────────────────────
# Update paths in commands to point to the installed script location
for FILE in commands/*.md skills/*.md; do
    DEST="$COMMANDS_DIR/$(basename "$FILE")"
    sed "s|C:/Users/stealthy/.claude/plugins/gemini_bridge.py|$PLUGIN_DIR/gemini_bridge.py|g" "$FILE" > "$DEST"
    ok "Installed $(basename "$FILE") → $COMMANDS_DIR/"
done

# ── 7. Add CLAUDE.md workflow instructions ────────────────────────────────────
MARKER="# Gemini Bridge — Plugin Global"

if grep -qF "$MARKER" "$CLAUDE_MD" 2>/dev/null; then
    warn "CLAUDE.md already contains Gemini Bridge instructions — skipping"
else
    cat >> "$CLAUDE_MD" << CLAUDEMD

$MARKER

## Ce que c'est
Un pont vers Gemini installé globalement. Disponible dans **tous les projets** sans rien copier.

- Script : \`$PLUGIN_DIR/gemini_bridge.py\`
- Tiers disponibles :
  - \`--tier lite\`  → rapide, économique
  - \`--tier flash\` → équilibré
  - \`--tier pro\`   → défaut — raisonnement max (100 req/jour)

## Commande d'appel
\`\`\`bash
python $PLUGIN_DIR/gemini_bridge.py --tier pro "ta question"
\`\`\`

## Workflow obligatoire pour toute tâche complexe

Pour toute tâche impliquant de la génération ou modification de code, suis ces 5 étapes **sans exception** :

1. **Analyser** la demande entièrement avant d'agir.
2. **Rédiger** le plan ou le code en mémoire — ne pas encore toucher les fichiers.
3. **OBLIGATOIRE — Soumettre à Gemini** :
\`\`\`bash
python $PLUGIN_DIR/gemini_bridge.py --tier pro "Analyse ce plan/code en expert. Cherche : 1) failles logiques ou de sécurité, 2) hallucinations ou hypothèses incorrectes, 3) optimisations possibles. Sois critique et précis. Voici le plan/code : [TON CONTENU]"
\`\`\`
4. **Lire la réponse Gemini** et corriger le plan. Signaler brièvement à l'utilisateur ce que Gemini a trouvé.
5. **Exécuter** la tâche finale avec le plan corrigé et validé.

**Si le script échoue** (clé manquante, erreur réseau) : signaler à l'utilisateur et attendre ses instructions.
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
    warn "'claude' CLI not found in PATH. Register manually with:"
    warn "  claude mcp add --scope user gemini-mcp-connect -- $PYTHON_BIN $MCP_SCRIPT"
fi

# ── 9. Test the installation ──────────────────────────────────────────────────
echo ""
echo "Testing MCP server..."
if python3 "$MCP_SCRIPT" --help 2>/dev/null || python3 -c "
import sys
sys.argv = ['gemini_bridge_mcp']
exec(open('$MCP_SCRIPT').read().split('if __name__')[0])
print('OK')
" 2>/dev/null; then
    ok "MCP server loads successfully"
else
    # Simpler test: just check imports
    if python3 -c "from mcp.server.fastmcp import FastMCP; from google import genai; print('OK')" 2>/dev/null; then
        ok "Dependencies OK — MCP server ready"
    else
        warn "Some dependencies may be missing. Run: pip install mcp google-genai"
    fi
fi

echo ""
echo "Available tools in Claude Code (via MCP):"
echo "  query_gemini(prompt, tier)     — query Gemini directly"
echo "  review_code(code, language)    — critical code review"
echo "  validate_plan(plan)            — validate implementation plan"
echo "  gemini_status()                — check daily quota"
echo ""
echo "Available slash commands:"
echo "  /gemini <prompt>               — query Gemini"
echo "  /gemini-status                 — check daily quota"
echo "  /review-code <code>            — critical code review"
echo "  /validate-plan <plan>          — validate implementation plan"
echo ""
echo "Done. Restart Claude Code to load the MCP server."

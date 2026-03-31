# gemini-mcp-connect installer for Windows
# Usage: .\install.ps1

$ErrorActionPreference = "Stop"

$PluginDir   = "$env:USERPROFILE\.claude\plugins"
$CommandsDir = "$env:USERPROFILE\.claude\commands"
$ClaudeMd    = "$env:USERPROFILE\.claude\CLAUDE.md"

function Ok   { param($msg) Write-Host "✓ $msg" -ForegroundColor Green }
function Warn { param($msg) Write-Host "! $msg" -ForegroundColor Yellow }
function Err  { param($msg) Write-Host "✗ $msg" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "Installing gemini-mcp-connect plugin for Claude Code..." -ForegroundColor Cyan
Write-Host ""

# ── 1. Check Python ───────────────────────────────────────────────────────────
try {
    $pyVersion = python --version 2>&1
    Ok "Python found: $pyVersion"
} catch {
    Err "Python is required. Install it from https://python.org"
}

# ── 2. Install Python dependencies ────────────────────────────────────────────
Write-Host "Installing Python dependencies..."
python -m pip install --quiet google-genai python-dotenv mcp
Ok "google-genai, python-dotenv, mcp installed"

# ── 3. Create directories ─────────────────────────────────────────────────────
New-Item -ItemType Directory -Force -Path $PluginDir   | Out-Null
New-Item -ItemType Directory -Force -Path $CommandsDir | Out-Null
Ok "Directories ready: $PluginDir"

# ── 4. Copy core script ───────────────────────────────────────────────────────
Copy-Item "gemini_bridge.py"     "$PluginDir\gemini_bridge.py"     -Force
Copy-Item "gemini_bridge_mcp.py" "$PluginDir\gemini_bridge_mcp.py" -Force
Ok "Copied gemini_bridge.py and gemini_bridge_mcp.py → $PluginDir\"

# ── 5. API key setup ──────────────────────────────────────────────────────────
$EnvDest = "$PluginDir\.env"

if (Test-Path $EnvDest) {
    Warn ".env already exists at $EnvDest — skipping (won't overwrite your API key)"
} elseif (Test-Path ".env") {
    Copy-Item ".env" $EnvDest -Force
    Ok "Copied .env → $EnvDest"
} else {
    Write-Host ""
    Write-Host "Enter your Gemini API key (get one at https://aistudio.google.com/apikey):"
    $ApiKey = Read-Host -AsSecureString
    $ApiKeyPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($ApiKey)
    )

    $EnvContent = Get-Content ".env.example" -Raw
    if ($ApiKeyPlain) {
        $EnvContent = $EnvContent -replace "your_api_key_here", $ApiKeyPlain
        Ok "API key configured"
    } else {
        Warn "No API key entered. Edit $EnvDest manually and set GEMINI_API_KEY."
    }
    Set-Content -Path $EnvDest -Value $EnvContent
}

# ── 6. Install slash commands & skills ───────────────────────────────────────
$ScriptPath = "$PluginDir\gemini_bridge.py" -replace "\\", "/"

foreach ($File in (Get-ChildItem "commands\*.md", "skills\*.md")) {
    $Dest = "$CommandsDir\$($File.Name)"
    $Content = Get-Content $File.FullName -Raw
    $Content = $Content -replace [regex]::Escape("C:/Users/stealthy/.claude/plugins/gemini_bridge.py"), $ScriptPath
    Set-Content -Path $Dest -Value $Content
    Ok "Installed $($File.Name) → $CommandsDir\"
}

# ── 7. Add CLAUDE.md workflow instructions ────────────────────────────────────
$Marker = "# Gemini Bridge — Plugin Global"

if ((Test-Path $ClaudeMd) -and (Get-Content $ClaudeMd -Raw) -match [regex]::Escape($Marker)) {
    Warn "CLAUDE.md already contains Gemini Bridge instructions — skipping"
} else {
    $Workflow = @"

$Marker

## Ce que c'est
Un pont vers Gemini installé globalement. Disponible dans **tous les projets** sans rien copier.

- Script : ``$ScriptPath``
- Tiers disponibles :
  - ``--tier lite``  → rapide, économique
  - ``--tier flash`` → équilibré
  - ``--tier pro``   → défaut — raisonnement max (100 req/jour)

## Commande d'appel
``````bash
python $ScriptPath --tier pro "ta question"
``````

## Workflow obligatoire pour toute tâche complexe

Pour toute tâche impliquant de la génération ou modification de code, suis ces 5 étapes **sans exception** :

1. **Analyser** la demande entièrement avant d'agir.
2. **Rédiger** le plan ou le code en mémoire — ne pas encore toucher les fichiers.
3. **OBLIGATOIRE — Soumettre à Gemini** :
``````bash
python $ScriptPath --tier pro "Analyse ce plan/code en expert. Cherche : 1) failles logiques ou de sécurité, 2) hallucinations ou hypothèses incorrectes, 3) optimisations possibles. Sois critique et précis. Voici le plan/code : [TON CONTENU]"
``````
4. **Lire la réponse Gemini** et corriger le plan. Signaler brièvement à l'utilisateur ce que Gemini a trouvé.
5. **Exécuter** la tâche finale avec le plan corrigé et validé.

**Si le script échoue** (clé manquante, erreur réseau) : signaler à l'utilisateur et attendre ses instructions.
"@
    Add-Content -Path $ClaudeMd -Value $Workflow
    Ok "Gemini Bridge workflow added to $ClaudeMd"
}

# ── 8. Register MCP server with Claude Code ───────────────────────────────────
$PythonBin = (Get-Command python -ErrorAction SilentlyContinue)?.Source ?? "python"
$McpScript = "$PluginDir\gemini_bridge_mcp.py"

Write-Host ""
Write-Host "Registering MCP server with Claude Code..."
$ClaudeCmd = Get-Command claude -ErrorAction SilentlyContinue
if ($ClaudeCmd) {
    & claude mcp add --scope user gemini-mcp-connect -- $PythonBin $McpScript
    Ok "MCP server registered: gemini-mcp-connect"
} else {
    Warn "'claude' CLI not found. Register manually with:"
    Warn "  claude mcp add --scope user gemini-mcp-connect -- $PythonBin $McpScript"
}

# ── 9. Test dependencies ──────────────────────────────────────────────────────
Write-Host ""
Write-Host "Testing dependencies..."
$TestResult = python -c "from mcp.server.fastmcp import FastMCP; from google import genai; print('OK')" 2>&1
if ($TestResult -eq "OK") {
    Ok "All dependencies OK — MCP server ready"
} else {
    Warn "Dependency check failed: $TestResult"
    Warn "Run: pip install mcp google-genai"
}

Write-Host ""
Write-Host "Available tools in Claude Code (via MCP):" -ForegroundColor Cyan
Write-Host "  query_gemini(prompt, tier)     — query Gemini directly"
Write-Host "  review_code(code, language)    — critical code review"
Write-Host "  validate_plan(plan)            — validate implementation plan"
Write-Host "  gemini_status()                — check daily quota"
Write-Host ""
Write-Host "Available slash commands:"
Write-Host "  /gemini <prompt>               — query Gemini"
Write-Host "  /gemini-status                 — check daily quota"
Write-Host "  /review-code <code>            — critical code review"
Write-Host "  /validate-plan <plan>          — validate implementation plan"
Write-Host ""
Write-Host "Done. Restart Claude Code to load the MCP server." -ForegroundColor Green

# gemini-mcp-connect installer for Windows
# Local:  .\install.ps1
# Remote: irm https://raw.githubusercontent.com/StealthyLabsHQ/gemini-mcp-connect/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

$RepoRaw     = "https://raw.githubusercontent.com/StealthyLabsHQ/gemini-mcp-connect/main"
$PluginDir   = "$env:USERPROFILE\.claude\plugins"
$CommandsDir = "$env:USERPROFILE\.claude\commands"
$ClaudeMd    = "$env:USERPROFILE\.claude\CLAUDE.md"

function Ok   { param($msg) Write-Host "v $msg" -ForegroundColor Green }
function Warn { param($msg) Write-Host "! $msg" -ForegroundColor Yellow }
function Err  { param($msg) Write-Host "x $msg" -ForegroundColor Red; exit 1 }

function Fetch {
    param($RemotePath, $DestPath)
    $url = "$RepoRaw/$RemotePath"
    Invoke-WebRequest -Uri $url -OutFile $DestPath -UseBasicParsing
}

# Detect remote mode
$Remote = -not (Test-Path "gemini_bridge_mcp.py")

Write-Host ""
Write-Host "Installing gemini-mcp-connect plugin for Claude Code..." -ForegroundColor Cyan
if ($Remote) { Write-Host "(remote mode — downloading files from GitHub)" }
else         { Write-Host "(local mode)" }
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
New-Item -ItemType Directory -Force -Path $PluginDir               | Out-Null
New-Item -ItemType Directory -Force -Path $CommandsDir             | Out-Null
New-Item -ItemType Directory -Force -Path "$CommandsDir\gemini"    | Out-Null
Ok "Directories ready"

# ── 4. Install core scripts ───────────────────────────────────────────────────
if ($Remote) {
    Fetch "gemini_bridge.py"     "$PluginDir\gemini_bridge.py"
    Fetch "gemini_bridge_mcp.py" "$PluginDir\gemini_bridge_mcp.py"
} else {
    Copy-Item "gemini_bridge.py"     "$PluginDir\gemini_bridge.py"     -Force
    Copy-Item "gemini_bridge_mcp.py" "$PluginDir\gemini_bridge_mcp.py" -Force
}
Ok "Core scripts → $PluginDir\"

# ── 5. API key setup ──────────────────────────────────────────────────────────
$EnvDest = "$PluginDir\.env"

if (Test-Path $EnvDest) {
    Warn ".env already exists at $EnvDest — skipping (won't overwrite your API key)"
} else {
    Write-Host ""
    Write-Host "Enter your Gemini API key (get one at https://aistudio.google.com/apikey):"
    $ApiKey = Read-Host -AsSecureString
    $ApiKeyPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($ApiKey)
    )
    if ($ApiKeyPlain) {
        Set-Content -Path $EnvDest -Value "GEMINI_API_KEY=$ApiKeyPlain"
        Ok "API key saved to $EnvDest"
    } else {
        Warn "No API key entered. Edit $EnvDest manually and set GEMINI_API_KEY."
        Set-Content -Path $EnvDest -Value "GEMINI_API_KEY=your_key_here"
    }
}

# ── 6. Install slash commands ─────────────────────────────────────────────────
$GeminiCommands = @("lite", "flash", "pro", "status", "review", "validate")

if ($Remote) {
    foreach ($Cmd in $GeminiCommands) {
        Fetch "commands/gemini/$Cmd.md" "$CommandsDir\gemini\$Cmd.md"
        Ok "Installed /gemini:$Cmd"
    }
    foreach ($Cmd in @("gemini", "gemini-status")) {
        try {
            Fetch "commands/$Cmd.md" "$CommandsDir\$Cmd.md"
            Ok "Installed /$Cmd"
        } catch { }
    }
} else {
    $ScriptPath = "$PluginDir\gemini_bridge.py" -replace "\\", "/"
    foreach ($File in (Get-ChildItem "commands\*.md", "skills\*.md" -ErrorAction SilentlyContinue)) {
        $Content = (Get-Content $File.FullName -Raw) -replace [regex]::Escape("C:/Users/stealthy/.claude/plugins/gemini_bridge.py"), $ScriptPath
        Set-Content -Path "$CommandsDir\$($File.Name)" -Value $Content
        Ok "Installed $($File.Name)"
    }
    foreach ($File in (Get-ChildItem "commands\gemini\*.md" -ErrorAction SilentlyContinue)) {
        Copy-Item $File.FullName "$CommandsDir\gemini\$($File.Name)" -Force
        Ok "Installed gemini\$($File.Name)"
    }
}

# ── 7. Add CLAUDE.md workflow instructions ────────────────────────────────────
$Marker = "# Gemini Bridge — Plugin Global"

if ((Test-Path $ClaudeMd) -and (Get-Content $ClaudeMd -Raw) -match [regex]::Escape($Marker)) {
    Warn "CLAUDE.md already contains Gemini Bridge instructions — skipping"
} else {
    $Workflow = @"

$Marker

## Ce que c'est
Un serveur MCP natif connecte a Google Gemini. Disponible dans **tous les projets** automatiquement.

- MCP server : ``gemini-mcp-connect``
- Tiers disponibles via le parametre ``tier`` :
  - ``lite``  -> rapide, economique
  - ``flash`` -> equilibre
  - ``pro``   -> defaut - raisonnement max (100 req/jour)

## Workflow obligatoire pour toute tache complexe

1. Analyser la demande entierement avant d'agir.
2. Rediger le plan ou le code en memoire.
3. OBLIGATOIRE - Soumettre a Gemini via le tool MCP :
   - Pour un plan : appelle validate_plan(plan="[TON PLAN]")
   - Pour du code : appelle review_code(code="[TON CODE]", language="python")
4. Lire la reponse Gemini et corriger le plan.
5. Executer la tache finale avec le plan corrige et valide.

**Si le tool MCP echoue** : signaler a l'utilisateur et attendre ses instructions.
"@
    Add-Content -Path $ClaudeMd -Value $Workflow
    Ok "Gemini Bridge workflow added to $ClaudeMd"
}

# ── 8. Register MCP server with Claude Code ───────────────────────────────────
$PythonBin = (Get-Command python -ErrorAction SilentlyContinue).Source
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

# ── 9. Verify dependencies ────────────────────────────────────────────────────
Write-Host ""
$TestResult = python -c "from mcp.server.fastmcp import FastMCP; from google import genai; print('OK')" 2>&1
if ($TestResult -eq "OK") {
    Ok "All dependencies OK"
} else {
    Warn "Dependency check failed. Run: pip install mcp google-genai python-dotenv"
}

Write-Host ""
Write-Host "Available tools in Claude Code (via MCP):" -ForegroundColor Cyan
Write-Host "  query_gemini(prompt, tier)     - query Gemini directly"
Write-Host "  review_code(code, language)    - critical code review"
Write-Host "  validate_plan(plan)            - validate implementation plan"
Write-Host "  gemini_status()                - check daily quota"
Write-Host ""
Write-Host "Available slash commands:"
Write-Host "  /gemini:lite <prompt>          - Gemini Lite (fast, economical)"
Write-Host "  /gemini:flash <prompt>         - Gemini Flash (balanced)"
Write-Host "  /gemini:pro <prompt>           - Gemini Pro (max reasoning, 100 req/day)"
Write-Host "  /gemini:status                 - check daily quota"
Write-Host "  /gemini:review <file|code>     - critical code review"
Write-Host "  /gemini:validate <plan>        - validate plan before execution"
Write-Host ""
Write-Host "Done. Restart Claude Code to load the MCP server." -ForegroundColor Green

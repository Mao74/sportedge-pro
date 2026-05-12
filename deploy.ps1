<#
.SYNOPSIS
    SportEdge Pro - one-shot deploy / update orchestrator (Windows -> Hostinger VPS).

.DESCRIPTION
    Esegue da locale tutta la sequenza:
      1. git add/commit/push (opzionale, solo se ci sono modifiche)
      2. ssh sul VPS, git pull, docker compose up -d --build
      3. smoke check (https + /api/v1/health)

    Compatibile con Windows PowerShell 5.1 e PowerShell 7+.
    Pensato per un singolo utente, single environment (prod).
    Lo script NON deve mai essere committato con segreti dentro:
    la .env.prod vive solo sul VPS, mai sul laptop.

.PARAMETER Mode
    init    Primo deploy. Clone se manca, scaffolda .env.prod da example,
            build + start, mostra logs.
    update  (default) git push locale, ssh pull, docker compose up -d --build,
            smoke check.
    logs    Tail dei logs di backend + frontend.
    status  docker compose ps + curl /api/v1/health.
    rollback git reset --hard HEAD~1 sul VPS + rebuild (ultima risorsa).

.PARAMETER Message
    Commit message da usare quando ci sono modifiche locali non committate.

.PARAMETER NoCommit
    Salta git add/commit/push locale. Utile se hai gia' pushato a mano.

.EXAMPLE
    .\deploy.ps1
    # update mode: push -> pull -> rebuild -> smoke

.EXAMPLE
    .\deploy.ps1 -Mode init
    # primo deploy: clone, scaffold .env.prod, up --build

.NOTES
    Configurazione SSH consigliata in ~/.ssh/config:

        Host sportedge-vps
            HostName 187.124.0.133
            User root
            IdentityFile ~/.ssh/id_ed25519
            ServerAliveInterval 30
#>

[CmdletBinding()]
param(
    [ValidateSet('init', 'update', 'logs', 'status', 'rollback')]
    [string]$Mode = 'update',

    [string]$Message = "",

    [switch]$NoCommit
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrEmpty($Message)) {
    $Message = "deploy: " + (Get-Date -Format 'yyyy-MM-dd HH:mm')
}

# --- Config ---------------------------------------------------------------
$VpsHost     = 'sportedge-vps'                          # ~/.ssh/config alias
$VpsFallback = 'root@187.124.0.133'                     # se l'alias non c'e'
$RemoteDir   = '/srv/sportedge'
$RepoUrl     = 'https://github.com/Mao74/sportedge-pro.git'
$PublicUrl   = 'https://sportedge.mauriziomolinari.cloud'
$ComposeCmd  = 'docker compose --env-file .env.prod -f docker-compose.prod.yml'

# --- Helpers --------------------------------------------------------------
function Write-Step {
    param([string]$msg)
    Write-Host ""
    Write-Host ("==> " + $msg) -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$msg)
    Write-Host ("  OK " + $msg) -ForegroundColor Green
}

function Write-Warn2 {
    param([string]$msg)
    Write-Host ("  !  " + $msg) -ForegroundColor Yellow
}

function Write-Err2 {
    param([string]$msg)
    Write-Host ("  X  " + $msg) -ForegroundColor Red
}

function Test-SshHost {
    param([string]$Target)
    # PS 5.1 promuove stderr di comandi nativi a errore terminating se
    # ErrorActionPreference=Stop, quindi rilassiamo il contesto qui.
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & ssh -o BatchMode=yes -o ConnectTimeout=5 $Target 'true' 2>&1 | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Resolve-VpsTarget {
    if (Test-SshHost $VpsHost) {
        Write-Ok ("SSH alias '" + $VpsHost + "' raggiungibile")
        return $VpsHost
    }
    Write-Warn2 ("Alias '" + $VpsHost + "' non configurato - uso " + $VpsFallback)
    if (-not (Test-SshHost $VpsFallback)) {
        throw "Impossibile connettersi al VPS ($VpsFallback). Verifica chiave SSH e firewall."
    }
    return $VpsFallback
}

# Invoke a remote command (single shell line). Use Invoke-RemoteScript for
# multi-line bash scripts.
function Invoke-Remote {
    param(
        [string]$Target,
        [string]$Command,
        [switch]$Interactive
    )
    if ($Interactive) {
        & ssh -t $Target $Command
    } else {
        & ssh $Target $Command
    }
    if ($LASTEXITCODE -ne 0) {
        throw ("Comando remoto fallito (exit " + $LASTEXITCODE + "): " + $Command)
    }
}

# Pipe a multi-line bash script to 'bash -s' over SSH. Each $Lines element
# becomes a separate line. Uses LF endings (not CRLF) for bash safety.
function Invoke-RemoteScript {
    param(
        [string]$Target,
        [string[]]$Lines,
        [switch]$AllowFail   # set $script:RemoteExitCode without throwing
    )
    $script = ($Lines -join "`n") + "`n"
    $script | & ssh $Target 'bash -s'
    $script:RemoteExitCode = $LASTEXITCODE
    if (-not $AllowFail -and $LASTEXITCODE -ne 0) {
        throw ("Script remoto fallito (exit " + $LASTEXITCODE + ")")
    }
}

function Invoke-LocalGitPush {
    Write-Step "Git locale"
    $status = & git status --porcelain
    if ([string]::IsNullOrWhiteSpace($status)) {
        Write-Ok "Working tree pulito, niente da committare"
    } else {
        Write-Host $status
        if ($NoCommit) {
            Write-Warn2 "Modifiche non committate ma -NoCommit attivo, skippo"
        } else {
            Write-Host ("  Commit message: " + $Message) -ForegroundColor DarkGray
            & git add -A
            & git commit -m $Message
            if ($LASTEXITCODE -ne 0) { throw "git commit fallito" }
            Write-Ok "Commit creato"
        }
    }

    $branch = (& git rev-parse --abbrev-ref HEAD).Trim()
    Write-Host ("  Push branch '" + $branch + "' a origin...") -ForegroundColor DarkGray
    & git push origin $branch
    if ($LASTEXITCODE -ne 0) { throw "git push fallito" }
    Write-Ok "Push completato"
}

function Test-SmokeCheck {
    Write-Step "Smoke check pubblico"
    try {
        $resp = Invoke-WebRequest -Uri ($PublicUrl + "/api/v1/health") -UseBasicParsing -TimeoutSec 15
        if ($resp.StatusCode -eq 200) {
            Write-Ok "/api/v1/health -> 200"
            Write-Host ("    " + $resp.Content) -ForegroundColor DarkGray
        } else {
            Write-Warn2 ("/api/v1/health -> HTTP " + $resp.StatusCode)
        }
    } catch {
        Write-Err2 ("Smoke fallito: " + $_.Exception.Message)
        Write-Warn2 "Il backend potrebbe essere ancora in migration. Riprova tra 10s o usa -Mode logs."
    }
}

# --- Mode handlers --------------------------------------------------------
function Invoke-ModeInit {
    param([string]$Target)

    Write-Step ("Init: primo deploy su " + $Target)

    $lines = @(
        'set -eu',
        "mkdir -p $RemoteDir",
        "cd $RemoteDir",
        '',
        'if [ -d .git ]; then',
        '    echo "[init] repo gia clonato, skip clone"',
        '    git fetch --all --quiet',
        '    git reset --hard origin/main',
        'else',
        "    echo '[init] clono $RepoUrl ...'",
        "    git clone $RepoUrl .",
        'fi',
        '',
        'mkdir -p obsidian-vault',
        '',
        'if [ ! -f .env.prod ]; then',
        '    echo "[init] copio .env.prod.example -> .env.prod"',
        '    cp .env.prod.example .env.prod',
        '    chmod 600 .env.prod',
        '    echo ""',
        '    echo "!! ATTENZIONE: .env.prod NON e configurata."',
        '    echo "!! Apri /srv/sportedge/.env.prod e compila i campi required,"',
        '    echo "!! poi rilancia .\deploy.ps1 -Mode update."',
        '    echo ""',
        '    echo "Suggerimenti per i secret:"',
        '    echo "  POSTGRES_PASSWORD=$(openssl rand -base64 32)"',
        '    echo "  JWT_SECRET_KEY=$(openssl rand -hex 48)"',
        '    exit 42',
        'fi'
    )

    Invoke-RemoteScript -Target $Target -Lines $lines -AllowFail
    if ($script:RemoteExitCode -eq 42) {
        Write-Warn2 ".env.prod appena creata, compila i campi required sul VPS e poi ri-esegui."
        Write-Host ""
        Write-Host ("  ssh " + $Target) -ForegroundColor DarkGray
        Write-Host ("  nano " + $RemoteDir + "/.env.prod") -ForegroundColor DarkGray
        Write-Host "  exit" -ForegroundColor DarkGray
        Write-Host "  .\deploy.ps1 -Mode update" -ForegroundColor DarkGray
        return
    } elseif ($script:RemoteExitCode -ne 0) {
        throw ("Init remoto fallito (exit " + $script:RemoteExitCode + ")")
    }

    Write-Step "Build + start stack (puo richiedere 2-3 minuti la prima volta)"
    Invoke-Remote -Target $Target -Command ("cd " + $RemoteDir + "; " + $ComposeCmd + " up -d --build")
    Write-Ok "Stack avviato"

    Write-Step "Status containers"
    Invoke-Remote -Target $Target -Command ("cd " + $RemoteDir + "; " + $ComposeCmd + " ps")

    Write-Step "Logs backend (Ctrl-C per uscire)"
    Invoke-Remote -Target $Target -Command ("cd " + $RemoteDir + "; " + $ComposeCmd + " logs -f --tail=80 backend") -Interactive
}

function Invoke-ModeUpdate {
    param([string]$Target)

    if (-not $NoCommit) {
        Invoke-LocalGitPush
    } else {
        Write-Step "Git locale: skip (-NoCommit)"
    }

    Write-Step ("Pull + rebuild su " + $Target)
    $lines = @(
        'set -eu',
        "cd $RemoteDir",
        'git pull --ff-only',
        "$ComposeCmd up -d --build",
        "$ComposeCmd ps"
    )
    Invoke-RemoteScript -Target $Target -Lines $lines

    Start-Sleep -Seconds 5
    Test-SmokeCheck
}

function Invoke-ModeLogs {
    param([string]$Target)
    Write-Step "Tail logs (backend + frontend, Ctrl-C per uscire)"
    Invoke-Remote -Target $Target -Command ("cd " + $RemoteDir + "; " + $ComposeCmd + " logs -f --tail=120 backend frontend") -Interactive
}

function Invoke-ModeStatus {
    param([string]$Target)
    Write-Step "Containers"
    Invoke-Remote -Target $Target -Command ("cd " + $RemoteDir + "; " + $ComposeCmd + " ps")

    Write-Step "Disk usage"
    Invoke-Remote -Target $Target -Command "df -h /; docker system df"

    Test-SmokeCheck
}

function Invoke-ModeRollback {
    param([string]$Target)
    Write-Step "Rollback: HEAD~1 + rebuild (richiede conferma)"
    Write-Warn2 "Questo fara' 'git reset --hard HEAD~1' sul VPS e ribuildera'."
    $confirm = Read-Host "Sei sicuro? (digita 'yes' per procedere)"
    if ($confirm -ne 'yes') {
        Write-Host "Annullato." -ForegroundColor DarkGray
        return
    }
    $lines = @(
        'set -eu',
        "cd $RemoteDir",
        'git reset --hard HEAD~1',
        "$ComposeCmd up -d --build",
        "$ComposeCmd ps"
    )
    Invoke-RemoteScript -Target $Target -Lines $lines
    Start-Sleep -Seconds 5
    Test-SmokeCheck
}

# --- Main -----------------------------------------------------------------
Write-Host ""
Write-Host ("SportEdge Pro - deploy.ps1 (mode: " + $Mode + ")") -ForegroundColor Magenta
Write-Host "============================================" -ForegroundColor Magenta

$target = Resolve-VpsTarget

switch ($Mode) {
    'init'     { Invoke-ModeInit     -Target $target }
    'update'   { Invoke-ModeUpdate   -Target $target }
    'logs'     { Invoke-ModeLogs     -Target $target }
    'status'   { Invoke-ModeStatus   -Target $target }
    'rollback' { Invoke-ModeRollback -Target $target }
}

Write-Host ""
Write-Host "Done." -ForegroundColor Magenta

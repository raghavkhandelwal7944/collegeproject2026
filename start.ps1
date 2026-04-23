# ============================================================
#  Firewall LLM - Windows Launcher
#  Starts: MySQL, MongoDB, Redis, Ollama, Backend, Frontend
# ============================================================

$ROOT = $PSScriptRoot

function Write-OK([string]$msg)  { Write-Host "  [OK]  $msg" -ForegroundColor Green  }
function Write-INF([string]$msg) { Write-Host "  [..] $msg"  -ForegroundColor Cyan   }
function Write-WRN([string]$msg) { Write-Host "  [!!] $msg"  -ForegroundColor Yellow }
function Write-ERR([string]$msg) { Write-Host "  [XX] $msg"  -ForegroundColor Red    }

function Test-Port([int]$Port) {
    $c = New-Object Net.Sockets.TcpClient
    try {
        $c.Connect("127.0.0.1", $Port)
        $c.Close()
        return $true
    } catch {
        return $false
    }
}

function Wait-ForPort([int]$Port, [int]$MaxSeconds = 20, [string]$Label = "service") {
    $waited = 0
    while ($waited -lt $MaxSeconds) {
        Start-Sleep -Seconds 1
        $waited++
        if (Test-Port $Port) {
            Write-OK "$Label ready on port $Port."
            return $true
        }
    }
    Write-WRN "$Label not ready on port $Port within ${MaxSeconds}s."
    return $false
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Magenta
Write-Host "   Firewall LLM - Starting All Services"    -ForegroundColor Magenta
Write-Host "============================================" -ForegroundColor Magenta
Write-Host ""

Set-Location $ROOT

# -- 1. Prerequisites -----------------------------------------
Write-INF "Checking prerequisites..."
foreach ($cmd in @("python", "npm", "ollama")) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Write-ERR "'$cmd' not found in PATH. Please install it and re-run."
        exit 1
    }
}
Write-OK "python, npm, ollama found."

# -- 2. MySQL -------------------------------------------------
Write-INF "Checking MySQL (port 3306)..."
if (Test-Port 3306) {
    Write-OK "MySQL already running."
} else {
    $svc = Get-Service -Name "MySQL*" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($svc) {
        Start-Service $svc.Name -ErrorAction SilentlyContinue
        $null = Wait-ForPort -Port 3306 -MaxSeconds 15 -Label "MySQL"
    } else {
        Write-WRN "MySQL not found. Backend database features will fail."
    }
}

# -- 3. MongoDB -----------------------------------------------
Write-INF "Checking MongoDB (port 27017)..."
if (Test-Port 27017) {
    Write-OK "MongoDB already running."
} else {
    $svc = Get-Service -Name "MongoDB*" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($svc) {
        Start-Service $svc.Name -ErrorAction SilentlyContinue
        $null = Wait-ForPort -Port 27017 -MaxSeconds 15 -Label "MongoDB"
    } else {
        Write-WRN "MongoDB not found. Conversation history will be unavailable."
    }
}

# -- 4. Redis -------------------------------------------------
Write-INF "Checking Redis (port 6379)..."
$redisUp = Test-Port 6379
if ($redisUp) {
    Write-OK "Redis already running."
}

if (-not $redisUp) {
    $redisSvc = Get-Service -Name "Redis*", "Memurai*" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($redisSvc) {
        Start-Service $redisSvc.Name -ErrorAction SilentlyContinue
        $redisUp = Wait-ForPort -Port 6379 -MaxSeconds 15 -Label "Redis"
    }
}

if (-not $redisUp) {
    $redisBin = $null
    $rbCmd = Get-Command "redis-server" -ErrorAction SilentlyContinue
    if ($rbCmd) {
        $redisBin = $rbCmd.Source
    } else {
        $candidates = @(
            "C:\Program Files\Redis\redis-server.exe",
            "C:\Redis\redis-server.exe",
            "$env:LOCALAPPDATA\Programs\Redis\redis-server.exe"
        )
        foreach ($c in $candidates) {
            if (Test-Path $c) {
                $redisBin = $c
                break
            }
        }
    }
    if ($redisBin) {
        Start-Process -FilePath $redisBin -WindowStyle Minimized
        $redisUp = Wait-ForPort -Port 6379 -MaxSeconds 15 -Label "Redis"
    }
}

if (-not $redisUp) {
    if (Get-Command "wsl" -ErrorAction SilentlyContinue) {
        Write-INF "Trying Redis via WSL..."
        wsl -- redis-server --daemonize yes
        Start-Sleep -Seconds 2
        $redisUp = Test-Port 6379
        if ($redisUp) {
            Write-OK "Redis started via WSL."
        }
    }
}

if (-not $redisUp) {
    Write-WRN "Redis is not running. Token Vault + Semantic Cache will be DISABLED."
}

# -- 5. Ollama ------------------------------------------------
Write-INF "Checking Ollama (port 11434)..."
$ollamaUp = Test-Port 11434
if ($ollamaUp) {
    Write-OK "Ollama already running - skipping start."
} else {
    Write-INF "Starting Ollama..."
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "ollama serve" -WindowStyle Minimized
    $ollamaUp = Wait-ForPort -Port 11434 -MaxSeconds 20 -Label "Ollama"
    if (-not $ollamaUp) {
        Write-WRN "Ollama did not start in time. Chat may fail."
    }
}

# -- 6. Python venv + backend deps ----------------------------
Write-INF "Setting up Python virtual environment..."
if (-not (Test-Path "$ROOT\venv")) {
    Write-INF "Creating venv..."
    python -m venv "$ROOT\venv"
}
Write-INF "Installing / verifying backend dependencies..."
& "$ROOT\venv\Scripts\pip.exe" install -q -r "$ROOT\requirements.txt"
Write-OK "Backend dependencies ready."

# -- 7. Frontend node_modules ---------------------------------
Write-INF "Checking frontend node_modules..."
if (-not (Test-Path "$ROOT\frontend-react\node_modules")) {
    Write-INF "Running npm install in frontend-react..."
    Push-Location "$ROOT\frontend-react"
    npm install
    Pop-Location
}
Write-OK "Frontend dependencies ready."

# -- 8. Launch Backend ----------------------------------------
Write-INF "Launching backend (uvicorn on :8000)..."
$backendCmd = "& '$ROOT\venv\Scripts\Activate.ps1'; Set-Location '$ROOT'; uvicorn backend.main:app --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd -WindowStyle Normal
Write-OK "Backend window opened."

Write-INF "Waiting 8s for backend to settle..."
Start-Sleep -Seconds 8

# -- 9. Launch Frontend ---------------------------------------
Write-INF "Launching frontend (Next.js on :3000)..."
$frontendCmd = "Set-Location '$ROOT\frontend-react'; `$env:NODE_OPTIONS='--max-old-space-size=512'; npm run dev"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd -WindowStyle Normal
Write-OK "Frontend window opened."

# -- Summary --------------------------------------------------
Write-Host ""
Write-Host "============================================" -ForegroundColor Magenta
Write-Host "   All services launched!"                   -ForegroundColor Magenta
Write-Host ""
Write-Host "   Frontend  ->  http://localhost:3000"      -ForegroundColor White
Write-Host "   Backend   ->  http://localhost:8000/docs" -ForegroundColor White
Write-Host "   Ollama    ->  http://localhost:11434"      -ForegroundColor White
if ($redisUp) {
    Write-Host "   Redis     ->  127.0.0.1:6379  [ON]"  -ForegroundColor Green
} else {
    Write-Host "   Redis     ->  not running   [OFF]" -ForegroundColor Yellow
}
Write-Host "============================================" -ForegroundColor Magenta

$ErrorActionPreference = "Stop"

$ProjectDir = "C:\Users\web_a\Documents\MarketPlace"
$DockerDesktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
$LogDir = Join-Path $ProjectDir "logs"
$LogFile = Join-Path $LogDir "autostart.log"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-Log {
    param([string] $Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -LiteralPath $LogFile -Value "[$timestamp] $Message"
}

Write-Log "Starting TTN Telegram bot autostart script."

if (-not (Test-Path -LiteralPath $DockerDesktop)) {
    Write-Log "Docker Desktop executable not found: $DockerDesktop"
    exit 1
}

Write-Log "Starting Docker Desktop."
Start-Process -FilePath $DockerDesktop -WindowStyle Hidden

function Test-DockerReady {
    $job = Start-Job -ScriptBlock {
        & docker.exe info --format "{{.ServerVersion}}" 2>$null
    }

    if (-not (Wait-Job -Job $job -Timeout 10)) {
        Stop-Job -Job $job -ErrorAction SilentlyContinue
        Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
        return $false
    }

    $serverVersion = (Receive-Job -Job $job -ErrorAction SilentlyContinue) -join ""
    Remove-Job -Job $job -Force -ErrorAction SilentlyContinue

    return $serverVersion -match "^\d+\.\d+"
}

$dockerReady = $false
$maxAttempts = 180
for ($i = 1; $i -le $maxAttempts; $i++) {
    if (Test-DockerReady) {
        $dockerReady = $true
        break
    }
    Write-Log "Docker Engine is not ready yet. Attempt $i of $maxAttempts."
    Start-Sleep -Seconds 5
}

if (-not $dockerReady) {
    Write-Log "Docker Engine did not become ready in time."
    exit 1
}

Set-Location -LiteralPath $ProjectDir

$localBotProcesses = Get-CimInstance Win32_Process -Filter "name = 'python.exe'" |
    Where-Object { $_.CommandLine -like '*-m ttn_bot.main*' }
foreach ($process in $localBotProcesses) {
    Write-Log "Stopping local TTN bot process $($process.ProcessId) before Docker start."
    Stop-Process -Id $process.ProcessId -Force
}

Write-Log "Running docker compose up -d --build ttn-bot."
cmd.exe /c "docker compose up -d --build ttn-bot > `"$LogDir\compose-up.log`" 2>&1"

if ($LASTEXITCODE -ne 0) {
    Write-Log "docker compose up -d --build ttn-bot failed with exit code $LASTEXITCODE."
    exit $LASTEXITCODE
}

Write-Log "TTN Telegram bot stack started successfully."

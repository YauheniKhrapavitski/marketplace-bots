$ErrorActionPreference = "Stop"

$ProjectDir = "C:\Users\web_a\Documents\MarketPlace"
Set-Location -LiteralPath $ProjectDir
docker compose down

$localBotProcesses = Get-CimInstance Win32_Process -Filter "name = 'python.exe'" |
    Where-Object { $_.CommandLine -like '*-m ttn_bot.main*' }
foreach ($process in $localBotProcesses) {
    Stop-Process -Id $process.ProcessId -Force
}

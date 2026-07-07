Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $PSScriptRoot)
$env:PYTHONPATH = (Get-Location).Path
$env:GEW_USE_MAIN_BROWSER_PROFILE = "true"
$env:DISCORD_MESSAGE_CONTENT_INTENT = "true"

$logDir = Join-Path (Get-Location) "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir "discord-bot-supervisor.log"

while ($true) {
    $startedAt = Get-Date
    "[$startedAt] starting worker Discord runtime" | Out-File -FilePath $logPath -Append -Encoding utf8
    & python -m discord.online
    $exitCode = $LASTEXITCODE
    $endedAt = Get-Date
    "[$endedAt] worker Discord runtime exited with code $exitCode" | Out-File -FilePath $logPath -Append -Encoding utf8
    if ($exitCode -eq 0) {
        break
    }
    Start-Sleep -Seconds 5
}

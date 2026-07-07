Set-Location (Split-Path -Parent $PSScriptRoot)
$env:PYTHONPATH = (Get-Location).Path
$env:GEW_USE_MAIN_BROWSER_PROFILE = "true"
$env:DISCORD_MESSAGE_CONTENT_INTENT = "true"
& (Join-Path $PSScriptRoot "run_discord_bot_forever.ps1")

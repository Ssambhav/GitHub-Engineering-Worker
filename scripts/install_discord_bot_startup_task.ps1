param(
    [string]$TaskName = "GitHubEngineeringWorkerDiscordBot"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$runner = Join-Path $PSScriptRoot "run_discord_bot_forever.ps1"
if (-not (Test-Path $runner)) {
    throw "Runner script not found: $runner"
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runner`""
$triggers = @(
    (New-ScheduledTaskTrigger -AtStartup),
    (New-ScheduledTaskTrigger -AtLogOn)
)
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $triggers `
    -Settings $settings `
    -Description "Runs the GitHub Engineering Worker Discord frontend against the shared runtime and restarts it after crashes or reboot." `
    -User $env:USERNAME `
    -Force | Out-Null

Write-Output "Registered scheduled task '$TaskName' for $repoRoot"

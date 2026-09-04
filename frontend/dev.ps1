# Panopticon Frontend Native PowerShell Dev Runner
# Bypasses cmd.exe subshell, Windows PATH bloat, and npm runner quirks

$ErrorActionPreference = "Stop"

$NodeCandidate = "C:\Program Files\nodejs\node.exe"
if (-not (Test-Path $NodeCandidate)) {
    $NodeCmd = Get-Command node -ErrorAction SilentlyContinue
    if ($NodeCmd) {
        $NodeCandidate = $NodeCmd.Source
    }
}

if (-not (Test-Path $NodeCandidate)) {
    Write-Error "Node.js executable was not found. Please verify Node.js is installed at C:\Program Files\nodejs\node.exe"
    exit 1
}

$ViteJs = Join-Path $PSScriptRoot "node_modules\vite\bin\vite.js"
if (-not (Test-Path $ViteJs)) {
    Write-Error "Vite entrypoint not found at $ViteJs. Run 'npm install' first."
    exit 1
}

Write-Host "Starting Panopticon Observatory with Node ($NodeCandidate)..." -ForegroundColor Cyan
& $NodeCandidate $ViteJs @args

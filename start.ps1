param(
    [int]$Port = 8000,
    [switch]$TrustedLocal
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
Get-Command uv -ErrorAction Stop | Out-Null
Write-Host "VerdictPilot learning workspace: http://127.0.0.1:$Port"
$serverArguments = @('run','--frozen','verdictpilot','serve','--port',"$Port")
if ($TrustedLocal) { $serverArguments += '--trusted-local' }
& uv @serverArguments
exit $LASTEXITCODE

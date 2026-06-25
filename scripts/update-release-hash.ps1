param(
    [string]$ExePath = "dist\WindowsSpotlightDownloader.exe",
    [string]$OutputPath = "dist\SHA256SUMS.txt"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $ExePath)) {
    throw "Executable not found: $ExePath"
}

$hash = Get-FileHash -Algorithm SHA256 -LiteralPath $ExePath
$line = "$($hash.Hash)  $([System.IO.Path]::GetFileName($ExePath))"

$outputDir = Split-Path -Parent $OutputPath
if ($outputDir) {
    New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
}

Set-Content -LiteralPath $OutputPath -Value $line -Encoding UTF8
Write-Output $line

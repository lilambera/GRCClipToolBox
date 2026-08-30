# Download ffmpeg and deno into the project root (not tracked by git).
# Run from repo root:  powershell -ExecutionPolicy Bypass -File scripts/setup_deps.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$FfmpegDir = Join-Path $Root "ffmpeg\bin"
$DenoDir = Join-Path $Root "deno"

New-Item -ItemType Directory -Force -Path $FfmpegDir, $DenoDir | Out-Null

# ffmpeg (BtbN GPL build via GitHub releases)
$FfmpegZip = Join-Path $env:TEMP "ffmpeg-win64-gpl.zip"
$FfmpegUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"

if (-not (Test-Path (Join-Path $FfmpegDir "ffmpeg.exe"))) {
    Write-Host "Downloading ffmpeg..."
    Invoke-WebRequest -Uri $FfmpegUrl -OutFile $FfmpegZip
    $ExtractDir = Join-Path $env:TEMP "ffmpeg-extract"
    if (Test-Path $ExtractDir) { Remove-Item $ExtractDir -Recurse -Force }
    Expand-Archive -Path $FfmpegZip -DestinationPath $ExtractDir
    $BinSrc = Get-ChildItem -Path $ExtractDir -Recurse -Filter "ffmpeg.exe" |
        Select-Object -First 1 |
        ForEach-Object { $_.Directory.FullName }
    Copy-Item (Join-Path $BinSrc "ffmpeg.exe") $FfmpegDir
    Copy-Item (Join-Path $BinSrc "ffprobe.exe") $FfmpegDir
    Remove-Item $FfmpegZip, $ExtractDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "ffmpeg ready: $FfmpegDir"
} else {
    Write-Host "ffmpeg already present, skipping."
}

# deno
$DenoExe = Join-Path $DenoDir "deno.exe"
$DenoUrl = "https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip"

if (-not (Test-Path $DenoExe)) {
    Write-Host "Downloading deno..."
    $DenoZip = Join-Path $env:TEMP "deno-win.zip"
    Invoke-WebRequest -Uri $DenoUrl -OutFile $DenoZip
    Expand-Archive -Path $DenoZip -DestinationPath $DenoDir -Force
    Remove-Item $DenoZip -Force -ErrorAction SilentlyContinue
    Write-Host "deno ready: $DenoExe"
} else {
    Write-Host "deno already present, skipping."
}

Write-Host "Done. Copy config.json.example to config.json if you have not already."

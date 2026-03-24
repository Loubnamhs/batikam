param(
    [string]$Version = "dev"
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

$appName = "BatikamRenove"
$distDir = Join-Path $projectRoot "dist"
$releaseDir = Join-Path $distDir "release"
$bundleDir = Join-Path $distDir $appName
$packageDir = Join-Path $releaseDir "$appName-$Version"
$zipPath = Join-Path $releaseDir "$appName-Windows-$Version.zip"

$pyiArgs = @(
    "--noconfirm",
    "--clean",
    "--windowed",
    "--onedir",
    "--name", $appName,
    "--add-data", "assets;assets",
    "--add-data", "templates;templates",
    "--add-data", "company_info.json;.",
    "--collect-all", "docx",
    "--collect-all", "docxtpl",
    "--collect-all", "reportlab",
    "app/main.py"
)

$iconPath = Join-Path $projectRoot "assets/logo.ico"
if (Test-Path $iconPath) {
    $pyiArgs = @("--icon", $iconPath) + $pyiArgs
}

python -m PyInstaller @pyiArgs

if (-not (Test-Path $bundleDir)) {
    throw "Dossier de build introuvable: $bundleDir"
}

New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
if (Test-Path $packageDir) {
    Remove-Item -Recurse -Force $packageDir
}
New-Item -ItemType Directory -Force -Path $packageDir | Out-Null

Copy-Item -Recurse -Force (Join-Path $bundleDir "*") $packageDir

# Garantit un fichier editable au premier lancement.
$companyInfoPath = Join-Path $packageDir "company_info.json"
if (-not (Test-Path $companyInfoPath) -and (Test-Path "company_info.json")) {
    Copy-Item -Force "company_info.json" $companyInfoPath
}

if (Test-Path $zipPath) {
    Remove-Item -Force $zipPath
}
Compress-Archive -Path (Join-Path $packageDir "*") -DestinationPath $zipPath -Force

Write-Host ""
Write-Host "Build Windows terminée."
Write-Host "Package dossier : $packageDir"
Write-Host "Archive ZIP    : $zipPath"

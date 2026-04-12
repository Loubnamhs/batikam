param(
    [string]$Version = "1.0.0",
    [switch]$SkipInstaller   # passer -SkipInstaller pour ne pas appeler Inno Setup
)

$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$projectRoot = Get-Location

# ── Chemins ──────────────────────────────────────────────────────────────────
$appName    = "BatikamRenove"
$distDir    = Join-Path $projectRoot "dist"
$bundleDir  = Join-Path $distDir $appName         # dossier onedir PyInstaller
$releaseDir = Join-Path $distDir "release"
$iconPath   = Join-Path $projectRoot "assets\logo.ico"
$issTemplate= Join-Path $PSScriptRoot "installer.iss"
$issBuilt   = Join-Path $distDir "installer_built.iss"

$venvPython = Join-Path $projectRoot "venv\Scripts\python.exe"
$pythonExe  = if (Test-Path $venvPython) { $venvPython } else { "python" }

# ── 0. Générer logo.ico si absent ────────────────────────────────────────────
if (-not (Test-Path $iconPath)) {
    Write-Host ">> Génération de logo.ico..."
    & $pythonExe -c @"
from PIL import Image
import struct, io, pathlib

def make_ico(src, dst, sizes):
    img = Image.open(src).convert('RGBA')
    frames = [(s, img.resize((s,s), Image.LANCZOS)) for s in sizes]
    pngs   = []
    for s, f in frames:
        buf = io.BytesIO(); f.save(buf,'PNG'); pngs.append((s, buf.getvalue()))
    n = len(pngs)
    header = struct.pack('<HHH', 0, 1, n)
    off = 6 + 16*n
    dirs = b''
    for s, data in pngs:
        w = s if s < 256 else 0
        dirs += struct.pack('<BBBBHHII', w, w, 0, 0, 1, 32, len(data), off)
        off  += len(data)
    with open(dst,'wb') as f:
        f.write(header + dirs)
        for _, data in pngs: f.write(data)

src = next((p for p in ['assets/logo1.png','assets/logo_principal1.png','assets/logo.png'] if pathlib.Path(p).exists()), None)
if src:
    make_ico(src, 'assets/logo.ico', [16,24,32,48,64,128,256])
    print('ICO:', pathlib.Path('assets/logo.ico').stat().st_size, 'bytes')
else:
    print('WARN: aucun PNG source trouvé, icône non générée')
"@
}

# ── 1. PyInstaller — build onedir ─────────────────────────────────────────────
Write-Host ""
Write-Host ">> PyInstaller — build $appName v$Version..."

$pyiArgs = @(
    "--noconfirm", "--clean",
    "--windowed",
    "--onedir",
    "--name",     $appName,
    "--add-data", "assets;assets",
    "--add-data", "app/ui/theme.qss;app/ui",
    "--add-data", "company_info.json;.",
    "--collect-all", "qfluentwidgets",
    "--collect-all", "docx",
    "--collect-all", "docxtpl",
    "--collect-all", "reportlab",
    "app/main.py"
)

if (Test-Path $iconPath) {
    $pyiArgs = @("--icon", $iconPath) + $pyiArgs
}

& $pythonExe -m PyInstaller @pyiArgs
if ($LASTEXITCODE -ne 0) { throw "PyInstaller a échoué (code $LASTEXITCODE)" }

if (-not (Test-Path $bundleDir)) {
    throw "Dossier bundle introuvable après build : $bundleDir"
}

# ── 2a. Fix PyInstaller 6.x — copier python3XX.dll à la racine ───────────────
# Windows cherche python312.dll à côté de l'exe, pas dans _internal/
$internalDir = Join-Path $bundleDir "_internal"
Get-ChildItem $internalDir -Filter "python*.dll" | ForEach-Object {
    $dest = Join-Path $bundleDir $_.Name
    if (-not (Test-Path $dest)) {
        Copy-Item $_.FullName $dest
        Write-Host "   Copié : $($_.Name) → racine bundle"
    }
}

# ── 2b. Copier les templates si présents ──────────────────────────────────────
$templatesDir = Join-Path $projectRoot "templates"
if (Test-Path $templatesDir) {
    $dst = Join-Path $bundleDir "templates"
    robocopy $templatesDir $dst /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
}

Write-Host ">> Bundle prêt : $bundleDir"

# ── 3. Inno Setup — génération de l'installeur ────────────────────────────────
if (-not $SkipInstaller) {
    # Chercher ISCC.exe
    $isccPaths = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe",
        "C:\Program Files (x86)\Inno Setup 5\ISCC.exe"
    )
    $iscc = $isccPaths | Where-Object { Test-Path $_ } | Select-Object -First 1

    if (-not $iscc) {
        Write-Host ""
        Write-Host "INFO : Inno Setup introuvable — l'installeur .exe ne sera pas généré."
        Write-Host "       Installez Inno Setup depuis https://jrsoftware.org/isinfo.php"
        Write-Host "       puis relancez ce script."
    } else {
        Write-Host ""
        Write-Host ">> Inno Setup — génération de l'installeur..."
        New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null

        # Remplacement des variables dans le template .iss
        $issContent = Get-Content $issTemplate -Raw -Encoding UTF8
        $issContent = $issContent `
            -replace '@VERSION@',   $Version `
            -replace '@SOURCEDIR@', $bundleDir `
            -replace '@ICONFILE@',  $iconPath `
            -replace '@OUTPUTDIR@', $releaseDir

        Set-Content -Path $issBuilt -Value $issContent -Encoding UTF8

        & $iscc $issBuilt
        if ($LASTEXITCODE -ne 0) { throw "Inno Setup a échoué (code $LASTEXITCODE)" }

        $setupExe = Get-ChildItem $releaseDir -Filter "BatikamRenove-Setup-*.exe" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        Write-Host ""
        Write-Host "Installeur généré : $($setupExe.FullName)"
    }
} else {
    Write-Host ">> -SkipInstaller : étape Inno Setup ignorée."
}

Write-Host ""
Write-Host "========================================"
Write-Host " Build terminé — Batikam Renove v$Version"
Write-Host "========================================"
Write-Host " Bundle  : $bundleDir"
if (Test-Path $releaseDir) {
    Write-Host " Release : $releaseDir"
}

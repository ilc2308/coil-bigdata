# ============================================================
# COIL Big Data — Script de inicio local (Windows PowerShell)
# Arranca la API (FastAPI) y el dashboard (Streamlit) en
# terminales separados sin necesidad de Docker.
#
# Uso:
#   .\start_local.ps1
#   .\start_local.ps1 -ApiOnly       # solo la API
#   .\start_local.ps1 -WebOnly       # solo Streamlit
#   .\start_local.ps1 -RunTests      # ejecutar tests
# ============================================================

param (
    [switch]$ApiOnly,
    [switch]$WebOnly,
    [switch]$RunTests
)

$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " COIL Big Data — Sistema de Ordenes Medicas" -ForegroundColor Cyan
Write-Host " Modo: LOCAL | Python + FastAPI + Streamlit" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# ── Verificar .env ──────────────────────────────────────────
if (-not (Test-Path ".env")) {
    Write-Host "`n[CONFIG] .env no encontrado. Creando desde .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "  > .env creado. Edita las variables si es necesario." -ForegroundColor Green
}

# ── Verificar Python ──────────────────────────────────────────
$python = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python 3") {
            $python = $cmd
            Write-Host "`n[OK] Python encontrado: $ver ($cmd)" -ForegroundColor Green
            break
        }
    } catch {}
}

if (-not $python) {
    Write-Host "`n[ERROR] Python 3 no encontrado en PATH." -ForegroundColor Red
    Write-Host "  Instala Python 3.11+ desde https://python.org" -ForegroundColor Yellow
    exit 1
}

# ── Verificar/Instalar dependencias ─────────────────────────
Write-Host "`n[DEPS] Verificando dependencias..." -ForegroundColor Yellow
$fastapi_check = & $python -c "import fastapi" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Instalando requirements.txt..." -ForegroundColor Yellow
    & $python -m pip install -r requirements.txt --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Falló la instalación de dependencias." -ForegroundColor Red
        exit 1
    }
    Write-Host "  > Dependencias instaladas correctamente." -ForegroundColor Green
} else {
    Write-Host "  > Dependencias OK." -ForegroundColor Green
}

# ── Crear directorios necesarios ────────────────────────────
New-Item -ItemType Directory -Path "uploads", "output\gold_curated", "output\quarantine" -Force | Out-Null

# ── Ejecutar tests ──────────────────────────────────────────
if ($RunTests) {
    Write-Host "`n[TESTS] Ejecutando suite de tests..." -ForegroundColor Yellow
    Write-Host "  Tests unitarios (glosa_parser + rule_engine):" -ForegroundColor Gray
    & $python -m pytest tests/test_components.py -v
    Write-Host "`n  Tests de integración (API):" -ForegroundColor Gray
    & $python -m pytest tests/test_api_integration.py -v --tb=short
    exit $LASTEXITCODE
}

# ── Iniciar API ──────────────────────────────────────────────
if (-not $WebOnly) {
    Write-Host "`n[API] Iniciando FastAPI en http://localhost:8000 ..." -ForegroundColor Yellow
    Write-Host "      Documentacion: http://localhost:8000/docs" -ForegroundColor Gray
    $apiJob = Start-Process -FilePath $python -ArgumentList @(
        "-m", "uvicorn", "api.main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload"
    ) -WorkingDirectory $ProjectRoot -PassThru -NoNewWindow

    # Esperar a que la API esté lista
    Write-Host "  Esperando que la API arranque..." -ForegroundColor Gray
    $attempts = 0
    $ready = $false
    while ($attempts -lt 15 -and -not $ready) {
        Start-Sleep -Seconds 2
        $attempts++
        try {
            $null = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 2 -ErrorAction Stop
            $ready = $true
            Write-Host "  > API lista!" -ForegroundColor Green
        } catch {
            Write-Host "  . Intento $attempts/15..." -ForegroundColor Gray
        }
    }
    if (-not $ready) {
        Write-Host "  [WARN] La API no respondio en tiempo. Verifica los logs." -ForegroundColor Yellow
    }
}

# ── Iniciar Streamlit ────────────────────────────────────────
if (-not $ApiOnly) {
    Write-Host "`n[WEB] Iniciando Streamlit en http://localhost:8501 ..." -ForegroundColor Yellow
    $stJob = Start-Process -FilePath $python -ArgumentList @(
        "-m", "streamlit", "run", "app\main.py",
        "--server.port=8501",
        "--server.address=localhost"
    ) -WorkingDirectory $ProjectRoot -PassThru -NoNewWindow

    Start-Sleep -Seconds 3
    Write-Host "  > Dashboard listo en http://localhost:8501" -ForegroundColor Green
    Write-Host "    Usuario: admin | Contrasena: coil2026" -ForegroundColor Gray
}

# ── Mensaje final ────────────────────────────────────────────
Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host " COIL en ejecucion:" -ForegroundColor Cyan
if (-not $WebOnly) {
    Write-Host "   API REST:  http://localhost:8000" -ForegroundColor White
    Write-Host "   Swagger:   http://localhost:8000/docs" -ForegroundColor White
}
if (-not $ApiOnly) {
    Write-Host "   Dashboard: http://localhost:8501" -ForegroundColor White
}
Write-Host "`n  Presiona Ctrl+C para detener los servicios." -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan

# Mantener el script activo
try {
    while ($true) { Start-Sleep -Seconds 10 }
} finally {
    Write-Host "`nDeteniendo servicios..." -ForegroundColor Yellow
    if ($apiJob -and -not $apiJob.HasExited) { Stop-Process -Id $apiJob.Id -Force -ErrorAction SilentlyContinue }
    if ($stJob  -and -not $stJob.HasExited)  { Stop-Process -Id $stJob.Id  -Force -ErrorAction SilentlyContinue }
    Write-Host "Servicios detenidos." -ForegroundColor Green
}

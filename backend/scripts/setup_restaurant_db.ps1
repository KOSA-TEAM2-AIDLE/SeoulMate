param(
    [switch]$Resume,
    [switch]$SkipEmbeddings,
    [switch]$ValidateOnly,
    [switch]$VerifyOnly,
    [int]$BatchSize = 100
)

$ErrorActionPreference = "Stop"
$BackendDir = Split-Path -Parent $PSScriptRoot
Set-Location $BackendDir

if (-not (Test-Path -LiteralPath ".env")) {
    throw "backend\.env가 없습니다. .env.example을 복사하고 DB 및 OPENAI_API_KEY 값을 입력하세요."
}

$ArgsList = @("scripts/setup_restaurant_db.py", "--batch-size", "$BatchSize")
if (-not $Resume -and -not $ValidateOnly -and -not $VerifyOnly) {
    $ArgsList += @("--reset", "--yes")
}
if ($SkipEmbeddings) { $ArgsList += "--skip-embeddings" }
if ($ValidateOnly) { $ArgsList += "--validate-only" }
if ($VerifyOnly) { $ArgsList += "--verify-only" }

$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $VenvPython) {
    & $VenvPython @ArgsList
} elseif (Get-Command uv -ErrorAction SilentlyContinue) {
    & uv run python @ArgsList
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python @ArgsList
} else {
    throw "Python을 찾을 수 없습니다. Python 3.12+ 또는 uv를 설치하세요."
}

if ($LASTEXITCODE -ne 0) {
    throw "식당 DB 구축 실패 (exit code: $LASTEXITCODE)"
}


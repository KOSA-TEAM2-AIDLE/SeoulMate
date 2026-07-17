$projectRoot = Split-Path -Parent $PSScriptRoot

Push-Location $projectRoot
try {
    uv run uvicorn main:app `
        --host 127.0.0.1 `
        --port 8000 `
        --reload `
        --reload-dir $projectRoot `
        --reload-exclude ".uv-cache/*" `
        --reload-exclude ".venv/*" `
        --reload-exclude ".test-venv/*" `
        --reload-exclude "**/__pycache__/*"
}
finally {
    Pop-Location
}

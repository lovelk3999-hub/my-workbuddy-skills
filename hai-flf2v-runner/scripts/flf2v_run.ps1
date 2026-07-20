param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$Args
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Runner = Join-Path $Root "scripts\flf2v_run.py"

if (-not (Test-Path -LiteralPath $Python)) {
  throw "Missing local Python venv: $Python. Run: py -3.12 -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements-hai.txt"
}

& $Python $Runner @Args
exit $LASTEXITCODE

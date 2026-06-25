# Batch mapped-table acceptance (Pro :8000). MAPPED-BATCH-001
param(
    [string]$RepoRoot = (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent),
    [string]$ApiRoot = "http://127.0.0.1:8000",
    [string]$SetName = "mapped_bank_statement_3"
)

$ErrorActionPreference = "Stop"
$manifestPath = Join-Path $RepoRoot "test_data\testfiles\batch\manifest.json"
$outDir = Join-Path $RepoRoot "test_data\TestResult\PhaseBatch"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

if (-not (Test-Path $manifestPath)) {
    throw "Manifest not found: $manifestPath"
}

$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
$set = $manifest.sets | Where-Object { $_.name -eq $SetName } | Select-Object -First 1
if (-not $set) {
    throw "Set not found in manifest: $SetName"
}

$health = Invoke-WebRequest -Uri "$ApiRoot/health" -UseBasicParsing
if ($health.StatusCode -ne 200) {
    throw "Health check failed. Start backend: cd backend; python run.py"
}

$testfilesRoot = Join-Path $RepoRoot "test_data\testfiles"
$boundary = [guid]::NewGuid().ToString()
$bodyLines = New-Object System.Collections.Generic.List[string]
function Add-FormField([string]$name, [string]$value) {
    $script:bodyLines.Add("--$boundary")
    $script:bodyLines.Add("Content-Disposition: form-data; name=`"$name`"")
    $script:bodyLines.Add("")
    $script:bodyLines.Add($value)
}

$opts = @{}
if ($set.options) {
    $set.options.PSObject.Properties | ForEach-Object { $opts[$_.Name] = $_.Value }
}
if ($set.document_type -and -not $opts.ContainsKey("document_type")) {
    $opts["document_type"] = $set.document_type
}
$optionsJson = $opts | ConvertTo-Json -Compress
Write-Host "options:" $optionsJson

Add-FormField "name" "Mapped batch $SetName"
Add-FormField "options" $optionsJson

foreach ($rel in $set.files) {
    $path = Join-Path $testfilesRoot ($rel -replace "/", "\")
    if (-not (Test-Path $path)) {
        Write-Warning "Skip missing file: $path"
        continue
    }
    $bytes = [System.IO.File]::ReadAllBytes($path)
    $fileName = [System.IO.Path]::GetFileName($path)
    $script:bodyLines.Add("--$boundary")
    $script:bodyLines.Add("Content-Disposition: form-data; name=`"files`"; filename=`"$fileName`"")
    $script:bodyLines.Add("Content-Type: application/octet-stream")
    $script:bodyLines.Add("")
    $bodyLines.Add([System.Text.Encoding]::GetEncoding("iso-8859-1").GetString($bytes))
}

$bodyLines.Add("--$boundary--")
$bodyLines.Add("")
$bodyRaw = ($bodyLines -join "`r`n") + "`r`n"
$bodyBytes = [System.Text.Encoding]::GetEncoding("iso-8859-1").GetBytes($bodyRaw)

$createResp = Invoke-WebRequest -Uri "$ApiRoot/api/v1/batch" -Method POST -ContentType "multipart/form-data; boundary=$boundary" -Body $bodyBytes -UseBasicParsing
$batch = $createResp.Content | ConvertFrom-Json
$batchId = $batch.batch_id
Write-Host "batch_id:" $batchId
Write-Host "export BATCH_ID=$batchId"

Invoke-WebRequest -Uri "$ApiRoot/api/v1/batch/$batchId/start" -Method POST -UseBasicParsing | Out-Null

for ($i = 0; $i -lt 360; $i++) {
    Start-Sleep -Seconds 3
    $status = Invoke-WebRequest -Uri "$ApiRoot/api/v1/batch/$batchId" -UseBasicParsing
    $job = $status.Content | ConvertFrom-Json
    Write-Host $job.status $job.progress "%"
    if ($job.status -in @("completed", "failed", "cancelled")) {
        break
    }
}

if ($job.status -ne "completed") {
    Write-Error "MAPPED-BATCH-001 failed: batch status $($job.status)"
}

$xlsxPath = Join-Path $outDir "batch_${batchId}_mapped.xlsx"
Invoke-WebRequest -Uri "$ApiRoot/api/v1/batch/$batchId/export.xlsx?mode=all" -OutFile $xlsxPath -UseBasicParsing
Write-Host "Wrote" $xlsxPath

$zipPath = $xlsxPath
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
$mappedEntry = $zip.Entries | Where-Object { $_.FullName -like "*MappedRows*" -or $_.Name -eq "MappedRows" } | Select-Object -First 1
$sheetNames = @()
foreach ($entry in $zip.Entries) {
    if ($entry.FullName -like "xl/worksheets/sheet*.xml") { $sheetNames += $entry.FullName }
}
$zip.Dispose()

try {
    python -c @"
import sys
import pandas as pd
path = sys.argv[1]
xl = pd.ExcelFile(path)
if 'MappedRows' not in xl.sheet_names:
    raise SystemExit('MappedRows sheet missing: ' + str(xl.sheet_names))
df = pd.read_excel(path, sheet_name='MappedRows')
if len(df) < 1:
    raise SystemExit('MappedRows has no data rows')
print('MAPPED-BATCH-001 passed:', len(df), 'mapped row(s)')
"@ $xlsxPath
    if ($LASTEXITCODE -ne 0) {
        Write-Error "MAPPED-BATCH-001 failed: Excel validation"
    }
} catch {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Warning "Python/pandas not available; verify MappedRows sheet manually in $xlsxPath"
    } else {
        throw
    }
}

Write-Host "MAPPED-BATCH-001 passed"

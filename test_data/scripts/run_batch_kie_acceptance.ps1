# Batch KIE acceptance (Pro :8000). Outputs under test_data/TestResult/PhaseBatch/
param(
    [string]$RepoRoot = (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent),
    [string]$ApiRoot = "http://127.0.0.1:8000",
    [string]$SetName = "kie_invoice_6"
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

# Merge set-level document_type into options (API only reads options JSON).
$opts = @{}
if ($set.options) {
    $set.options.PSObject.Properties | ForEach-Object { $opts[$_.Name] = $_.Value }
}
if ($set.document_type -and -not $opts.ContainsKey("document_type")) {
    $opts["document_type"] = $set.document_type
}
if (-not $opts.ContainsKey("enable_kie")) {
    $opts["enable_kie"] = $true
}
$optionsJson = $opts | ConvertTo-Json -Compress
Write-Host "options:" $optionsJson

Add-FormField "name" "Cloud batch $SetName"
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

$csvPath = Join-Path $outDir "batch_${batchId}_kie.csv"
Invoke-WebRequest -Uri "$ApiRoot/api/v1/batch/$batchId/export.csv?mode=kie" -OutFile $csvPath -UseBasicParsing
Write-Host "Wrote" $csvPath

$resultsPath = Join-Path $outDir "batch_${batchId}_results.json"
$results = Invoke-WebRequest -Uri "$ApiRoot/api/v1/batch/$batchId/results" -UseBasicParsing
$results.Content | Set-Content -Path $resultsPath -Encoding UTF8
Write-Host "Wrote" $resultsPath

$csvRows = Import-Csv $csvPath
$hitCount = @($csvRows | Where-Object { $_.kie_production_hit -eq "True" }).Count
$totalRows = $csvRows.Count
Write-Host "kie_production_hit:" "$hitCount/$totalRows"
if ($hitCount -lt $totalRows) {
    Write-Host "Per-task CSV summary:"
    foreach ($row in $csvRows) {
        Write-Host ("  {0}: status={1} kie_stage={2} hit={3} fields={4}" -f `
            $row.file_name, $row.status, $row.kie_stage, $row.kie_production_hit, $row.kie_fields_count)
    }
    if (Test-Path $resultsPath) {
        try {
            $parsed = Get-Content $resultsPath -Raw | ConvertFrom-Json
            foreach ($task in @($parsed.results)) {
                $q = $task.result.quality
                if ($q) {
                    Write-Host ("  result {0}: reason={1}" -f $task.file_name, $q.kie_production_reason)
                }
            }
        } catch {
            Write-Warning "Could not parse results JSON for kie_production_reason"
        }
    }
    $skipped = @($csvRows | Where-Object { $_.kie_stage -eq "skipped_doc_type" }).Count
    if ($skipped -gt 0) {
        Write-Error "BATCH-002 failed: $skipped task(s) skipped_doc_type (check options.document_type in manifest/script)"
    }
    Write-Host "Hint: curl -s $ApiRoot/health | python3 -m json.tool | grep -A5 kie"
    Write-Error "BATCH-002 failed: kie_production_hit $hitCount/$totalRows"
}

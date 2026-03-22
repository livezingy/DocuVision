# Manual Test Script Example (Windows PowerShell)
# Usage: .\example_test_script.ps1

$API_BASE = "http://localhost:8000/api/v1"

Write-Host "=========================================="
Write-Host "DocuVision Manual Test Script"
Write-Host "=========================================="
Write-Host ""

# Test 1: Health Check
Write-Host "[Test 1] Health Check"
try {
    $response = Invoke-RestMethod -Uri "$API_BASE/../health" -Method Get
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
}
Write-Host ""

# Test 2: OCR Test
Write-Host "[Test 2] OCR Text Extraction"
$testFile = "images\scanned\scanned_page_01.jpg"
if (Test-Path $testFile) {
    try {
        $form = @{
            file = Get-Item $testFile
        }
        $response = Invoke-RestMethod -Uri "$API_BASE/ocr" -Method Post -Form $form
        $response | ConvertTo-Json -Depth 10
    } catch {
        Write-Host "Error: $_" -ForegroundColor Red
    }
} else {
    Write-Host "Skip: Test file not found ($testFile)" -ForegroundColor Yellow
}
Write-Host ""

# Test 3: Template List
Write-Host "[Test 3] Template List"
try {
    $response = Invoke-RestMethod -Uri "$API_BASE/templates" -Method Get
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
}
Write-Host ""

# Test 4: Invoice Template Match
Write-Host "[Test 4] Invoice Template Match"
try {
    $body = @{
        text = "Invoice Number: INV-2024-001`nInvoice Date: 2024-01-15`nTotal Amount: `$1,234.56`nVendor: ABC Company`nCustomer: XYZ Company"
    }
    $response = Invoke-RestMethod -Uri "$API_BASE/templates/match" -Method Post -Body $body
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
}
Write-Host ""

Write-Host "=========================================="
Write-Host "Test Completed"
Write-Host "=========================================="


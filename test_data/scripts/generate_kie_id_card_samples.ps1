# Generate synthetic Chinese ID card KIE samples (02~04). Windows + .NET Drawing.
# Layout: dynamic label column + id_number on second line; self-check before save.
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

function U([string]$b64) { [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($b64)) }

$OutDir = (Resolve-Path (Join-Path $PSScriptRoot "..\testfiles\images\kie")).Path
$CardW, $CardH = 860, 540
$LabelX = 40
$PhotoX = 650
$PhotoW = 180
$ContentRight = $PhotoX - 16
$MinGap = 16

$RowLabels = @(
    (U("5aeT5ZCN")),
    (U("5Ye655Sf")),
    (U("5L2P5Z2A")),
    (U("5pyJ5pWI5pyf6ZmQ")),
    (U("562+5Y+R5py65YWz")),
    (U("5YWs5rCR6Lqr5Lu95Y+356CB"))
)

$Samples = @(
    @{
        File = "id_card_sample_02.jpg"; Variant = "clear"
        Name = U("5byg5Lyf"); IdNumber = "110101199001011234"
        Dob = U("MTk5MOW5tDAx5pyIMDHml6U="); Address = U("5YyX5Lqs5biC5Lic5Z+O5Yy65rWL6K+V6LevMeWPtw==")
        Expiration = "2030.01.01-2040.01.01"; Authority = U("5YyX5Lqs5biC5YWs5a6J5bGA5Lic5Z+O5YiG5bGA")
    },
    @{
        File = "id_card_sample_03.jpg"; Variant = "tilted_compressed"
        Name = U("5p2O6Iqz"); IdNumber = "32010219880515231X"
        Dob = U("MTk4OOW5tDA15pyIMTXml6U="); Address = U("5rGf6IuP55yB5Y2X5Lqs5biC546E5q2m5Yy656S66IyD6KGX6YGTODjlj7c=")
        Expiration = "2025.05.15-2035.05.15"; Authority = U("5Y2X5Lqs5biC5YWs5a6J5bGA546E5q2m5YiG5bGA")
    },
    @{
        File = "id_card_sample_04.jpg"; Variant = "blurred"
        Name = U("546L5by6"); IdNumber = "440105199203073456"
        Dob = U("MTk5MuW5tDAz5pyIMDfml6U="); Address = U("5bm/5Lic55yB5bm/5bee5biC5aSp5rKz5Yy66aqM5pS25aSn6YGTMTAw5Y+3")
        Expiration = "2022.03.07-2032.03.07"; Authority = U("5bm/5bee5biC5YWs5a6J5bGA5aSp5rKz5YiG5bGA")
    }
)

function Get-Font($size, [switch]$Bold) {
    $style = if ($Bold) { [System.Drawing.FontStyle]::Bold } else { [System.Drawing.FontStyle]::Regular }
    foreach ($name in @("Microsoft YaHei UI", "Microsoft YaHei", "SimHei", "Arial")) {
        try { return New-Object System.Drawing.Font($name, $size, $style) } catch {}
    }
    return New-Object System.Drawing.Font("Arial", $size, $style)
}

function Measure-TextBox($g, [string]$text, $font, [int]$x, [int]$y) {
    $size = $g.MeasureString($text, $font)
    $w = [int][Math]::Ceiling($size.Width)
    $h = [int][Math]::Ceiling($size.Height)
    return @{ L = $x; T = $y; R = $x + $w; B = $y + $h; W = $w; H = $h }
}

function Test-BoxOverlap($a, $b, [int]$margin = 2) {
    return -not (($a.R + $margin -le $b.L) -or ($b.R + $margin -le $a.L) -or ($a.B + $margin -le $b.T) -or ($b.B + $margin -le $a.T))
}

function Get-LayoutPlan($data, $fonts) {
    $bmp = New-Object System.Drawing.Bitmap 1, 1
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $maxLabelW = 0
    foreach ($lbl in $RowLabels) {
        $w = [int][Math]::Ceiling(($g.MeasureString($lbl, $fonts.Label)).Width)
        if ($w -gt $maxLabelW) { $maxLabelW = $w }
    }
    $valueX = $LabelX + $maxLabelW + $MinGap
    $g.Dispose(); $bmp.Dispose()

    $blocks = @()
    $y = 90
    $photo = @{ L = $PhotoX; T = 86; R = $PhotoX + $PhotoW; B = 86 + 228 }

    $bmp2 = New-Object System.Drawing.Bitmap 1, 1
    $g = [System.Drawing.Graphics]::FromImage($bmp2)
    $pairs = @(
        @("name", (U("5aeT5ZCN")), $data.Name, $fonts.Value, 14),
        @("dob", (U("5Ye655Sf")), $data.Dob, $fonts.Value, 14),
        @("address", (U("5L2P5Z2A")), $data.Address, $fonts.Small, 18),
        @("expiration", (U("5pyJ5pWI5pyf6ZmQ")), $data.Expiration, $fonts.Small, 14),
        @("authority", (U("562+5Y+R5py65YWz")), $data.Authority, $fonts.Small, 20)
    )
    foreach ($p in $pairs) {
        $lb = Measure-TextBox $g $p[1] $fonts.Label $LabelX $y
        $vb = Measure-TextBox $g $p[2] $p[3] $valueX $y
        $blocks += @{ Field = $p[0]; Role = "label"; Box = $lb }
        $blocks += @{ Field = $p[0]; Role = "value"; Box = $vb }
        $y = [Math]::Max($lb.B, $vb.B) + $p[4]
    }
    $idLabel = U("5YWs5rCR6Lqr5Lu95Y+356CB")
    $lb = Measure-TextBox $g $idLabel $fonts.Label $LabelX $y
    $blocks += @{ Field = "id_number"; Role = "label"; Box = $lb }
    $idY = $lb.B + 8
    $vb = Measure-TextBox $g $data.IdNumber $fonts.IdNumber $LabelX $idY
    $blocks += @{ Field = "id_number"; Role = "value"; Box = $vb }
    $g.Dispose(); $bmp2.Dispose()

    $errors = @()
    foreach ($b in $blocks) {
        if ($b.Role -eq "value" -and $b.Box.R -gt $ContentRight) {
            $errors += "$($b.Field) value exceeds content column (right=$($b.Box.R), max=$ContentRight)"
        }
        if (Test-BoxOverlap $b.Box $photo) {
            $errors += "$($b.Field) $($b.Role) overlaps photo"
        }
    }
    $byField = $blocks | Group-Object Field
    foreach ($gItem in $byField) {
        $lbl = ($gItem.Group | Where-Object { $_.Role -eq "label" } | Select-Object -First 1)
        $val = ($gItem.Group | Where-Object { $_.Role -eq "value" } | Select-Object -First 1)
        if ($lbl -and $val -and $val.Box.L -lt ($lbl.Box.R + $MinGap - 2)) {
            $errors += "$($gItem.Name) label/value too close"
        }
        if ($lbl -and $val -and (Test-BoxOverlap $lbl.Box $val.Box)) {
            $errors += "$($gItem.Name) label/value overlap"
        }
    }
    return @{ ValueX = $valueX; Errors = $errors }
}

function New-IdCardBitmap($data, $fonts, [int]$valueX) {
    $bmp = New-Object System.Drawing.Bitmap $CardW, $CardH
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
    $g.Clear([System.Drawing.Color]::FromArgb(61, 126, 184))

    $penLight = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(69, 137, 196))
    for ($yy = 0; $yy -lt $CardH; $yy += 6) { $g.DrawLine($penLight, 0, $yy, $CardW, $yy) }
    for ($xx = 0; $xx -lt $CardW; $xx += 8) { $g.DrawLine($penLight, $xx, 0, $xx, $CardH) }

    $white = [System.Drawing.Brushes]::White
    $labelBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(232, 244, 255))
    $sf = New-Object System.Drawing.StringFormat
    $sf.Alignment = [System.Drawing.StringAlignment]::Center

    $g.DrawString((U("5Lit5Y2O5Lq65rCR5YWx5ZKM5Zu95bGF5rCR6Lqr5Lu96K+B")), $fonts.Title, $white, ($CardW / 2), 28, $sf)

    $photoY = 86
    $g.DrawRectangle([System.Drawing.Pens]::White, $PhotoX, $photoY, $PhotoW, 228)
    $g.FillRectangle([System.Drawing.Brushes]::LightSteelBlue, ($PhotoX + 1), ($photoY + 1), ($PhotoW - 2), 226)
    $g.DrawString((U("54Wn54mH")), $fonts.Label, [System.Drawing.Brushes]::DimGray, ($PhotoX + $PhotoW / 2), ($photoY + 114), $sf)

    $y = 90
    foreach ($row in @(
        @((U("5aeT5ZCN")), $data.Name, $fonts.Value, 14),
        @((U("5Ye655Sf")), $data.Dob, $fonts.Value, 14),
        @((U("5L2P5Z2A")), $data.Address, $fonts.Small, 18),
        @((U("5pyJ5pWI5pyf6ZmQ")), $data.Expiration, $fonts.Small, 14),
        @((U("562+5Y+R5py65YWz")), $data.Authority, $fonts.Small, 20)
    )) {
        $g.DrawString($row[0], $fonts.Label, $labelBrush, $LabelX, $y)
        $g.DrawString($row[1], $row[2], $white, $valueX, $y)
        $ls = $g.MeasureString($row[0], $fonts.Label)
        $vs = $g.MeasureString($row[1], $row[2])
        $y = $y + [Math]::Max([int]$ls.Height, [int]$vs.Height) + $row[3]
    }

    $idLabel = U("5YWs5rCR6Lqr5Lu95Y+356CB")
    $g.DrawString($idLabel, $fonts.Label, $labelBrush, $LabelX, $y)
    $ls = $g.MeasureString($idLabel, $fonts.Label)
    $g.DrawString($data.IdNumber, $fonts.IdNumber, $white, $LabelX, ($y + [int]$ls.Height + 8))

    $g.DrawString((U("5ZCI5oiQ5rWL6K+V5qC35L6LIMK3IOmdnuecn+WunuivgeS7tg==")), $fonts.Note, $labelBrush, ($CardW - 20), ($CardH - 16))
    $g.Dispose()
    return $bmp
}

function Apply-Variant($bmp, $variant) {
    if ($variant -eq "clear") { return $bmp }
    if ($variant -eq "tilted_compressed") {
        $rotated = New-Object System.Drawing.Bitmap $CardW, $CardH
        $rg = [System.Drawing.Graphics]::FromImage($rotated)
        $rg.Clear([System.Drawing.Color]::FromArgb(42, 42, 42))
        $rg.TranslateTransform($CardW / 2, $CardH / 2)
        $rg.RotateTransform(-4.5)
        $rg.TranslateTransform(-$CardW / 2, -$CardH / 2)
        $rg.DrawImage($bmp, 0, 0)
        $rg.Dispose(); $bmp.Dispose()
        return $rotated
    }
    if ($variant -eq "blurred") {
        $blur = New-Object System.Drawing.Bitmap $CardW, $CardH
        $bg = [System.Drawing.Graphics]::FromImage($blur)
        $bg.DrawImage($bmp, 1, 1); $bg.DrawImage($bmp, -1, 0); $bg.DrawImage($bmp, 0, -1); $bg.DrawImage($bmp, 0, 0)
        $bg.Dispose(); $bmp.Dispose()
        return $blur
    }
    return $bmp
}

$fonts = @{
    Title = Get-Font 28 -Bold
    Label = Get-Font 18
    Value = Get-Font 21 -Bold
    Small = Get-Font 17
    IdNumber = Get-Font 24 -Bold
    Note = Get-Font 11
}

$failed = $false
foreach ($spec in $Samples) {
    $plan = Get-LayoutPlan $spec $fonts
    if ($plan.Errors.Count -gt 0) {
        $failed = $true
        Write-Error "Layout validation failed for $($spec.File): $($plan.Errors -join '; ')"
    }
    $bmp = New-IdCardBitmap $spec $fonts $plan.ValueX
    $outBmp = Apply-Variant $bmp $spec.Variant
    $path = Join-Path $OutDir $spec.File
    $codec = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() | Where-Object { $_.MimeType -eq "image/jpeg" }
    $encParams = New-Object System.Drawing.Imaging.EncoderParameters 1
    $quality = if ($spec.Variant -eq "tilted_compressed") { 38 } else { 92 }
    $encParams.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter ([System.Drawing.Imaging.Encoder]::Quality, [long]$quality)
    $outBmp.Save($path, $codec, $encParams)
    $outBmp.Dispose()
    Write-Host "wrote $path (value_x=$($plan.ValueX))"
}

if ($failed) { exit 1 }

# Optional: Python cross-check if available
$py = Get-Command python -ErrorAction SilentlyContinue
if ($py) {
    $validator = Join-Path $PSScriptRoot "validate_kie_id_card_samples.py"
    & python $validator
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "layout OK"


# compress_png.ps1

Get-ChildItem -File -Filter "*.png" | Where-Object {
    $_.BaseName -notlike "*_compressed"
} | ForEach-Object {
    $inputFile = $_.FullName
    $outputFile = Join-Path $_.DirectoryName "$($_.BaseName)_compressed.png"

    if (Test-Path $outputFile) {
        Write-Host "Skipping (already exists): $($_.Name)"
        return
    }

    ffmpeg -hide_banner -loglevel error -i $inputFile `
        -c:v png -compression_level 9 $outputFile

    if ($LASTEXITCODE -ne 0 -or !(Test-Path $outputFile)) {
        Write-Host "Failed: $($_.Name)" -ForegroundColor Red
        return
    }

    $oldSize = $_.Length
    $newSize = (Get-Item $outputFile).Length

    if ($newSize -ge $oldSize) {
        Remove-Item $outputFile
        Write-Host "No improvement: $($_.Name)"
    }
    else {
        $saved = [math]::Round((1 - $newSize / $oldSize) * 100, 2)
        Write-Host "$($_.Name) -> $([math]::Round($saved, 2))% smaller" -ForegroundColor Green
    }
}

import subprocess
ps = """
$pptx = [System.IO.Path]::GetFullPath('output/m105_fresh_client_submission/deck.pptx')
$outDir = [System.IO.Path]::GetFullPath('output/pngs')
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }
$ppt = New-Object -ComObject PowerPoint.Application
$ppt.Visible = [Microsoft.Office.Core.MsoTriState]::msoTrue
$pres = $ppt.Presentations.Open($pptx, $true, $false, $false)
for ($i = 1; $i -le $pres.Slides.Count; $i++) {
    $slide = $pres.Slides.Item($i)
    $filename = Join-Path $outDir ("slide_{0:D2}.png" -f $i)
    $slide.Export($filename, 'PNG', 1920, 1080)
}
$cnt = $pres.Slides.Count
$pres.Close()
$ppt.Quit()
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($ppt) | Out-Null
Write-Host "Exported $cnt slides"
"""
result = subprocess.run(['powershell', '-Command', ps], capture_output=True, text=True, timeout=120)
print(result.stdout)
if result.stderr:
    print('STDERR:', result.stderr[:300])

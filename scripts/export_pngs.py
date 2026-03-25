"""Export PPTX slides to PNG files via PowerPoint COM on Windows."""

from __future__ import annotations

import subprocess
from pathlib import Path


def export_slides(
    pptx_path: str | Path,
    output_dir: str | Path,
    width: int = 1920,
    height: int = 1080,
) -> str:
    """Export all slides from a PPTX as PNG images."""
    pptx = Path(pptx_path).resolve()
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    ps = f"""
$pptx = [System.IO.Path]::GetFullPath('{pptx.as_posix()}')
$outDir = [System.IO.Path]::GetFullPath('{out_dir.as_posix()}')
if (-not (Test-Path $outDir)) {{ New-Item -ItemType Directory -Path $outDir | Out-Null }}
$ppt = New-Object -ComObject PowerPoint.Application
$ppt.Visible = [Microsoft.Office.Core.MsoTriState]::msoTrue
$pres = $ppt.Presentations.Open($pptx, $true, $false, $false)
for ($i = 1; $i -le $pres.Slides.Count; $i++) {{
    $slide = $pres.Slides.Item($i)
    $filename = Join-Path $outDir ("slide_{{0:D2}}.png" -f $i)
    $slide.Export($filename, 'PNG', {width}, {height})
}}
$count = $pres.Slides.Count
$pres.Close()
$ppt.Quit()
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($ppt) | Out-Null
Write-Host "Exported $count slides to PNG."
"""
    result = subprocess.run(
        ["powershell", "-Command", ps],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "PowerPoint PNG export failed")
    return result.stdout.strip()


if __name__ == "__main__":
    print(export_slides("output/deck.pptx", "output/pngs"))


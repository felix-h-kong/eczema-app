#!/usr/bin/env python3
"""Convert derm-info-pack.md → derm-info-pack.html.

Usage:
    python scripts/build_derm_html.py
"""
import base64
import re
import markdown
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "docs" / "reports"

md_text = (REPORTS / "derm-info-pack.md").read_text()

body_html = markdown.markdown(
    md_text,
    extensions=["tables", "fenced_code", "nl2br"],
)

CSS = """
  @page { size: A4; margin: 18mm 15mm 18mm 15mm; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 10.5pt; line-height: 1.45; color: #1a1a1a;
    max-width: 210mm; margin: 0 auto; padding: 12mm 15mm; background: #fff;
  }
  h1 { font-size: 16pt; color: #111; border-bottom: 2.5px solid #1a1a1a; padding-bottom: 6px; margin-bottom: 8px; }
  h2 { font-size: 13pt; color: #1a1a1a; margin-top: 18px; margin-bottom: 8px; border-bottom: 1.5px solid #ccc; padding-bottom: 4px; page-break-after: avoid; }
  h3 { font-size: 11pt; color: #333; margin-top: 14px; margin-bottom: 6px; page-break-after: avoid; }
  p { margin-bottom: 6px; }
  blockquote { border-left: 3px solid #4a90d9; background: #f0f5fc; padding: 8px 12px; margin: 8px 0 12px 0; font-size: 9.5pt; color: #2c3e50; border-radius: 0 4px 4px 0; }
  blockquote strong { color: #1a3a5c; }
  img { max-width: 100%; height: auto; display: block; margin: 10px auto; border: 1px solid #ddd; border-radius: 4px; }
  table { width: 100%; border-collapse: collapse; margin: 8px 0 12px 0; font-size: 9.5pt; page-break-inside: avoid; }
  th { background: #f1f3f5; font-weight: 600; text-align: left; padding: 6px 8px; border: 1px solid #d0d0d0; font-size: 9pt; color: #333; }
  td { padding: 5px 8px; border: 1px solid #d0d0d0; vertical-align: top; }
  tr:nth-child(even) td { background: #fafafa; }
  ul, ol { margin: 4px 0 8px 20px; }
  li { margin-bottom: 3px; }
  hr { border: none; border-top: 1.5px solid #ccc; margin: 16px 0; }
  strong { color: #111; }
  .page-break { page-break-before: always; }
  @media print {
    body { padding: 0; font-size: 10pt; }
    blockquote { background: #f5f5f5 !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    th { background: #f0f0f0 !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    tr:nth-child(even) td { background: #f8f8f8 !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    img { max-height: 45vh; object-fit: contain; }
    h2 { page-break-after: avoid; }
    table { page-break-inside: avoid; }
  }
  h2:nth-of-type(n+5) ~ * { font-size: 9.5pt; }
  h2:nth-of-type(n+5) ~ table { font-size: 9pt; }
  h2:last-of-type ~ ol { font-size: 8.5pt; line-height: 1.35; color: #444; }
"""

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Eczema Tracking Summary — Dermatologist Info Pack</title>
<style>{CSS}</style>
</head>
<body>
{body_html}
</body>
</html>
"""

# Embed images as base64 data URIs so the HTML is self-contained
def embed_image(match):
    src = match.group(1)
    img_path = REPORTS / src
    if not img_path.exists():
        return match.group(0)
    mime = "image/png" if src.endswith(".png") else "image/jpeg"
    data = base64.b64encode(img_path.read_bytes()).decode()
    return f'src="data:{mime};base64,{data}"'

html = re.sub(r'src="([^"]+\.(png|jpe?g))"', embed_image, html)

out = REPORTS / "derm-info-pack.html"
out.write_text(html)
print(f"Written: {out} ({out.stat().st_size // 1024} KB)")

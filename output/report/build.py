"""Build the single-file deliverables: report.html and slides.html at the repo root.

    python output/report/build.py

Edit output/report/report_src.html or slides_src.html (they reference img/*.jpg); this script inlines every
image as base64 so each deliverable is one self-contained HTML file that works when uploaded on its own.
"""
import base64
import re
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent.parent


def inline(src: str) -> str:
    def sub(m):
        path = HERE / m.group(1)
        mime = "image/png" if path.suffix == ".png" else "image/jpeg"
        return f'src="data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"'
    return re.sub(r'src="(img/[^"]+)"', sub, src)


for name in ("report", "slides"):
    src = HERE / f"{name}_src.html"
    if src.exists():
        out = ROOT / f"{name}.html"
        out.write_text(inline(src.read_text(encoding="utf-8")), encoding="utf-8")
        print(f"{out.name}: {out.stat().st_size / 1e6:.1f} MB")

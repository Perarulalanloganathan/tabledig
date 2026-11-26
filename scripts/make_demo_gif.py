"""Record docs/demo.gif from the real Streamlit app (headless Chrome via Playwright).

    pip install -e ".[app]" playwright pillow
    python scripts/make_demo_gif.py [--chrome /usr/bin/google-chrome]
"""
from __future__ import annotations

import argparse
import io
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PORT = 8599
W, H = 1180, 960


def caption(img: Image.Image, text: str) -> Image.Image:
    bar = 52
    out = Image.new("RGB", (img.width, img.height + bar), (24, 24, 27))
    out.paste(img, (0, bar))
    draw = ImageDraw.Draw(out)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    draw.text((20, 13), text, fill=(255, 255, 255), font=font)
    return out


def wait_for_server() -> None:
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://localhost:{PORT}/_stcore/health", timeout=2)
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError("Streamlit did not start")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chrome", default="/usr/bin/google-chrome")
    parser.add_argument("--out", default=str(ROOT / "docs" / "demo.gif"))
    args = parser.parse_args()

    server = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(ROOT / "app" / "streamlit_app.py"),
         "--server.headless", "true", "--server.port", str(PORT), "--browser.gatherUsageStats", "false"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    frames: list[tuple[Image.Image, int]] = []
    try:
        wait_for_server()
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=args.chrome, args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": W, "height": H}, color_scheme="light")

            def shot(text: str, ms: int = 2400) -> None:
                page.wait_for_timeout(900)
                img = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
                frames.append((caption(img, text), ms))

            page.goto(f"http://localhost:{PORT}")
            page.get_by_text("Attributes found").wait_for(timeout=60000)
            shot("1. Pick a sample PDF (or upload your own) and list the attributes you want", 3000)

            def show_results() -> None:
                page.get_by_role("tab", name="Results").click()
                page.get_by_role("tab", name="Results").scroll_into_view_if_needed()
                page.mouse.wheel(0, 260)

            show_results()
            shot("2. Values come back with page, column, unit and match score", 3200)

            page.get_by_role("tab", name="Detected tables").click()
            page.get_by_text("Page 1").first.click()
            shot("3. Every detected table is shown, so you can copy exact row labels", 3200)

            page.mouse.wheel(0, -3000)
            page.get_by_role("combobox").first.click()
            page.get_by_role("option", name="Invoice (borderless table)").click()
            page.get_by_text("Attributes found").wait_for()
            show_results()
            shot("4. Works on borderless tables too, such as invoices", 3200)

            page.mouse.wheel(0, -3000)
            box = page.get_by_role("textbox", name="Attributes to extract (one per line)")
            box.fill("Total = Total due\nSubtotal\nSales tax\nDiscount")
            box.press("Control+Enter")
            page.wait_for_timeout(1200)
            show_results()
            shot("5. Attributes that are not in the PDF are reported as not found", 3800)
            browser.close()
    finally:
        server.terminate()

    width = 1000
    imgs = []
    for img, _ in frames:
        h = round(img.height * width / img.width)
        imgs.append(img.resize((width, h), Image.LANCZOS).quantize(colors=128, method=Image.MEDIANCUT))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    imgs[0].save(out, save_all=True, append_images=imgs[1:], duration=[ms for _, ms in frames],
                 loop=0, optimize=True, disposal=2)
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB, {len(imgs)} frames)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

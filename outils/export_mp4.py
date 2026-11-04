#!/usr/bin/env python3
"""apercu.html -> vidéo muette, image par image (Playwright + ffmpeg).

La page doit exposer window.seek(t) (t en secondes) qui affiche l'état EXACT de
l'animation au temps t, sans dépendre de l'horloge réelle. Elle peut aussi
exposer window.DUREE (secondes) ; sinon la durée est lue dans voix.srt à côté
de la page, ou passée avec --duree.

Usage :
    python outils/export_mp4.py videos/001-slug/apercu.html videos/001-slug/muette.mp4
    python outils/export_mp4.py apercu.html muette.mp4 --duree 72.4 --fps 30
"""
import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CHROMIUM_PREINSTALLE = "/opt/pw-browsers/chromium"


def reglages():
    try:
        return json.loads((RACINE / "kit" / "reglages.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def duree_srt(srt):
    temps = re.findall(r"--> (\d+):(\d+):(\d+)[,.](\d+)", srt.read_text(encoding="utf-8"))
    if not temps:
        return None
    h, m, s, ms = map(int, temps[-1])
    return h * 3600 + m * 60 + s + ms / 1000


async def lancer_navigateur(pw):
    try:
        return await pw.chromium.launch()
    except Exception:
        if os.path.exists(CHROMIUM_PREINSTALLE):
            for racine, _, fichiers in os.walk("/opt/pw-browsers"):
                if "chrome" in fichiers and "headless" not in racine:
                    return await pw.chromium.launch(executable_path=os.path.join(racine, "chrome"),
                                                    args=["--no-sandbox"])
        raise


async def exporter(html, sortie, largeur, hauteur, fps, duree):
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        nav = await lancer_navigateur(pw)
        page = await nav.new_page(viewport={"width": largeur, "height": hauteur}, device_scale_factor=1)
        await page.goto(Path(html).resolve().as_uri(), wait_until="networkidle")
        await page.evaluate("document.fonts ? document.fonts.ready.then(() => true) : true")
        if not await page.evaluate("typeof window.seek === 'function'"):
            raise RuntimeError("la page n'expose pas window.seek(t)")
        if duree is None:
            duree = await page.evaluate("typeof window.DUREE === 'number' ? window.DUREE : null")
        if duree is None:
            srt = Path(html).parent / "voix.srt"
            duree = duree_srt(srt) if srt.exists() else None
        if not duree:
            raise RuntimeError("durée inconnue : passer --duree, définir window.DUREE ou fournir voix.srt")

        n = int(round(duree * fps))
        ff = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps),
             "-c:v", "png", "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
             "-pix_fmt", "yuv420p", "-r", str(fps), "-movflags", "+faststart", str(sortie)],
            stdin=subprocess.PIPE)
        try:
            for i in range(n):
                t = i / fps
                await page.evaluate("t => Promise.resolve(window.seek(t))", t)
                ff.stdin.write(await page.screenshot(type="png"))
                if i % (fps * 5) == 0:
                    print(f"  image {i}/{n} (t = {t:.1f} s)", flush=True)
        finally:
            ff.stdin.close()
            code = ff.wait()
            await nav.close()
        if code != 0:
            raise RuntimeError(f"ffmpeg a échoué (code {code})")
        return n, duree


def main():
    reg = reglages()
    l, h = (int(x) for x in reg.get("format", "1080x1920").split("x"))
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("html")
    p.add_argument("sortie")
    p.add_argument("--fps", type=int, default=int(reg.get("fps", 30)))
    p.add_argument("--duree", type=float, default=None)
    a = p.parse_args()
    try:
        n, d = asyncio.run(exporter(a.html, a.sortie, l, h, a.fps, a.duree))
    except Exception as e:
        print(f"ERREUR export_mp4.py : {e}", file=sys.stderr)
        sys.exit(1)
    print(f"OK : {a.sortie} ({n} images, {d:.2f} s, {l}x{h} à {a.fps} i/s)")


if __name__ == "__main__":
    main()

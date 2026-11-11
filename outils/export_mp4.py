#!/usr/bin/env python3
"""apercu.html -> vidéo muette, image par image (Playwright + ffmpeg), en parallèle.

La page doit exposer window.seek(t) (t en secondes) qui affiche l'état EXACT de
l'animation au temps t, sans dépendre de l'horloge réelle. Elle peut aussi
exposer window.DUREE (secondes) ; sinon la durée est lue dans voix.srt à côté
de la page, ou passée avec --duree.

Vitesse : captures JPEG (5 fois plus rapides que PNG) et plusieurs navigateurs en
parallèle, un par tranche d'images ; les tranches sont ensuite collées sans réencodage.
Une vidéo de 63 s (1 908 images) se rend en 2 à 4 minutes au lieu de 20.

Usage :
    python outils/export_mp4.py videos/001-slug/apercu.html muette.mp4
    python outils/export_mp4.py apercu.html muette.mp4 --duree 72.4 --fps 30 --workers 4
"""
import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
import time
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


async def tranche(num, html, largeur, hauteur, fps, a, b, chemin, qualite, progression):
    """Rend les images [a, b) dans un navigateur à part et les encode dans `chemin`."""
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        nav = await lancer_navigateur(pw)
        page = await nav.new_page(viewport={"width": largeur, "height": hauteur}, device_scale_factor=1)
        await page.goto(Path(html).resolve().as_uri(), wait_until="networkidle")
        await page.evaluate("document.fonts ? document.fonts.ready.then(() => true) : true")
        if not await page.evaluate("typeof window.seek === 'function'"):
            raise RuntimeError("la page n'expose pas window.seek(t)")
        ff = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps),
             "-c:v", "mjpeg", "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
             "-pix_fmt", "yuv420p", "-r", str(fps), str(chemin)],
            stdin=subprocess.PIPE)
        try:
            for i in range(a, b):
                await page.evaluate("t => Promise.resolve(window.seek(t))", i / fps)
                ff.stdin.write(await page.screenshot(type="jpeg", quality=qualite))
                progression[num] = i - a + 1
        finally:
            ff.stdin.close()
            code = ff.wait()
            await nav.close()
        if code != 0:
            raise RuntimeError(f"ffmpeg a échoué sur la tranche {num} (code {code})")


async def suivi(progression, total, debut):
    while True:
        await asyncio.sleep(15)
        fait = sum(progression.values())
        ecoule = time.time() - debut
        reste = ecoule / max(fait, 1) * (total - fait)
        print(f"  {fait}/{total} images ({fait * 100 // total} %), reste ≈ {reste / 60:.1f} min", flush=True)


async def exporter(html, sortie, largeur, hauteur, fps, duree, workers, qualite):
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:   # lecture de la durée
        nav = await lancer_navigateur(pw)
        page = await nav.new_page(viewport={"width": largeur, "height": hauteur})
        await page.goto(Path(html).resolve().as_uri(), wait_until="networkidle")
        if duree is None:
            duree = await page.evaluate("typeof window.DUREE === 'number' ? window.DUREE : null")
        await nav.close()
    if duree is None:
        srt = Path(html).parent / "voix.srt"
        duree = duree_srt(srt) if srt.exists() else None
    if not duree:
        raise RuntimeError("durée inconnue : passer --duree, définir window.DUREE ou fournir voix.srt")

    n = int(round(duree * fps))
    workers = max(1, min(workers, n // 60 or 1))
    bornes = [(n * k // workers, n * (k + 1) // workers) for k in range(workers)]
    debut = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        chunks = [Path(tmp) / f"tranche_{k}.mp4" for k in range(workers)]
        progression = {k: 0 for k in range(workers)}
        moniteur = asyncio.create_task(suivi(progression, n, debut))
        try:
            await asyncio.gather(*[tranche(k, html, largeur, hauteur, fps, a, b, chunks[k], qualite, progression)
                                   for k, (a, b) in enumerate(bornes)])
        finally:
            moniteur.cancel()
        liste = Path(tmp) / "liste.txt"
        liste.write_text("".join(f"file '{c}'\n" for c in chunks))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(liste),
                        "-c", "copy", "-movflags", "+faststart", str(sortie)], check=True)
    return n, duree, workers, time.time() - debut


def main():
    reg = reglages()
    l, h = (int(x) for x in reg.get("format", "1080x1920").split("x"))
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("html")
    p.add_argument("sortie")
    p.add_argument("--fps", type=int, default=int(reg.get("fps", 30)))
    p.add_argument("--duree", type=float, default=None)
    p.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1), help="navigateurs en parallèle (défaut : nombre de processeurs, max 4)")
    p.add_argument("--qualite", type=int, default=95, help="qualité JPEG des captures (défaut 95)")
    a = p.parse_args()
    try:
        n, d, w, t = asyncio.run(exporter(a.html, a.sortie, l, h, a.fps, a.duree, a.workers, a.qualite))
    except Exception as e:
        print(f"ERREUR export_mp4.py : {e}", file=sys.stderr)
        sys.exit(1)
    print(f"OK : {a.sortie} ({n} images, {d:.2f} s, {l}x{h} à {a.fps} i/s, {w} navigateurs, rendu en {t / 60:.1f} min)")


if __name__ == "__main__":
    main()

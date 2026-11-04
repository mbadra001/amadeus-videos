#!/usr/bin/env python3
"""Vidéo muette + voix + musique (+ bruitages) -> video.mp4.

- La musique est baissée sous la voix par compression sidechain (ffmpeg).
- Si la musique n'est pas fournie, elle est générée par outils/sons.py.
- Si le fichier final fait 50 Mo ou plus, il est recompressé automatiquement
  à un débit calculé pour passer sous la limite (Telegram).

Usage :
    python outils/mixage.py --video muette.mp4 --voix voix.mp3 --sortie video.mp4 \\
        [--musique musique.wav | --coupures 20-28] [--bruitages sfx.json]

sfx.json : [{"t": 1.2, "type": "whoosh"}, {"t": 5.0, "type": "impact"}, ...]
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sons  # noqa: E402

LIMITE = 50 * 1024 * 1024
CIBLE = 46 * 1024 * 1024          # marge sous la limite


def duree(fichier):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(fichier)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def mixer(video, voix, musique, bruitages, sortie, debit_video=None):
    d = duree(video)
    filtre = (
        "[1:a]aformat=sample_rates=44100:channel_layouts=stereo,apad,asplit=2[voix][cle];"
        "[2:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=0.55[mus];"
        "[mus][cle]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=350:makeup=1[musb];"
        "[3:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=0.7[sfx];"
        "[voix][musb][sfx]amix=inputs=3:duration=first:normalize=0,"
        "alimiter=limit=0.95:level=disabled[a]"
    )
    v = ["-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p"]
    if debit_video:
        v += ["-b:v", f"{debit_video}k", "-maxrate", f"{int(debit_video * 1.2)}k", "-bufsize", f"{debit_video * 2}k"]
    else:
        v += ["-crf", "20"]
    ffmpeg("-i", str(video), "-i", str(voix), "-i", str(musique), "-i", str(bruitages),
           "-filter_complex", filtre, "-map", "0:v", "-map", "[a]", *v,
           "-c:a", "aac", "-b:a", "160k", "-t", f"{d:.3f}", "-movflags", "+faststart", str(sortie))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--video", required=True, help="vidéo muette (export_mp4.py)")
    p.add_argument("--voix", required=True, help="voix.mp3")
    p.add_argument("--sortie", required=True, help="video.mp4")
    p.add_argument("--musique", help="musique déjà générée (wav) ; sinon générée")
    p.add_argument("--coupures", default="", help="flash-backs pour la musique générée, ex. 20-28")
    p.add_argument("--bruitages", help="JSON des bruitages [{t, type, gain?}]")
    a = p.parse_args()

    try:
        d = duree(a.video)
        if duree(a.voix) < 1:
            raise RuntimeError("voix absente ou vide : on ne livre jamais une vidéo sans voix")
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            musique = a.musique
            if not musique:
                musique = tmp / "musique.wav"
                sons.ecrire_wav(musique, sons.musique(d, sons.parse_coupures(a.coupures)))
            evts = json.loads(Path(a.bruitages).read_text(encoding="utf-8")) if a.bruitages else []
            sfx = tmp / "bruitages.wav"
            sons.ecrire_wav(sfx, sons.piste_bruitages(evts, d))

            mixer(a.video, a.voix, musique, sfx, a.sortie)
            taille = Path(a.sortie).stat().st_size
            essais = 0
            while taille >= LIMITE and essais < 3:
                essais += 1
                debit = int((CIBLE * 8 / d) / 1000 * (0.9 ** (essais - 1))) - 160
                print(f"  {taille / 1e6:.1f} Mo ≥ 50 Mo : recompression à {debit} kb/s (essai {essais})")
                mixer(a.video, a.voix, musique, sfx, a.sortie, debit_video=max(debit, 300))
                taille = Path(a.sortie).stat().st_size
            if taille >= LIMITE:
                raise RuntimeError(f"video.mp4 fait encore {taille / 1e6:.1f} Mo après recompression")
    except Exception as e:
        print(f"ERREUR mixage.py : {e}", file=sys.stderr)
        sys.exit(1)
    print(f"OK : {a.sortie} ({d:.2f} s, {taille / 1024 / 1024:.1f} Mo)")


if __name__ == "__main__":
    main()

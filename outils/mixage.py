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


def mixer(video, voix, musique, bruitages, sortie, debit_video=None, vol_musique=0.55):
    d = duree(video)
    filtre = (
        "[1:a]aformat=sample_rates=44100:channel_layouts=stereo,apad,asplit=2[voix][cle];"
        f"[2:a]aformat=sample_rates=44100:channel_layouts=stereo,volume={vol_musique}[mus];"
        "[mus][cle]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=350:makeup=1[musb];"
        "[3:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=1.0[sfx];"
        "[voix][musb][sfx]amix=inputs=3:duration=first:normalize=0,"
        "loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=limit=0.89:level=disabled[a]"
    )
    v = ["-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p"]
    if debit_video:      # débit imposé (recompression de secours)
        v += ["-b:v", f"{debit_video}k", "-maxrate", f"{int(debit_video * 1.2)}k", "-bufsize", f"{debit_video * 2}k"]
    else:                # une seule passe : qualité constante, plafonnée pour rester sous 50 Mo
        plafond = int((CIBLE * 8 / d) / 1000) - 170
        v += ["-crf", "19", "-maxrate", f"{plafond}k", "-bufsize", f"{plafond * 2}k"]
    ffmpeg("-i", str(video), "-i", str(voix), "-i", str(musique), "-i", str(bruitages),
           "-filter_complex", filtre, "-map", "0:v", "-map", "[a]", *v,
           "-c:a", "aac", "-b:a", "160k", "-t", f"{d:.3f}", "-movflags", "+faststart", str(sortie))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--video", required=True, help="vidéo muette (export_mp4.py)")
    p.add_argument("--voix", required=True, help="voix.mp3")
    p.add_argument("--sortie", required=True, help="video.mp4")
    p.add_argument("--musique", help="fichier musique (mp3/wav, ex. trouvé via Openverse) ; sinon générée par sons.py")
    p.add_argument("--volume-musique", type=float, default=0.85, help="volume de la musique avant sidechain (défaut 0.85)")
    p.add_argument("--coupures", default="", help="flash-backs pour la musique générée, ex. 20-28")
    p.add_argument("--bruitages", help="JSON des bruitages [{t, type, gain?}]")
    a = p.parse_args()

    try:
        d = duree(a.video)
        if duree(a.voix) < 1:
            raise RuntimeError("voix.mp3 absent ou vide (relancer outils/voix.py)")
        mode_fichier = Path(a.voix).parent / "voix_mode.txt"
        mode = mode_fichier.read_text(encoding="utf-8").strip() if mode_fichier.exists() else "edge-tts"
        vol = 1.0 if mode == "sans-voix" else a.volume_musique   # sans voix : la musique porte la vidéo
        print(f"  mode voix : {mode}")
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            musique = a.musique
            if musique:   # musique externe : coupée à la durée, fondu d'entrée et de sortie
                prete = tmp / "musique_coupee.wav"
                ffmpeg("-i", str(musique), "-t", f"{d:.3f}", "-af",
                       f"afade=t=in:d=0.3,afade=t=out:st={max(0, d - 1.2):.2f}:d=1.2", "-ar", "44100", str(prete))
                musique = prete
            if not musique:
                musique = tmp / "musique.wav"
                sons.ecrire_wav(musique, sons.musique(d, sons.parse_coupures(a.coupures)))
            evts = json.loads(Path(a.bruitages).read_text(encoding="utf-8")) if a.bruitages else []
            sfx = tmp / "bruitages.wav"
            sons.ecrire_wav(sfx, sons.piste_bruitages(evts, d))

            mixer(a.video, a.voix, musique, sfx, a.sortie, vol_musique=vol)
            taille = Path(a.sortie).stat().st_size
            essais = 0
            while taille >= LIMITE and essais < 3:
                essais += 1
                debit = int((CIBLE * 8 / d) / 1000 * (0.9 ** (essais - 1))) - 160
                print(f"  {taille / 1e6:.1f} Mo ≥ 50 Mo : recompression à {debit} kb/s (essai {essais})")
                mixer(a.video, a.voix, musique, sfx, a.sortie, debit_video=max(debit, 300), vol_musique=vol)
                taille = Path(a.sortie).stat().st_size
            if taille >= LIMITE:
                raise RuntimeError(f"video.mp4 fait encore {taille / 1e6:.1f} Mo après recompression")
    except Exception as e:
        print(f"ERREUR mixage.py : {e}", file=sys.stderr)
        sys.exit(1)
    print(f"OK : {a.sortie} ({d:.2f} s, {taille / 1024 / 1024:.1f} Mo)")


if __name__ == "__main__":
    main()

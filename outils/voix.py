#!/usr/bin/env python3
"""Génère voix.mp3 et voix.srt (un sous-titre par mot), avec trois modes en cascade.

  1. edge-tts (voix de reglages.json) : voix principale, sous-titres mot à mot exacts.
  2. Piper (hors ligne, voix française SIWIS, licence CC BY 4.0) : voix de secours si
     edge-tts échoue. Modèle téléchargé une fois depuis les releases GitHub de Piper.
     Temps des mots : exacts par phrase, répartis dans la phrase selon la longueur des mots.
  3. Sans voix : voix.mp3 silencieux + voix.srt calé sur un rythme de lecture
     (2,7 mots/s), pour une vidéo musique + sous-titres.

Le mode utilisé est écrit dans <dossier>/voix_mode.txt : edge-tts | piper | sans-voix.

Usage :
    python outils/voix.py "Texte à dire" videos/001-slug/
    python outils/voix.py script.txt videos/001-slug/
    python outils/voix.py script.txt videos/001-slug/ --voix fr-FR-HenriNeural --vitesse +5%

    python outils/voix.py script.txt videos/001-slug/ --mode edge      # edge-tts seul
Modes : auto (défaut : edge -> piper -> sans), edge, piper, sans.
La voix et la vitesse par défaut viennent de kit/reglages.json.
Code de sortie 1 seulement si le mode demandé échoue (en auto, le mode « sans » ne peut pas échouer).
"""
import argparse
import asyncio
import json
import os
import re
import ssl
import subprocess
import sys
import urllib.request
import wave
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
REGLAGES = RACINE / "kit" / "reglages.json"


def lire_reglages():
    try:
        return json.loads(REGLAGES.read_text(encoding="utf-8"))
    except Exception:
        return {}


async def generer(texte, sortie, voix, vitesse):
    import edge_tts
    import edge_tts.communicate as ec

    # Environnements derrière un proxy HTTPS (ex. sessions cloud) : edge-tts
    # n'utilise ni HTTPS_PROXY ni SSL_CERT_FILE d'office, on les lui transmet.
    ca = os.environ.get("SSL_CERT_FILE")
    if ca and os.path.isfile(ca):
        ctx = ssl.create_default_context()
        ctx.load_verify_locations(cafile=ca)
        ec._SSL_CTX = ctx
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or None

    comm = edge_tts.Communicate(texte, voix, rate=vitesse, boundary="WordBoundary", proxy=proxy)
    sous_titres = edge_tts.SubMaker()
    audio = bytearray()
    async for morceau in comm.stream():
        if morceau["type"] == "audio":
            audio.extend(morceau["data"])
        elif morceau["type"] in ("WordBoundary", "SentenceBoundary"):
            sous_titres.feed(morceau)
    if not audio:
        raise RuntimeError("edge-tts n'a renvoyé aucun audio")
    srt = sous_titres.get_srt()
    if not srt.strip():
        raise RuntimeError("edge-tts n'a renvoyé aucun repère de mot (srt vide)")
    (sortie / "voix.mp3").write_bytes(bytes(audio))
    (sortie / "voix.srt").write_text(srt, encoding="utf-8")
    return srt.count("-->")


# ------------------------------------------------------------------ utilitaires
def fmt(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s_, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s_:02d},{ms:03d}"


def ecrire_srt(chemin, mots):
    """mots : liste de (debut, fin, mot)."""
    lignes = []
    for i, (a, b, w) in enumerate(mots, 1):
        lignes += [str(i), f"{fmt(a)} --> {fmt(b)}", w, ""]
    Path(chemin).write_text("\n".join(lignes), encoding="utf-8")


def phrases(texte):
    return [p.strip() for p in re.split(r"(?<=[.!?…])\s+", texte) if p.strip()]


def repartir(mots, debut, duree):
    """Répartit des mots sur [debut, debut+duree] proportionnellement à leur longueur."""
    poids = [len(w) + 2 for w in mots]
    total = sum(poids)
    t, out = debut, []
    for w, pd in zip(mots, poids):
        d = duree * pd / total
        out.append((t, t + d, w))
        t += d
    return out


def wav_vers_mp3(wav, mp3):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-c:a", "libmp3lame",
                    "-b:a", "128k", str(mp3)], check=True)


# ------------------------------------------------------------------ mode 2 : Piper
PIPER_URL = "https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-fr-siwis-medium.tar.gz"
PIPER_DIR = Path(os.environ.get("AMADEUS_CACHE", Path.home() / ".cache" / "amadeus")) / "piper"
PIPER_MODELE = PIPER_DIR / "fr-siwis-medium.onnx"
PIPER_PAUSE = 0.28   # silence entre deux phrases (s)


def modele_piper():
    if PIPER_MODELE.exists() and PIPER_MODELE.stat().st_size > 10_000_000:
        return PIPER_MODELE
    PIPER_DIR.mkdir(parents=True, exist_ok=True)
    archive = PIPER_DIR / "voix.tar.gz"
    print("  téléchargement du modèle Piper (≈ 60 Mo)...", flush=True)
    subprocess.run(["curl", "-sSL", "--fail", "--retry", "3", "-o", str(archive), PIPER_URL], check=True)
    subprocess.run(["tar", "xzf", str(archive), "-C", str(PIPER_DIR)], check=True)
    archive.unlink()
    if not PIPER_MODELE.exists():
        raise RuntimeError("modèle Piper introuvable après téléchargement")
    return PIPER_MODELE


def generer_piper(texte, sortie):
    import logging
    logging.getLogger("piper").setLevel(logging.ERROR)
    from piper import PiperVoice

    voix = PiperVoice.load(str(modele_piper()))
    sr = None
    pcm = bytearray()
    mots = []
    t = 0.0
    for ph in phrases(texte):
        morceau = bytearray()
        for chunk in voix.synthesize(ph):
            sr = chunk.sample_rate
            morceau.extend(chunk.audio_int16_bytes)
        if not morceau:
            continue
        duree = len(morceau) / 2 / sr
        mots += repartir(ph.split(), t, duree)
        pcm.extend(morceau)
        pcm.extend(b"\x00\x00" * int(PIPER_PAUSE * sr))
        t += duree + PIPER_PAUSE
    if not pcm:
        raise RuntimeError("Piper n'a produit aucun audio")
    wav = sortie / "voix_tmp.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(pcm))
    wav_vers_mp3(wav, sortie / "voix.mp3")
    wav.unlink()
    ecrire_srt(sortie / "voix.srt", mots)
    return len(mots)


# ------------------------------------------------------------------ mode 3 : sans voix
MOTS_PAR_S = 2.7


def generer_sans_voix(texte, sortie):
    mots, t = [], 0.0
    for ph in phrases(texte):
        ws = ph.split()
        d = len(ws) / MOTS_PAR_S
        mots += repartir(ws, t, d)
        t += d + 0.3
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "anullsrc=r=44100:cl=mono", "-t", f"{t:.3f}", "-c:a", "libmp3lame",
                    "-b:a", "64k", str(sortie / "voix.mp3")], check=True)
    ecrire_srt(sortie / "voix.srt", mots)
    return len(mots)


def main():
    reg = lire_reglages()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("texte", help="texte à dire, ou chemin d'un fichier .txt")
    p.add_argument("dossier", help="dossier de sortie (voix.mp3 + voix.srt)")
    p.add_argument("--voix", default=reg.get("voix", "fr-FR-HenriNeural"))
    p.add_argument("--vitesse", default=reg.get("vitesse_voix", "+0%"))
    p.add_argument("--mode", choices=["auto", "edge", "piper", "sans"], default="auto")
    a = p.parse_args()

    source = Path(a.texte)
    if source.suffix == ".txt" and source.is_file():
        texte = source.read_text(encoding="utf-8")
    else:
        texte = a.texte
    texte = " ".join(texte.split())
    if not texte:
        print("ERREUR voix.py : texte vide", file=sys.stderr)
        sys.exit(1)

    sortie = Path(a.dossier)
    sortie.mkdir(parents=True, exist_ok=True)
    essais = {
        "edge": ("edge-tts", lambda: asyncio.run(generer(texte, sortie, a.voix, a.vitesse))),
        "piper": ("piper", lambda: generer_piper(texte, sortie)),
        "sans": ("sans-voix", lambda: generer_sans_voix(texte, sortie)),
    }
    ordre = ["edge", "piper", "sans"] if a.mode == "auto" else [a.mode]
    erreurs = []
    for cle in ordre:
        nom, fonction = essais[cle]
        try:
            n = fonction()
        except Exception as e:  # réseau, voix inconnue, module absent...
            msg = f"{nom} : {type(e).__name__}: {e}"
            erreurs.append(msg)
            print(f"ÉCHEC {msg}", file=sys.stderr)
            continue
        (sortie / "voix_mode.txt").write_text(nom + "\n", encoding="utf-8")
        if erreurs:
            (sortie / "voix_erreurs.txt").write_text("\n".join(erreurs) + "\n", encoding="utf-8")
        print(f"OK [{nom}] : {sortie/'voix.mp3'} + {sortie/'voix.srt'} ({n} mots)")
        return
    print("ERREUR voix.py : " + " | ".join(erreurs), file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()

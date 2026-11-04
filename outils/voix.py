#!/usr/bin/env python3
"""Génère voix.mp3 et voix.srt (un sous-titre par mot) avec edge-tts.

Usage :
    python outils/voix.py "Texte à dire" videos/001-slug/
    python outils/voix.py script.txt videos/001-slug/
    python outils/voix.py script.txt videos/001-slug/ --voix fr-FR-HenriNeural --vitesse +5%

La voix et la vitesse par défaut viennent de kit/reglages.json.
Code de sortie 1 en cas d'échec (réseau, voix inconnue, audio vide...).
"""
import argparse
import asyncio
import json
import os
import ssl
import sys
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


def main():
    reg = lire_reglages()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("texte", help="texte à dire, ou chemin d'un fichier .txt")
    p.add_argument("dossier", help="dossier de sortie (voix.mp3 + voix.srt)")
    p.add_argument("--voix", default=reg.get("voix", "fr-FR-HenriNeural"))
    p.add_argument("--vitesse", default=reg.get("vitesse_voix", "+0%"))
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
    try:
        n = asyncio.run(generer(texte, sortie, a.voix, a.vitesse))
    except Exception as e:  # réseau, voix inconnue, module absent...
        print(f"ERREUR voix.py : {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"OK : {sortie/'voix.mp3'} + {sortie/'voix.srt'} ({n} mots, voix {a.voix}, vitesse {a.vitesse})")


if __name__ == "__main__":
    main()

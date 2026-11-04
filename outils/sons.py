#!/usr/bin/env python3
"""Musique trap/phonk 140 BPM (ré mineur) et bruitages, 100 % synthétisés (numpy/scipy).

Aucun échantillon externe, aucun fichier sous droits.

Usage :
    # Musique de 75 s, avec coupure filtrée (flash-back) de 20 s à 28 s puis drop
    python outils/sons.py musique --duree 75 --sortie musique.wav --coupures 20-28

    # Piste de bruitages placés dans le temps (JSON : [{"t": 1.2, "type": "whoosh"}, ...])
    python outils/sons.py bruitages --evenements sfx.json --duree 75 --sortie bruitages.wav

    # Un bruitage seul (whoosh | impact | riser)
    python outils/sons.py un --type impact --sortie impact.wav

    # Temps des kicks (JSON) pour caler le zoom de l'image dans apercu.html
    python outils/sons.py kicks --duree 75 [--coupures 20-28]
"""
import argparse
import json
import sys

import numpy as np
from scipy import signal
from scipy.io import wavfile

SR = 44100
BPM = 140
BEAT = 60.0 / BPM          # une noire
STEP = BEAT / 4            # une double-croche (16e)
BAR = BEAT * 4
RNG = np.random.default_rng(1406)

# Ré mineur : fréquences utiles
def note(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)

# Mélodie de cloche (ré mineur naturel), une note par double-croche ou None
MELODIE = [74, None, None, 77, None, None, 76, None, 74, None, 72, None, 69, None, None, None,
           74, None, None, 77, None, None, 81, None, 79, None, 77, None, 76, None, 72, None]
BASSE_PAR_MESURE = [38, 38, 33, 36]   # 808 : Ré2, Ré2, La1, Do2 (ré mineur)
KICKS_16 = [0, 7, 10]           # positions du kick dans une mesure de 16 doubles-croches
CLAPS_16 = [4, 12]


# ---------------------------------------------------------------- instruments
def env_exp(n, tau):
    t = np.arange(n) / SR
    return np.exp(-t / tau)


def kick808(f0, duree=0.55, drive=3.0):
    n = int(duree * SR)
    t = np.arange(n) / SR
    f = f0 + (f0 * 4) * np.exp(-t / 0.025)          # attaque en glissé
    phase = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(phase) * env_exp(n, duree / 2.2)
    x = np.tanh(drive * x) / np.tanh(drive)          # saturation
    clic = RNG.standard_normal(n) * env_exp(n, 0.002) * 0.3
    return x + clic


def clap(duree=0.25):
    n = int(duree * SR)
    bruit = RNG.standard_normal(n)
    b, a = signal.butter(2, [900 / (SR / 2), 4000 / (SR / 2)], btype="band")
    bruit = signal.lfilter(b, a, bruit)
    env = np.zeros(n)
    for d in (0.0, 0.010, 0.020):                    # trois micro-frappes
        i = int(d * SR)
        env[i:] += env_exp(n - i, 0.012 if d < 0.02 else 0.09)
    return bruit * env * 0.9


def charley(duree=0.05, ouvert=False):
    n = int((0.25 if ouvert else duree) * SR)
    bruit = RNG.standard_normal(n)
    b, a = signal.butter(4, 7000 / (SR / 2), btype="high")
    return signal.lfilter(b, a, bruit) * env_exp(n, 0.08 if ouvert else 0.012) * 0.35


def cloche(freq, duree=0.6):
    n = int(duree * SR)
    t = np.arange(n) / SR
    mod = np.sin(2 * np.pi * freq * 3.5 * t) * 2.2 * env_exp(n, 0.15)
    x = np.sin(2 * np.pi * freq * t + mod) * env_exp(n, 0.25)
    return x * 0.28


def placer(piste, son, t):
    i = int(t * SR)
    if i >= len(piste):
        return
    j = min(len(piste), i + len(son))
    piste[i:j] += son[: j - i]


# ---------------------------------------------------------------- musique
def parse_coupures(txt):
    out = []
    for part in (txt or "").split(","):
        part = part.strip()
        if part:
            a, b = part.split("-")
            out.append((float(a), float(b)))
    return out


def dans_coupure(t, coupures):
    return any(a <= t < b for a, b in coupures)


def temps_kicks(duree, coupures=()):
    ks = []
    m = 0
    while m * BAR < duree:
        for p in KICKS_16:
            t = m * BAR + p * STEP
            if t < duree and not dans_coupure(t, coupures):
                ks.append(round(t, 4))
        m += 1
    return ks


def musique(duree, coupures=()):
    n = int(duree * SR) + SR
    batterie = np.zeros(n)
    basse = np.zeros(n)
    melodie = np.zeros(n)
    m = 0
    while m * BAR < duree:
        t0 = m * BAR
        f_basse = note(BASSE_PAR_MESURE[m % 4])
        for p in range(16):
            t = t0 + p * STEP
            if t >= duree:
                break
            if p in KICKS_16:
                placer(basse, kick808(f_basse, duree=0.55 if p == 0 else 0.35), t)
            if p in CLAPS_16:
                placer(batterie, clap(), t)
            # charleys : croches, avec rafales (triolets de 32e) en fin de mesure paire
            if p % 2 == 0:
                placer(batterie, charley(ouvert=(p == 14 and m % 2)), t)
            if m % 2 == 1 and p in (11, 15):
                for k in range(3):
                    placer(batterie, charley() * 0.7, t + k * STEP / 3)
            mel = MELODIE[(m % 2) * 16 + p]
            if mel is not None:
                placer(melodie, cloche(note(mel)), t)
        m += 1

    mix = 0.9 * basse + 0.7 * batterie + 0.55 * melodie
    mix = mix[: int(duree * SR)]

    # Coupures (flash-backs) : batterie et basse retirées, mélodie filtrée passe-bas, puis drop
    for a, b in coupures:
        ia, ib = int(a * SR), min(len(mix), int(b * SR))
        if ib <= ia:
            continue
        bb, aa = signal.butter(2, 600 / (SR / 2), btype="low")
        filtre = signal.lfilter(bb, aa, melodie[ia:ib]) * 0.8
        fondu = min(int(0.05 * SR), (ib - ia) // 2)
        mix[ia:ib] = mix[ia:ib] * (1 - np.clip(np.arange(ib - ia) / max(fondu, 1), 0, 1)) + filtre
        # riser juste avant le drop
        r = riser(min(1.5, (b - a)))
        placer(mix, r * 0.6, b - len(r) / SR)
        placer(mix, impact() * 0.8, b)

    return normaliser(mix, -1.0)


# ---------------------------------------------------------------- bruitages
def whoosh(duree=0.45):
    n = int(duree * SR)
    bruit = RNG.standard_normal(n)
    out = np.zeros(n)
    bloc = 512
    for i in range(0, n, bloc):
        x = i / n
        fc = 300 + 5000 * np.sin(np.pi * x) ** 2
        b, a = signal.butter(2, [max(fc * 0.6, 50) / (SR / 2), min(fc * 1.6, SR / 2 - 100) / (SR / 2)], btype="band")
        out[i:i + bloc] = signal.lfilter(b, a, bruit[i:i + bloc])
    env = np.sin(np.pi * np.linspace(0, 1, n)) ** 1.5
    return normaliser(out * env, -6.0)


def impact(duree=1.2):
    n = int(duree * SR)
    t = np.arange(n) / SR
    f = 45 + 120 * np.exp(-t / 0.04)
    boum = np.sin(2 * np.pi * np.cumsum(f) / SR) * env_exp(n, 0.35)
    bruit = RNG.standard_normal(n)
    b, a = signal.butter(2, 2500 / (SR / 2), btype="low")
    crac = signal.lfilter(b, a, bruit) * env_exp(n, 0.06)
    x = np.tanh(2.5 * (boum + 0.5 * crac))
    return normaliser(x, -3.0)


def riser(duree=1.5):
    n = int(duree * SR)
    t = np.arange(n) / SR
    f = 200 * (8 ** (t / duree))
    ton = np.sin(2 * np.pi * np.cumsum(f) / SR)
    bruit = RNG.standard_normal(n)
    b, a = signal.butter(2, 3000 / (SR / 2), btype="high")
    souffle = signal.lfilter(b, a, bruit)
    env = (t / duree) ** 2
    return normaliser((0.5 * ton + 0.5 * souffle) * env, -6.0)


BRUITAGES = {"whoosh": whoosh, "impact": impact, "riser": riser}


def piste_bruitages(evenements, duree):
    piste = np.zeros(int(duree * SR) + 2 * SR)
    for ev in evenements:
        nom = ev["type"]
        if nom not in BRUITAGES:
            raise ValueError(f"bruitage inconnu : {nom}")
        son = BRUITAGES[nom]() * float(ev.get("gain", 1.0))
        t = float(ev["t"])
        if nom == "riser":            # le riser se termine sur t (la révélation)
            t -= len(son) / SR
        placer(piste, son, max(0.0, t))
    return normaliser(piste[: int(duree * SR)], -1.0)


# ---------------------------------------------------------------- utilitaires
def normaliser(x, db):
    pic = np.max(np.abs(x)) or 1.0
    return x / pic * (10 ** (db / 20))


def ecrire_wav(chemin, x):
    stereo = np.stack([x, x], axis=1)
    wavfile.write(chemin, SR, (np.clip(stereo, -1, 1) * 32767).astype(np.int16))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    m = sp.add_parser("musique")
    m.add_argument("--duree", type=float, required=True)
    m.add_argument("--sortie", required=True)
    m.add_argument("--coupures", default="", help="intervalles de flash-back, ex. 20-28,45-50")
    b = sp.add_parser("bruitages")
    b.add_argument("--evenements", required=True, help="JSON : [{t, type, gain?}]")
    b.add_argument("--duree", type=float, required=True)
    b.add_argument("--sortie", required=True)
    u = sp.add_parser("un")
    u.add_argument("--type", choices=sorted(BRUITAGES), required=True)
    u.add_argument("--sortie", required=True)
    k = sp.add_parser("kicks")
    k.add_argument("--duree", type=float, required=True)
    k.add_argument("--coupures", default="")
    a = p.parse_args()

    if a.cmd == "musique":
        ecrire_wav(a.sortie, musique(a.duree, parse_coupures(a.coupures)))
    elif a.cmd == "bruitages":
        with open(a.evenements, encoding="utf-8") as f:
            ecrire_wav(a.sortie, piste_bruitages(json.load(f), a.duree))
    elif a.cmd == "un":
        ecrire_wav(a.sortie, BRUITAGES[a.type]())
    elif a.cmd == "kicks":
        json.dump(temps_kicks(a.duree, parse_coupures(a.coupures)), sys.stdout)
        print()
        return
    print(f"OK : {a.sortie}")


if __name__ == "__main__":
    main()

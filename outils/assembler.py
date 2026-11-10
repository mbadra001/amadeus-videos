#!/usr/bin/env python3
"""Assemble videos/NNN-slug/apercu.html à partir de kit/modele_apercu.html.

  python outils/assembler.py videos/NNN-slug [--titre "..."] [--duree 63.4]

Entrées dans le dossier de la vidéo :
  voix.srt     temps de chaque mot (sous-titres mot à mot)
  plans.js     la liste des plans, une ligne par plan :  plan(t0,(lt,u,t)=>{ ... });
  medias/      images (jpg/png/webp), cartes, drapeaux (drapeau_xx.svg)
  cles.json    optionnel : {"or": ["PÉTROLE", ...], "rouge": ["GUERRE", ...]} (mots clés surlignés)

Fonctions disponibles dans plans.js (voir kit/DA.md, section « Boîte à outils ») :
  plein(nom,u,[cx,cy,h],[cx,cy,h])   image plein écran recadrée en 9:16, poussée de c0 vers c1
  cadre(nom,u,y)                      image paysage entière dans un cadre doré, fond flou
  drapeau(code,x,y,largeur,t)         drapeau officiel qui flotte (fond : fondDrapeau(nom))
  fondRouge(nom) / fondDrapeau(nom)   fonds pour les gros chiffres et les drapeaux
  grosChiffre(txt,lt,y,taille,coul,sous) titre(txt,lt,y) mot(txt,lt,y,taille,coul)
  tampon(txt,lt,x,y,coul,rot) mention(txt,y,coul) sepiaTon(a) avion() missile() eclat()
  option {rewind:true} sur un plan : effet REWIND au début du plan
`nom` = nom de fichier dans medias/ sans extension.
"""
import argparse
import json
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
MODELE = RACINE / "kit" / "modele_apercu.html"
CLES_DEFAUT = {"or": [], "rouge": ["GUERRE", "MORTS", "ERREUR", "FRAPPE", "ATTAQUE", "MINES", "BOMBE"]}


def mots_srt(srt):
    blocs = Path(srt).read_text(encoding="utf-8").strip().split("\n\n")
    f = lambda x: int(x[:2]) * 3600 + int(x[3:5]) * 60 + int(x[6:8]) + int(x[9:12]) / 1000
    out = []
    for b in blocs:
        l = b.strip().split("\n")
        if len(l) < 3 or "-->" not in l[1]:
            continue
        a, c = l[1].split(" --> ")
        out.append([round(f(a.strip()), 3), round(f(c.strip()), 3), " ".join(l[2:])])
    return out


def toile(chemin):
    import numpy as np
    from PIL import Image, ImageFilter
    h, w = 1920, 1080
    rng = np.random.default_rng(5)
    n = np.asarray(Image.fromarray((rng.random((h, w)) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))).astype(np.float32) / 255
    t = (np.sin(np.arange(w)[None] * 1.6) * np.sin(np.arange(h)[:, None] * 1.8)) * 0.5 + (n - 0.5) * 1.2
    t = (t - t.min()) / (t.max() - t.min()) * 255
    Image.fromarray(t.astype(np.uint8)).save(chemin)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("dossier")
    p.add_argument("--titre", default=None)
    p.add_argument("--duree", type=float, default=None)
    a = p.parse_args()
    d = Path(a.dossier)
    medias = d / "medias"
    if not (medias / "toile.png").exists():
        toile(medias / "toile.png")
    fichiers = sorted(f.name for f in medias.iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".svg"))
    mots = mots_srt(d / "voix.srt")
    duree = a.duree or round(mots[-1][1] + 0.4, 2)
    plans = (d / "plans.js").read_text(encoding="utf-8")
    cles = dict(CLES_DEFAUT)
    if (d / "cles.json").exists():
        cles.update(json.loads((d / "cles.json").read_text(encoding="utf-8")))
    # contrôles : images citées dans plans.js présentes dans medias/
    noms = {Path(f).stem for f in fichiers}
    cites = set(re.findall(r"(?:plein|cadre|fondRouge|fondDrapeau)\('([^']+)'", plans)) | {"drapeau_" + c for c in re.findall(r"drapeau\('([a-z]{2})'", plans)}
    manquants = sorted(cites - noms)
    if manquants:
        raise SystemExit(f"ERREUR assembler.py : images absentes de medias/ : {', '.join(manquants)}")
    t0 = [float(x) for x in re.findall(r"^plan\(([\d.]+)", plans, re.M)]
    durees = [b - a_ for a_, b in zip(t0, t0[1:] + [duree])]
    g = MODELE.read_text(encoding="utf-8")
    rempl = {"__TITRE__": a.titre or d.name, "__DUREE__": str(duree), "__FICHIERS__": json.dumps(fichiers),
             "__MOTS__": json.dumps(mots, ensure_ascii=False), "__PLANS__": plans,
             "__CLES_OR__": json.dumps([c.upper() for c in cles["or"]], ensure_ascii=False),
             "__CLES_RG__": json.dumps([c.upper() for c in cles["rouge"]], ensure_ascii=False)}
    for k, v in rempl.items():
        g = g.replace(k, v)
    (d / "apercu.html").write_text(g, encoding="utf-8")
    utilisees = {}
    for n in re.findall(r"(?:plein|cadre)\('([^']+)'", plans):
        utilisees[n] = utilisees.get(n, 0) + 1
    print(f"OK : {d / 'apercu.html'} — {len(t0)} plans, durée {duree} s, plan moyen {sum(durees) / len(durees):.2f} s, "
          f"plus long {max(durees):.2f} s, {len(utilisees)} images différentes"
          + (f" ; utilisées plus de 2 fois : {', '.join(k for k, v in utilisees.items() if v > 2)}" if any(v > 2 for v in utilisees.values()) else ""))


if __name__ == "__main__":
    main()

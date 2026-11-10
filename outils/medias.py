#!/usr/bin/env python3
"""Médias libres pour Amadeus : recherche, téléchargement, droits, crédits, rendu peinture.

Tout est écrit dans <dossier>/ (en général videos/NNN-slug/medias/) avec un credits.json
cumulatif : {fichier, source, titre, auteur, licence, page, credit}.

Sources d'images (de la plus précise à la plus générique) :
  loc       Bibliothèque du Congrès (photos historiques ; gardées seulement si
            « No known restrictions on publication » ou domaine public)
  nasa      NASA Image Library (domaine public : vues satellite, Terre depuis l'espace)
  aic       Art Institute of Chicago (tableaux du domaine public, CC0)
  cma       Cleveland Museum of Art (œuvres CC0 : tableaux, gravures, photographies anciennes)
  smk       SMK, galerie nationale du Danemark (tableaux du domaine public)
  openverse Openverse (Flickr, Wikimedia… ; CC0, PDM, CC BY, CC BY-SA)
  pexels    Pexels (photos modernes) — inactif tant qu'aucune clé n'est configurée
            (l'émission de clés Pexels est en pause en novembre 2026)
Musique :
  musique   Openverse audio (Jamendo, Wikimedia ; CC0, CC BY, CC BY-SA ; Freesound exclu,
            son serveur refuse les téléchargements automatiques)
Drapeaux :
  drapeau   flag-icons (GitHub lipis/flag-icons, licence MIT), codes ISO à 2 lettres : ir,us,fr…
Traitements :
  peinture  rendu peinture à l'huile légère (OpenCV) + étalonnage chaud + grain de toile
            (--doux : étalonnage seul, pour gravures et cartes anciennes)
  planche   planche-contact numérotée des images d'un dossier, pour les vérifier à l'œil

Exemples :
  python outils/medias.py loc "Khomeini 1979" videos/007-x/medias --n 4
  python outils/medias.py nasa "strait of hormuz" videos/007-x/medias --n 3
  python outils/medias.py aic "naval battle" videos/007-x/medias --n 2
  python outils/medias.py openverse "oil tanker" videos/007-x/medias --n 3
  python outils/medias.py musique "epic cinematic" videos/007-x/medias --n 1
  python outils/medias.py drapeau ir,us,sa videos/007-x/medias
  python outils/medias.py peinture videos/007-x/medias/loc_1.jpg videos/007-x/medias/p_loc_1.jpg
  python outils/medias.py planche videos/007-x/medias /tmp/planche.jpg

Rythme : une requête toutes les 1,5 s par source, nouvel essai sur 429/5xx.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

UA = "amadeus-videos/1.0 (outil de montage video ; https://github.com/mbadra001/amadeus-videos)"
LICENCES_OV = "cc0,pdm,by,by-sa"
_dernier = {}


# ----------------------------------------------------------------- réseau
def get(url, binaire=False, essais=4, entetes=None, cle="defaut"):
    for k in range(essais):
        attente = 1.5 - (time.time() - _dernier.get(cle, 0))
        if attente > 0:
            time.sleep(attente)
        _dernier[cle] = time.time()
        try:
            h = {"User-Agent": UA}
            h.update(entetes or {})
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=90) as r:
                data = r.read()
                return data if binaire else json.loads(data)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and k < essais - 1:
                time.sleep(10 * (k + 1))
                continue
            raise
        except urllib.error.URLError:
            if k < essais - 1:
                time.sleep(5)
                continue
            raise
    raise RuntimeError("échec après plusieurs essais")


def curl(url, dest, agent=True):
    """Téléchargement de fichier avec curl (certains serveurs refusent l'agent Python)."""
    cmd = ["curl", "-sSL", "--fail", "--retry", "3", "--max-time", "120", "-o", str(dest), url]
    if agent:
        cmd[1:1] = ["-A", UA]
    subprocess.run(cmd, check=True)


def enregistrer(dossier, entrees):
    f = Path(dossier) / "credits.json"
    anciens = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
    f.write_text(json.dumps(anciens + entrees, ensure_ascii=False, indent=1), encoding="utf-8")


def prochain_nom(dossier, prefixe, ext):
    i = 1
    while (Path(dossier) / f"{prefixe}_{i}.{ext}").exists():
        i += 1
    return f"{prefixe}_{i}.{ext}"


def image_ok(chemin, mini=900):
    try:
        from PIL import Image
        with Image.open(chemin) as im:
            return max(im.size) >= mini
    except Exception:
        return False


# ----------------------------------------------------------------- sources
def src_loc(q, dossier, n):
    url = f"https://www.loc.gov/photos/?q={urllib.parse.quote(q)}&fo=json&c={n * 5}&fa=online-format:image"
    pris = []
    for r in get(url, cle="loc").get("results", []):
        if len(pris) >= n:
            break
        try:
            item = get(r["id"].replace("http://", "https://").rstrip("/") + "/?fo=json", cle="loc")
        except Exception:
            continue
        it = item.get("item", {})
        droits = " ".join(it.get("rights_advisory") or []) if isinstance(it.get("rights_advisory"), list) else str(it.get("rights_advisory") or "")
        if not any(m in droits.lower() for m in ("no known restrictions", "public domain", "no known copyright")):
            continue
        fichiers = [f for res in item.get("resources", []) for grp in res.get("files", []) for f in grp
                    if f.get("mimetype") == "image/jpeg"]
        if not fichiers:
            continue
        meilleur = max(fichiers, key=lambda f: (f.get("width") or 0))
        nom = prochain_nom(dossier, "loc", "jpg")
        try:
            curl(meilleur["url"], Path(dossier) / nom)
        except Exception:
            continue
        if not image_ok(Path(dossier) / nom, 700):
            (Path(dossier) / nom).unlink(missing_ok=True)
            continue
        titre = it.get("title") or r.get("title", "")
        auteur = ", ".join(it.get("contributor_names") or []) or "Library of Congress"
        pris.append({"fichier": nom, "source": "loc", "titre": titre, "auteur": auteur, "licence": "domaine public / sans restriction connue",
                     "page": r["id"], "credit": f"{titre[:80]} — Library of Congress", "requete": q})
        print(f"  OK {nom} : {titre[:90]}")
    return pris


def src_nasa(q, dossier, n):
    d = get(f"https://images-api.nasa.gov/search?q={urllib.parse.quote(q)}&media_type=image", cle="nasa")
    pris = []
    for it in d["collection"]["items"]:
        if len(pris) >= n:
            break
        m = it["data"][0]
        nid = m["nasa_id"]
        nom = prochain_nom(dossier, "nasa", "jpg")
        ok = False
        for taille in ("large", "orig", "medium"):
            try:
                curl(f"https://images-assets.nasa.gov/image/{nid}/{nid}~{taille}.jpg", Path(dossier) / nom)
                if image_ok(Path(dossier) / nom):
                    ok = True
                    break
            except Exception:
                pass
        if not ok:
            (Path(dossier) / nom).unlink(missing_ok=True)
            continue
        pris.append({"fichier": nom, "source": "nasa", "titre": m.get("title"), "auteur": m.get("center", "NASA"), "licence": "domaine public (NASA)",
                     "page": f"https://images.nasa.gov/details/{nid}", "credit": f"{m.get('title', '')[:60]} — NASA", "date": m.get("date_created", "")[:10], "requete": q})
        print(f"  OK {nom} : {m.get('title', '')[:70]} ({m.get('date_created', '')[:10]})")
    return pris


def src_aic(q, dossier, n):
    d = get(f"https://api.artic.edu/api/v1/artworks/search?q={urllib.parse.quote(q)}&limit={n * 4}"
            "&fields=id,title,image_id,is_public_domain,artist_display,date_display", cle="aic")
    pris = []
    for r in d.get("data", []):
        if len(pris) >= n:
            break
        if not r.get("is_public_domain") or not r.get("image_id"):
            continue
        nom = prochain_nom(dossier, "aic", "jpg")
        try:
            curl(f"https://www.artic.edu/iiif/2/{r['image_id']}/full/1686,/0/default.jpg", Path(dossier) / nom, agent=False)
        except Exception:
            continue
        artiste = (r.get("artist_display") or "").split("\n")[0]
        pris.append({"fichier": nom, "source": "aic", "titre": r["title"], "auteur": artiste, "licence": "CC0 (Art Institute of Chicago)",
                     "page": f"https://www.artic.edu/artworks/{r['id']}", "credit": f"{r['title'][:60]} — {artiste} (domaine public)", "requete": q})
        print(f"  OK {nom} : {r['title'][:60]} — {artiste} {r.get('date_display', '')}")
    return pris


def src_cma(q, dossier, n):
    """Cleveland Museum of Art : œuvres CC0 (tableaux, gravures, photographies anciennes)."""
    d = get(f"https://openaccess-api.clevelandart.org/api/artworks/?q={urllib.parse.quote(q)}&has_image=1&cc0=1&limit={n * 3}", cle="cma")
    pris = []
    for r in d.get("data", []):
        if len(pris) >= n:
            break
        im = (r.get("images") or {})
        url = ((im.get("print") or {}).get("url")) or ((im.get("web") or {}).get("url"))
        if not url or r.get("share_license_status") != "CC0":
            continue
        nom = prochain_nom(dossier, "cma", "jpg")
        try:
            curl(url, Path(dossier) / nom)
        except Exception:
            continue
        auteur = ((r.get("creators") or [{}])[0].get("description") or "artiste inconnu")
        pris.append({"fichier": nom, "source": "cma", "titre": r.get("title"), "auteur": auteur, "licence": "CC0 (Cleveland Museum of Art)",
                     "page": r.get("url"), "credit": f"{r.get('title', '')[:60]} — {auteur} (domaine public)", "requete": q})
        print(f"  OK {nom} : {r.get('title', '')[:60]} — {auteur} {r.get('creation_date', '')}")
    return pris


def src_smk(q, dossier, n):
    """SMK, galerie nationale du Danemark : œuvres du domaine public."""
    d = get(f"https://api.smk.dk/api/v1/art/search/?keys={urllib.parse.quote(q)}&offset=0&rows={n * 3}"
            "&filters=%5Bpublic_domain:true%5D,%5Bhas_image:true%5D", cle="smk")
    pris = []
    for r in d.get("items", []):
        if len(pris) >= n:
            break
        url = r.get("image_native") or r.get("image_thumbnail")
        if not url or not r.get("public_domain"):
            continue
        nom = prochain_nom(dossier, "smk", "jpg")
        try:
            curl(url, Path(dossier) / nom)
        except Exception:
            continue
        if not image_ok(Path(dossier) / nom, 900):
            (Path(dossier) / nom).unlink(missing_ok=True)
            continue
        titre = ((r.get("titles") or [{}])[0].get("title") or q)
        auteur = ((r.get("production") or [{}])[0].get("creator") or "artiste inconnu")
        pris.append({"fichier": nom, "source": "smk", "titre": titre, "auteur": auteur, "licence": "domaine public (SMK)",
                     "page": f"https://open.smk.dk/artwork/image/{r.get('object_number', '')}", "credit": f"{titre[:60]} — {auteur} (SMK, domaine public)", "requete": q})
        print(f"  OK {nom} : {titre[:60]} — {auteur}")
    return pris


def jeton_openverse():
    f = os.environ.get("OPENVERSE_JETON")
    try:
        return json.load(open(f))["access_token"] if f else None
    except Exception:
        return None


def credit_ov(r):
    lic = r["license"]
    lic = "domaine public" if lic == "pdm" else "CC0" if lic == "cc0" else f"CC {lic.upper()} {r.get('license_version') or ''}".strip()
    return f"{r['title'][:70]} — {r.get('creator') or 'auteur inconnu'} ({lic})", lic


def miniature_wikimedia(url, largeur=1280):
    pre = "https://upload.wikimedia.org/wikipedia/commons/"
    if not url.startswith(pre) or "/thumb/" in url:
        return url
    chemin = url[len(pre):]
    nom = chemin.rsplit("/", 1)[-1]
    suf = ".jpg" if nom.lower().endswith((".tif", ".tiff")) else ".png" if nom.lower().endswith(".svg") else ""
    return f"{pre}thumb/{chemin}/{largeur}px-{nom}{suf}"


def src_openverse(q, dossier, n, audio=False):
    t = "audio" if audio else "images"
    ent = {"Authorization": "Bearer " + jeton_openverse()} if jeton_openverse() else {}
    extra = "&source=jamendo" if audio else ""
    d = get(f"https://api.openverse.org/v1/{t}/?q={urllib.parse.quote(q)}&license={LICENCES_OV}&page_size={max(n * 4, 10)}&mature=false{extra}",
            entetes=ent, cle="openverse")
    pris = []
    for r in d.get("results", []):
        if len(pris) >= n:
            break
        if audio and (r.get("source") == "freesound" or any(m in (r.get("title", "") + " " + str(r.get("tags", ""))).lower() for m in ("suno", " ai ", "ai-generated", "udio"))):
            continue
        if not audio and max(r.get("width") or 0, r.get("height") or 0) < 1000:
            continue
        ext = "mp3" if audio else (r.get("filetype") or "jpg").lower().replace("jpeg", "jpg")[:4]
        nom = prochain_nom(dossier, "musique" if audio else "ov", ext)
        try:
            curl(r["url"] if audio else miniature_wikimedia(r["url"]), Path(dossier) / nom)
        except Exception as e:
            print(f"  saute {r['url'][:70]} : {e}", file=sys.stderr)
            continue
        cr, lic = credit_ov(r)
        pris.append({"fichier": nom, "source": f"openverse/{r.get('source')}", "titre": r["title"], "auteur": r.get("creator"),
                     "licence": lic, "page": r.get("foreign_landing_url"), "credit": cr, "requete": q,
                     **({"duree_s": (r.get("duration") or 0) / 1000} if audio else {})})
        print(f"  OK {nom} : {cr}")
    return pris


def src_pexels(q, dossier, n):
    """La clé Pexels est injectée par le proxy de l'environnement (en-tête Authorization)."""
    d = get(f"https://api.pexels.com/v1/search?query={urllib.parse.quote(q)}&per_page={n * 2}&orientation=portrait",
            entetes={"Authorization": os.environ.get("PEXELS_CLE_FACTICE", "cle-injectee-par-le-proxy")}, cle="pexels")
    pris = []
    for p in d.get("photos", [])[:n]:
        nom = prochain_nom(dossier, "pexels", "jpg")
        try:
            curl(p["src"]["large2x"], Path(dossier) / nom)
        except Exception:
            continue
        pris.append({"fichier": nom, "source": "pexels", "titre": p.get("alt") or q, "auteur": p.get("photographer"), "licence": "licence Pexels",
                     "page": p.get("url"), "credit": f"Photo {p.get('photographer')} (Pexels)", "requete": q})
        print(f"  OK {nom} : {p.get('alt', '')[:60]} — {p.get('photographer')}")
    return pris


def drapeaux(codes, dossier):
    pris = []
    for c in codes.split(","):
        c = c.strip().lower()
        nom = f"drapeau_{c}.svg"
        curl(f"https://raw.githubusercontent.com/lipis/flag-icons/main/flags/4x3/{c}.svg", Path(dossier) / nom)
        pris.append({"fichier": nom, "source": "flag-icons", "titre": f"drapeau {c}", "auteur": "lipis/flag-icons", "licence": "MIT", "page": "https://github.com/lipis/flag-icons", "credit": ""})
        print(f"  OK {nom}")
    return pris


# ----------------------------------------------------------------- traitements
def peinture(src, dst, larg=1920, doux=False):
    import cv2
    import numpy as np
    im = cv2.imread(str(src))
    if im is None:
        from PIL import Image
        im = cv2.cvtColor(np.asarray(Image.open(src).convert("RGB")), cv2.COLOR_RGB2BGR)
    h, w = im.shape[:2]
    if max(h, w) > larg:
        k = larg / max(h, w)
        im = cv2.resize(im, (int(w * k), int(h * k)), interpolation=cv2.INTER_AREA)
    if doux:
        b = im
    else:   # peinture à l'huile légère : touches de pinceau mais détails gardés
        b = cv2.addWeighted(cv2.xphoto.oilPainting(im, 4, 1), 0.7, cv2.bilateralFilter(im, 7, 40, 40), 0.3, 0)
    f = b.astype(np.float32) / 255
    l = f.mean(-1, keepdims=True)
    f = np.clip((f * 0.82 + l * 0.18) * np.array([0.82, 0.97, 1.07]), 0, 1) ** 1.06   # BGR : ombres brunes, lumières dorées
    hh, ww = f.shape[:2]
    rng = np.random.default_rng(1)
    toile = (np.sin(np.arange(ww)[None] * 2.1) * np.sin(np.arange(hh)[:, None] * 2.3)) * 0.02 + rng.normal(0, 0.012, (hh, ww))
    f = np.clip(f + toile[..., None], 0, 1)
    cv2.imwrite(str(dst), (f * 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 90])


def planche(dossier, sortie):
    from PIL import Image, ImageDraw
    fs = sorted(p for p in Path(dossier).iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))
    col, tw, th = 5, 300, 260
    g = Image.new("RGB", (col * tw, ((len(fs) + col - 1) // col) * th), "black")
    d = ImageDraw.Draw(g)
    for i, f in enumerate(fs):
        try:
            im = Image.open(f).convert("RGB")
        except Exception:
            continue
        im.thumbnail((tw - 6, th - 30))
        x, y = (i % col) * tw, (i // col) * th
        g.paste(im, (x + 3, y + 3))
        d.text((x + 4, y + th - 24), f"{f.name} {im.size[0]}px", fill="yellow")
    g.save(sortie, quality=85)
    print(f"OK planche : {sortie} ({len(fs)} images)")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mode", choices=["loc", "nasa", "aic", "cma", "smk", "openverse", "pexels", "musique", "drapeau", "peinture", "planche"])
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--n", type=int, default=3)
    p.add_argument("--doux", action="store_true")
    x = p.parse_args()
    if x.mode == "peinture":
        peinture(x.a, x.b, doux=x.doux)
    elif x.mode == "planche":
        planche(x.a, x.b)
    else:
        Path(x.b).mkdir(parents=True, exist_ok=True)
        f = {"loc": src_loc, "nasa": src_nasa, "aic": src_aic, "cma": src_cma, "smk": src_smk, "openverse": src_openverse, "pexels": src_pexels}
        try:
            if x.mode == "drapeau":
                r = drapeaux(x.a, x.b)
            elif x.mode == "musique":
                r = src_openverse(x.a, x.b, x.n, audio=True)
            else:
                r = f[x.mode](x.a, x.b, x.n)
        except Exception as e:
            print(f"ERREUR {x.mode} « {x.a} » : {e}", file=sys.stderr)
            sys.exit(1)
        enregistrer(x.b, r)
        if not r:
            print(f"aucun résultat utilisable pour « {x.a} » ({x.mode})", file=sys.stderr)

#!/usr/bin/env python3
"""Médias libres pour Amadeus : recherche, téléchargement, droits, crédits, rendu peinture.

Tout est écrit dans <dossier>/ (en général videos/NNN-slug/medias/) avec un credits.json
cumulatif : {fichier, source, titre, auteur, licence, page, credit}.

Sources d'images (de la plus précise à la plus générique) :
  wiki      Wikipédia : TOUTES les images libres d'un article (une requête), avec licence et auteur.
            Le plus précis pour un sujet nommé : « Iran Air Flight 655 », « USS Vincennes (CG-49) »,
            « fr:Canal de Suez ». Préfixe de langue possible (fr:, en:, de:…), défaut en:.
            Seules les licences libres sont gardées (domaine public, CC0, CC BY, CC BY-SA).
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

Mode rapide (recommandé) : toutes les recherches d'un coup, en parallèle, avec tri automatique
  python outils/medias.py lot videos/007-x/images.json videos/007-x/medias
  images.json : [{"source":"wiki","q":"Iran Air Flight 655","n":6}, {"source":"loc","q":"Khomeini","n":3},
                 {"source":"drapeau","q":"ir,us"}, {"source":"musique","q":"epic cinematic","n":1}, ...]
  Les sources tournent en même temps (une file par source, débit poli), puis le tri automatique écarte
  les images trop petites, sombres, plates, floues ou en double, et une planche-contact est écrite.
  python outils/medias.py tri videos/007-x/medias            tri automatique seul
  python outils/medias.py retirer videos/007-x/medias a,b    supprime des images (et leurs crédits)
  python outils/medias.py peindre-tout videos/007-x/medias   rendu peinture de toutes les images, en parallèle

Exemples (une source à la fois) :
  python outils/medias.py wiki "Iran Air Flight 655" videos/007-x/medias --n 6
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
import concurrent.futures
import html
import json
import os
import re
import subprocess
import sys
import threading
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

UA = "amadeus-videos/1.0 (outil de montage video ; https://github.com/mbadra001/amadeus-videos)"
LICENCES_OV = "cc0,pdm,by,by-sa"
_dernier = {}
_ctx = threading.local()      # étiquette des noms de fichiers (loc_khomeini_1.jpg), propre à chaque fil


def slug(q):
    s = unicodedata.normalize("NFKD", q).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:24] or "img"


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
    etiq = getattr(_ctx, "etiq", "")
    base = f"{prefixe}_{etiq}" if etiq else prefixe
    i = 1
    while (Path(dossier) / f"{base}_{i}.{ext}").exists():
        i += 1
    return f"{base}_{i}.{ext}"


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
        _ctx.etiq = "" if audio else getattr(_ctx, "etiq", "")
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


# ----------------------------------------------------------------- Wikipédia
WIKI_EXCLUS = re.compile(r"flag of|logo|icon|crest|seal of|coat of arms|signature|blank|locator|location map|commons-|"
                         r"wikisource|symbol|emblem|stub|ambox|question mark|padlock|portal|edit-|nuvola|oojs|banner", re.I)
LIC_OK = re.compile(r"public domain|^pd\b|^pd-|cc0|cc[ -]by(-sa)?[ -]?\d|attribution|no restrictions|free use|\bgov", re.I)
LIC_NON = re.compile(r"-nc|-nd|non.?commercial|fair use|noderiv", re.I)


def propre(h):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h or ""))).strip()


def wiki_api(lang, params, patience=100):
    """API Wikipédia. Le débit anonyme est limité par adresse (partagée entre sessions cloud) : en cas de 429,
    on attend exactement la durée demandée par le serveur (en-tête Retry-After), dans la limite de `patience` secondes."""
    q = urllib.parse.urlencode({"format": "json", "redirects": 1, **params})
    debut = time.time()
    while True:
        try:
            return get(f"https://{lang}.wikipedia.org/w/api.php?{q}", essais=1, cle="wiki")
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            attente = min(int(e.headers.get("Retry-After") or 20) + 1, 90)
            if time.time() - debut + attente > patience:
                raise RuntimeError(f"Wikimedia limite le débit (429, attente demandée {attente} s) : abandon après {patience} s")
            time.sleep(attente)


def _suivre(correspondances, titre):
    """Titre final d'un article après normalisation et redirections renvoyées par l'API."""
    for liste in correspondances:
        titre = next((c["to"] for c in liste if c["from"] == titre), titre)
    return titre


def wiki_lot(rs, dossier, budget=170):
    """Images libres de plusieurs articles Wikipédia avec très peu de requêtes (la limite de débit est partagée) :
    1 requête pour les listes d'images de tous les articles, 1 pour les licences (par paquets de 30), puis les téléchargements.
    `budget` : durée maximale en secondes ; au-delà, les articles restants sont ignorés. Wikimedia limite fortement le débit
    depuis les serveurs cloud (adresse partagée) : ne jamais en dépendre, la liste des articles est donc à classer par priorité."""
    debut = time.time()
    par_langue = {}
    for r in rs:
        m = re.match(r"^([a-z]{2,3}):(.+)$", r["q"])
        lang, titre = m.groups() if m else ("en", r["q"])
        par_langue.setdefault(lang, []).append((r, titre))
    pris = []
    for lang, items in par_langue.items():
        # 1) liste des images de chaque article (une seule requête, suites comprises)
        pages, corr = {}, []
        params = {"action": "query", "titles": "|".join(t for _, t in items), "prop": "images", "imlimit": "max"}
        while True:
            d = wiki_api(lang, params)
            q_ = d.get("query") or {}
            corr = [q_.get("normalized", []), q_.get("redirects", [])]
            for pg in q_.get("pages", {}).values():
                pages.setdefault(pg["title"], {"images": [], "missing": "missing" in pg})["images"] += [i["title"] for i in pg.get("images", [])]
            if "continue" not in d:
                break
            params = {**params, **d["continue"]}
        # articles introuvables : on cherche le plus proche
        resolus = {}
        for r, t in items:
            final = _suivre(corr, t)
            if final not in pages or pages[final]["missing"]:
                h = (wiki_api(lang, {"action": "query", "list": "search", "srsearch": t, "srlimit": 1}).get("query") or {}).get("search", [])
                if h:
                    d2 = wiki_api(lang, {"action": "query", "titles": h[0]["title"], "prop": "images", "imlimit": "max"})
                    for pg in (d2.get("query") or {}).get("pages", {}).values():
                        pages[pg["title"]] = {"images": [i["title"] for i in pg.get("images", [])], "missing": False}
                    final = h[0]["title"]
            resolus[t] = final
        # 2) licences et adresses des fichiers retenus (paquets de 30)
        fichiers = sorted({f for t in resolus.values() for f in pages.get(t, {}).get("images", [])
                           if re.search(r"\.(jpe?g|png)$", f, re.I) and not WIKI_EXCLUS.search(f)})
        info = {}
        for k in range(0, len(fichiers), 30):
            d = wiki_api(lang, {"action": "query", "titles": "|".join(fichiers[k:k + 30]), "prop": "imageinfo",
                                "iiprop": "url|extmetadata|size|mime", "iiurlwidth": 1600,
                                "iiextmetadatafilter": "LicenseShortName|Artist|NonFree"})
            for pg in (d.get("query") or {}).get("pages", {}).values():
                ii = (pg.get("imageinfo") or [None])[0]
                if not ii or ii.get("mime") not in ("image/jpeg", "image/png"):
                    continue
                md = ii.get("extmetadata") or {}
                lic = (md.get("LicenseShortName") or {}).get("value", "")
                if (md.get("NonFree") or {}).get("value", "").lower() == "true" or LIC_NON.search(lic) or not LIC_OK.search(lic):
                    continue
                if max(ii.get("width", 0), ii.get("height", 0)) < 1000:
                    continue
                info[pg["title"]] = (ii, lic, propre((md.get("Artist") or {}).get("value", "")))
        # 3) téléchargements, article par article
        for r, t in items:
            if time.time() - debut > budget:
                print(f"  wiki : budget de {budget} s dépassé, « {t} » ignoré")
                continue
            final = resolus[t]
            cands = [(f, *info[f]) for f in pages.get(final, {}).get("images", []) if f in info]
            cands.sort(key=lambda c: (c[1].get("mime") != "image/jpeg", -(c[1].get("width", 0) * c[1].get("height", 0))))
            _ctx.etiq = slug(r.get("etiquette") or t)
            n_ok = 0
            for f, ii, lic, auteur in cands:
                if n_ok >= r.get("n", 3) or time.time() - debut > budget:
                    break
                nom = prochain_nom(dossier, "wiki", "jpg")
                try:
                    subprocess.run(["curl", "-sSL", "--fail", "--retry", "4", "--retry-delay", "3", "--max-time", "90", "-A", UA,
                                    "-o", str(Path(dossier) / nom), ii.get("thumburl") or ii["url"]], check=True)
                except Exception:
                    (Path(dossier) / nom).unlink(missing_ok=True)
                    continue
                if not image_ok(Path(dossier) / nom, 900):
                    (Path(dossier) / nom).unlink(missing_ok=True)
                    continue
                titre_f = re.sub(r"^[^:]+:", "", f).rsplit(".", 1)[0]
                auteur = auteur[:60] or "auteur inconnu"
                pris.append({"fichier": nom, "source": f"wikipedia/{lang}", "titre": titre_f, "auteur": auteur, "licence": lic,
                             "page": ii.get("descriptionurl"), "article": final, "credit": f"{titre_f[:60]} — {auteur} ({lic})", "requete": r["q"]})
                print(f"  OK {nom} : {titre_f[:70]} ({lic})")
                n_ok += 1
                time.sleep(0.6)
            if n_ok == 0:
                print(f"  aucune image libre exploitable : wiki « {t} »")
    return pris


def src_wiki(q, dossier, n):
    return wiki_lot([{"q": q, "n": n}], dossier)


SOURCES = {"loc": src_loc, "nasa": src_nasa, "aic": src_aic, "cma": src_cma, "smk": src_smk,
           "openverse": src_openverse, "pexels": src_pexels, "wiki": src_wiki}


# ----------------------------------------------------------------- lot, tri, peinture en parallèle
def lot(fichier, dossier):
    """Exécute toutes les recherches d'un fichier JSON : une file par source, les sources en parallèle."""
    requetes = json.load(open(fichier, encoding="utf-8"))
    Path(dossier).mkdir(parents=True, exist_ok=True)
    groupes = {}
    for r in requetes:
        groupes.setdefault(r["source"], []).append(r)

    def courir(source, rs):
        sortie = []
        if source == "wiki":      # tous les articles ensemble : très peu de requêtes
            try:
                return wiki_lot(rs, dossier)
            except Exception as e:
                print(f"  ERREUR wiki : {e}", file=sys.stderr)
                return []
        for r in rs:
            _ctx.etiq = slug(r.get("etiquette") or r["q"])
            try:
                if source == "drapeau":
                    res = drapeaux(r["q"], dossier)
                elif source == "musique":
                    res = src_openverse(r["q"], dossier, r.get("n", 1), audio=True)
                else:
                    res = SOURCES[source](r["q"], dossier, r.get("n", 3))
            except Exception as e:
                print(f"  ERREUR {source} « {r['q']} » : {e}", file=sys.stderr)
                continue
            if not res:
                print(f"  aucun résultat utilisable : {source} « {r['q']} »")
            sortie += res
        return sortie

    debut = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(groupes)) as ex:
        res = [f.result() for f in [ex.submit(courir, s, rs) for s, rs in groupes.items()]]
    toutes = [e for r in res for e in r]
    enregistrer(dossier, toutes)
    print(f"lot : {len(toutes)} fichiers en {time.time() - debut:.0f} s ({len(requetes)} recherches, {len(groupes)} sources en parallèle)")


def _dhash(g):
    import cv2
    d = cv2.resize(g, (9, 8))
    return int("".join("1" if b else "0" for b in (d[:, 1:] > d[:, :-1]).flatten()), 2)


def tri_auto(dossier, mini=900, supprimer=True):
    """Écarte les images trop petites, sombres, claires, plates, floues ou en double (garde la plus grande)."""
    import cv2
    dossier = Path(dossier)
    fs = [f for f in sorted(dossier.iterdir()) if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
          and not f.name.startswith(("c_", "p_", "toile"))]
    mesures = []
    rejets = []
    for f in fs:
        im = cv2.imread(str(f))
        if im is None:
            rejets.append((f, "illisible"))
            continue
        h, w = im.shape[:2]
        if max(h, w) < mini:
            rejets.append((f, f"trop petite ({w}x{h})"))
            continue
        k = 512 / max(h, w)
        g = cv2.cvtColor(cv2.resize(im, (max(int(w * k), 9), max(int(h * k), 8))), cv2.COLOR_BGR2GRAY)
        moy, ecart, nettete = float(g.mean()), float(g.std()), float(cv2.Laplacian(g, cv2.CV_64F).var())
        if moy < 20:
            rejets.append((f, f"trop sombre ({moy:.0f})"))
        elif moy > 238:
            rejets.append((f, f"trop claire ({moy:.0f})"))
        elif ecart < 15:
            rejets.append((f, f"image plate ({ecart:.0f})"))
        elif nettete < 8:
            rejets.append((f, f"floue ({nettete:.0f})"))
        else:
            mesures.append((w * h, f, _dhash(g)))
    gardes = []
    for pixels, f, hh in sorted(mesures, key=lambda m: -m[0]):    # les plus grandes d'abord
        doublon = next((g for _, g, gh in gardes if bin(hh ^ gh).count("1") <= 5), None)
        if doublon:
            rejets.append((f, f"doublon de {doublon.name}"))
        else:
            gardes.append((pixels, f, hh))
    for f, raison in rejets:
        print(f"  écartée {f.name} : {raison}")
        if supprimer:
            f.unlink(missing_ok=True)
    if supprimer and rejets:
        retirer_credits(dossier, [f.name for f, _ in rejets])
    print(f"tri : {len(gardes)} gardées, {len(rejets)} écartées")
    return [f.name for _, f, _ in gardes]


def retirer_credits(dossier, noms):
    f = Path(dossier) / "credits.json"
    if f.exists():
        c = [e for e in json.loads(f.read_text(encoding="utf-8")) if e.get("fichier") not in set(noms)]
        f.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")


def retirer(dossier, liste):
    noms = []
    for n in liste.split(","):
        n = n.strip()
        for f in Path(dossier).glob(n if "." in n else n + ".*"):
            f.unlink()
            noms.append(f.name)
            print(f"  retirée {f.name}")
    retirer_credits(dossier, noms)


def _peindre_un(args):
    chemin, doux = args
    chemin = Path(chemin)
    tmp = chemin.with_name(chemin.stem + ".tmp.jpg")
    peinture(chemin, tmp, doux=doux)
    final = chemin.with_suffix(".jpg")
    chemin.unlink()
    tmp.rename(final)
    return chemin.name, final.name


def peindre_tout(dossier):
    """Rend toutes les images en peinture (en place, en parallèle). Gravures et tableaux (aic, cma, smk) : étalonnage seul."""
    dossier = Path(dossier)
    marque = dossier / "peint.json"
    deja = set(json.loads(marque.read_text()) if marque.exists() else [])
    fs = [f for f in sorted(dossier.iterdir()) if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
          and not f.name.startswith(("c_", "toile")) and f.stem not in deja]
    debut = time.time()
    with concurrent.futures.ProcessPoolExecutor(max_workers=os.cpu_count() or 2) as ex:
        res = list(ex.map(_peindre_un, [(f, f.name.startswith(("aic_", "cma_", "smk_"))) for f in fs]))
    f_cred = dossier / "credits.json"
    if f_cred.exists():
        chg = {a: b for a, b in res if a != b}
        c = json.loads(f_cred.read_text(encoding="utf-8"))
        for e in c:
            e["fichier"] = chg.get(e.get("fichier"), e.get("fichier"))
        f_cred.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
    marque.write_text(json.dumps(sorted(deja | {Path(b).stem for _, b in res})))
    print(f"peinture : {len(res)} images en {time.time() - debut:.0f} s")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mode", choices=["lot", "tri", "retirer", "peindre-tout", "wiki", "loc", "nasa", "aic", "cma", "smk",
                                    "openverse", "pexels", "musique", "drapeau", "peinture", "planche"])
    p.add_argument("a")
    p.add_argument("b", nargs="?")
    p.add_argument("--n", type=int, default=3)
    p.add_argument("--doux", action="store_true")
    p.add_argument("--planche", default=None, help="lot : chemin de la planche-contact (défaut : <dossier>/../planche_medias.jpg)")
    x = p.parse_args()
    if x.mode == "peinture":
        peinture(x.a, x.b, doux=x.doux)
    elif x.mode == "planche":
        planche(x.a, x.b)
    elif x.mode == "tri":
        tri_auto(x.a)
    elif x.mode == "retirer":
        retirer(x.a, x.b)
    elif x.mode == "peindre-tout":
        peindre_tout(x.a)
    elif x.mode == "lot":
        lot(x.a, x.b)
        tri_auto(x.b)
        planche(x.b, x.planche or str(Path(x.b).resolve().parent / "planche_medias.jpg"))
    else:
        Path(x.b).mkdir(parents=True, exist_ok=True)
        _ctx.etiq = slug(x.a)
        try:
            if x.mode == "drapeau":
                r = drapeaux(x.a, x.b)
            elif x.mode == "musique":
                r = src_openverse(x.a, x.b, x.n, audio=True)
            else:
                r = SOURCES[x.mode](x.a, x.b, x.n)
        except Exception as e:
            print(f"ERREUR {x.mode} « {x.a} » : {e}", file=sys.stderr)
            sys.exit(1)
        enregistrer(x.b, r)
        if not r:
            print(f"aucun résultat utilisable pour « {x.a} » ({x.mode})", file=sys.stderr)

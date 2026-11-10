#!/usr/bin/env python3
"""Cartes exactes (Natural Earth, domaine public) dessinées en style carte ancienne, format vertical.

  python outils/cartes.py sortie.png --bbox lon0 lat0 lon1 lat1 [--surligne IRN,IRQ]
       [--etiquettes "IRAN:53:32,IRAK:44:33:60"]   (NOM:lon:lat[:taille])
       [--route "56.2:26.6,60:25,72:20"] [--point 56.25:26.57]

--surligne prend les codes pays ISO à 3 lettres (ADM0_A3 de Natural Earth : FRA, USA, IRN, CHN, RUS...).
Les données (≈ 28 Mo) sont téléchargées une fois depuis GitHub (nvkelso/natural-earth-vector)
dans ~/.cache/amadeus/geo.

Rendu : papier vieilli, mers en lignes horizontales, terres hachurées, côtes dorées,
pays surlignés en rouge sang, étiquettes en capitales serif. 1080x1920.
"""
import argparse
import json
import math
import os
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
OR = (229, 181, 71)
ORF = (160, 120, 40)
ENCRE = (58, 38, 20)
PAPIER = (232, 214, 170)
MER = (176, 160, 122)
ROUGE = (150, 30, 30)


def police(taille, gras=False):
    for f in ["/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf" if gras else "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"]:
        if Path(f).exists():
            return ImageFont.truetype(f, taille)
    return ImageFont.load_default()


def projeteur(bbox):
    lon0, lat0, lon1, lat1 = bbox
    k = math.cos(math.radians((lat0 + lat1) / 2))
    # cadre vertical : on ajuste l'emprise pour remplir 1080x1920 sans déformation
    cx, cy = (lon0 + lon1) / 2, (lat0 + lat1) / 2
    lx, ly = (lon1 - lon0) * k, (lat1 - lat0)
    if lx / ly > W / H:
        ly = lx * H / W
    else:
        lx = ly * W / H
    def p(lon, lat):
        return ((lon - cx) * k / lx * W + W / 2, (cy - lat) / ly * H + H / 2)
    return p


def anneaux(geom):
    t = geom["type"]
    polys = geom["coordinates"] if t == "MultiPolygon" else [geom["coordinates"]]
    for poly in polys:
        for anneau in poly:
            yield anneau


GEO = Path(os.environ.get("AMADEUS_CACHE", Path.home() / ".cache" / "amadeus")) / "geo"
NE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/{}.geojson"
_cache = {}


def charger(geo, nom):
    if nom in _cache:
        return _cache[nom]
    f = Path(geo) / f"{nom}.geojson"
    if not f.exists() or f.stat().st_size < 1000:
        Path(geo).mkdir(parents=True, exist_ok=True)
        subprocess.run(["curl", "-sSL", "--fail", "--retry", "3", "-o", str(f), NE.format(nom)], check=True)
    _cache[nom] = json.load(open(f))["features"]
    return _cache[nom]


def dans(anneau, bbox, marge=5):
    lon0, lat0, lon1, lat1 = bbox
    xs = [c[0] for c in anneau]; ys = [c[1] for c in anneau]
    return not (max(xs) < lon0 - marge or min(xs) > lon1 + marge or max(ys) < lat0 - marge or min(ys) > lat1 + marge)


def carte(geo, sortie, bbox, surligne=(), etiquettes=(), route=None, point=None, seed=1):
    p = projeteur(bbox)
    rng = np.random.default_rng(seed)
    # papier vieilli
    fond = np.ones((H, W, 3), np.float32) * np.array(PAPIER, np.float32)
    bruit = np.asarray(Image.fromarray((rng.random((H // 8, W // 8)) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)).astype(np.float32) / 255
    fond *= (0.88 + 0.12 * bruit)[..., None]
    img = Image.fromarray(fond.astype(np.uint8))

    # masque des terres
    terre = Image.new("L", (W, H), 0)
    dt = ImageDraw.Draw(terre)
    for f in charger(geo, "ne_10m_land"):
        for a in anneaux(f["geometry"]):
            if dans(a, bbox):
                dt.polygon([p(*c) for c in a], fill=255)
    for f in charger(geo, "ne_10m_lakes"):
        for a in anneaux(f["geometry"]):
            if dans(a, bbox):
                dt.polygon([p(*c) for c in a], fill=0)
    pays = charger(geo, "ne_10m_admin_0_countries")
    surl = Image.new("L", (W, H), 0)
    ds = ImageDraw.Draw(surl)
    for f in pays:
        if f["properties"].get("ADM0_A3") in surligne:
            for a in anneaux(f["geometry"]):
                if dans(a, bbox):
                    ds.polygon([p(*c) for c in a], fill=255)

    # mer : teinte + lignes horizontales ondulées
    mer = Image.new("RGB", (W, H), MER)
    dm = ImageDraw.Draw(mer)
    for y in range(0, H, 14):
        pts = [(x, y + 2 * math.sin(x * 0.02 + y)) for x in range(0, W + 20, 20)]
        dm.line(pts, fill=(170, 150, 110), width=1)
    img = Image.composite(img, mer, terre)
    # terres : hachures diagonales
    hach = img.copy()
    dh = ImageDraw.Draw(hach)
    for k in range(-H, W, 11):
        dh.line([(k, 0), (k + H, H)], fill=(185, 160, 115), width=1)
    img = Image.composite(hach, img, terre)
    # pays surlignés
    if surligne:
        rouge = Image.new("RGB", (W, H), ROUGE)
        img = Image.composite(Image.blend(img, rouge, 0.45), img, surl)
    # frontières
    d = ImageDraw.Draw(img)
    for f in pays:
        for a in anneaux(f["geometry"]):
            if dans(a, bbox):
                d.line([p(*c) for c in a], fill=(120, 90, 55), width=2)
    # côtes dorées (contour du masque des terres) avec léger relief
    bord = terre.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(3))
    ombre = bord.filter(ImageFilter.GaussianBlur(6))
    img = Image.composite(Image.new("RGB", (W, H), (120, 85, 30)), img, ombre.point(lambda v: int(v * 0.5)))
    img = Image.composite(Image.new("RGB", (W, H), ORF), img, bord)
    d = ImageDraw.Draw(img)
    # graticule
    lon0, lat0, lon1, lat1 = bbox
    pas = 1 if lon1 - lon0 < 10 else 5 if lon1 - lon0 < 40 else 10
    for lon in range(int(lon0 // pas * pas) - 20, int(lon1) + 20, pas):
        d.line([p(lon, -80), p(lon, 85)], fill=(150, 120, 80), width=1)
    for lat in range(int(lat0 // pas * pas) - 20, int(lat1) + 20, pas):
        d.line([p(-180, lat), p(180, lat)], fill=(150, 120, 80), width=1)
    # route maritime
    if route:
        pts = [p(*map(float, c.split(":"))) for c in route.split(",")]
        for i in range(len(pts) - 1):
            x0, y0 = pts[i]; x1, y1 = pts[i + 1]
            n = int(math.hypot(x1 - x0, y1 - y0) / 18)
            for j in range(0, n, 2):
                a, b = j / n, min(1, (j + 1) / n)
                d.line([(x0 + (x1 - x0) * a, y0 + (y1 - y0) * a), (x0 + (x1 - x0) * b, y0 + (y1 - y0) * b)], fill=ROUGE, width=7)
    if point:
        x, y = p(*map(float, point.split(":")))
        for r, c in ((34, ROUGE), (22, PAPIER), (12, ROUGE)):
            d.ellipse([x - r, y - r, x + r, y + r], fill=c)
    # étiquettes
    for e in etiquettes:
        nom, lon, lat, *t = e.split(":")
        taille = int(t[0]) if t else 46
        x, y = p(float(lon), float(lat))
        f = police(taille, True)
        d.text((x, y), nom, font=f, fill=ENCRE, anchor="mm", stroke_width=4, stroke_fill=PAPIER)
    # rose des vents simple
    cx, cy = W - 170, 300
    for ang in range(0, 360, 45):
        r = 90 if ang % 90 == 0 else 50
        a = math.radians(ang)
        d.polygon([(cx, cy), (cx + math.cos(a + 0.18) * 22, cy + math.sin(a + 0.18) * 22), (cx + math.cos(a) * r, cy + math.sin(a) * r)], fill=ORF)
    d.text((cx, cy - 120), "N", font=police(40, True), fill=ENCRE, anchor="mm")
    # vieillissement : vignette brune
    a = np.asarray(img).astype(np.float32) / 255
    yy, xx = np.mgrid[0:H, 0:W]
    dist = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    a *= np.clip(1.1 - 0.45 * dist ** 1.6, 0.35, 1)[..., None]
    a = np.clip(a * np.array([1.0, 0.96, 0.86]), 0, 1)
    Image.fromarray((a * 255).astype(np.uint8)).save(sortie, quality=93)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("sortie")
    ap.add_argument("--geo", default=str(GEO))
    ap.add_argument("--bbox", nargs=4, type=float, required=True)
    ap.add_argument("--surligne", default="")
    ap.add_argument("--etiquettes", default="")
    ap.add_argument("--route", default=None)
    ap.add_argument("--point", default=None)
    x = ap.parse_args()
    carte(x.geo, x.sortie, x.bbox, [s for s in x.surligne.split(",") if s],
          [s for s in x.etiquettes.split(",") if s], x.route, x.point)

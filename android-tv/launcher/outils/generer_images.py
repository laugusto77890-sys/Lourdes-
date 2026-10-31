#!/usr/bin/env python3
"""Génère les fonds d'écran nature (paysages procéduraux originaux) et l'icône/bannière
d'Accueil Zen. Aucune image externe : tout est calculé ici, donc libre de droits.

Usage : python3 generer_images.py <dossier_assets_fonds> <dossier_res_drawable>
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

L, H = 1920, 1080
RNG = np.random.default_rng(14)


def melange(c1, c2, t):
    t = np.clip(t, 0, 1)[..., None]
    return np.asarray(c1, float) * (1 - t) + np.asarray(c2, float) * t


def degrade_vertical(stops, h=H, w=L):
    """stops : liste de (position 0..1, (r,g,b))."""
    y = np.linspace(0, 1, h)
    out = np.zeros((h, 3))
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        m = (y >= p0) & (y <= p1)
        t = (y[m] - p0) / max(p1 - p0, 1e-6)
        t = t * t * (3 - 2 * t)
        out[m] = melange(c0, c1, t)
    return np.repeat(out[:, None, :], w, axis=1)


def bruit_1d(n, octaves=6, persistance=0.5, base=3, graine=None):
    rng = np.random.default_rng(graine)
    x = np.linspace(0, 1, n)
    total = np.zeros(n)
    amp, freq, somme = 1.0, base, 0.0
    for _ in range(octaves):
        pts = rng.uniform(-1, 1, freq + 2)
        xp = np.linspace(0, 1, freq + 2)
        v = np.interp(x, xp, pts)
        # lissage cosinus entre points
        total += amp * v
        somme += amp
        amp *= persistance
        freq *= 2
    return total / somme


def crete(hauteur_moy, amplitude, graine, octaves=7, base=3, aigu=False):
    b = bruit_1d(L, octaves=octaves, base=base, graine=graine)
    if aigu:
        b = 1 - np.abs(b) * 2
    return (hauteur_moy - amplitude * b) * H


def peindre_couche(img, profil, couleur, brume=None, intensite_brume=0.0):
    yy = np.arange(H)[:, None]
    masque = yy >= profil[None, :]
    col = np.asarray(couleur, float)
    if brume is not None and intensite_brume > 0:
        # brume plus forte en haut de la couche
        prof = np.clip((yy - profil[None, :]) / (0.25 * H), 0, 1)
        t = intensite_brume * (1 - prof)
        couche = col[None, None, :] * (1 - t[..., None]) + np.asarray(brume, float)[None, None, :] * t[..., None]
    else:
        couche = np.broadcast_to(col, img.shape)
    img[masque] = couche[masque] if couche.shape == img.shape else np.broadcast_to(couche, img.shape)[masque]
    return img


def soleil(img, cx, cy, rayon, couleur, halo=6.0, force=1.0):
    yy, xx = np.mgrid[0:H, 0:L]
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    disque = np.clip((rayon - d) / 2.0, 0, 1)
    glow = np.exp(-(d / (rayon * halo)) ** 2) * 0.55 * force
    a = np.clip(disque + glow, 0, 1)[..., None]
    return img * (1 - a) + np.asarray(couleur, float) * a


def etoiles(img, n, graine, limite_y=1.0):
    rng = np.random.default_rng(graine)
    xs = rng.integers(0, L, n)
    ys = (rng.random(n) ** 1.6 * H * limite_y).astype(int)
    lum = rng.uniform(120, 255, n)
    for x, y, v in zip(xs, ys, lum):
        img[y, x] = np.maximum(img[y, x], v)
        if v > 235 and 0 < x < L - 1 and 0 < y < H - 1:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                img[y + dy, x + dx] = np.maximum(img[y + dy, x + dx], v * 0.45)
    return img


def reflet(img, y_eau, assombrir=0.75, teinte=(20, 40, 70), ondes=True):
    haut = img[:y_eau].copy()
    h_eau = H - y_eau
    miroir = haut[::-1][:h_eau]
    if miroir.shape[0] < h_eau:
        miroir = np.concatenate([miroir, np.repeat(miroir[-1:], h_eau - miroir.shape[0], 0)], 0)
    if ondes:
        rng = np.random.default_rng(3)
        res = np.empty_like(miroir)
        for i in range(h_eau):
            dec = int(math.sin(i * 0.35) * (1 + i / h_eau * 6) + rng.normal(0, 0.6 + i / h_eau * 2))
            res[i] = np.roll(miroir[i], dec, axis=0)
        miroir = res
    prof = np.linspace(0, 1, h_eau)[:, None, None]
    eau = miroir * assombrir * (1 - 0.35 * prof) + np.asarray(teinte, float) * (0.25 + 0.35 * prof)
    img[y_eau:] = np.clip(eau, 0, 255)
    # fine ligne de rivage
    img[y_eau:y_eau + 2] *= 0.8
    return img


def sapins(img, base_y, couleur, densite, hauteur, graine, brume=None, t_brume=0.0):
    rng = np.random.default_rng(graine)
    pil = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(pil)
    col = tuple(int(c) for c in couleur)
    x = -20
    while x < L + 20:
        h = hauteur * rng.uniform(0.6, 1.25)
        w = h * rng.uniform(0.28, 0.36)
        by = base_y[int(np.clip(x, 0, L - 1))] + rng.uniform(-6, 10)
        etages = 5
        for k in range(etages):
            t0 = by - h * (k / etages) * 0.95
            larg = w * (1 - k / etages) * 0.9 + w * 0.12
            d.polygon([(x - larg, t0), (x + larg, t0), (x, t0 - h * 0.38)], fill=col)
        d.rectangle([x - w * 0.05, by, x + w * 0.05, H], fill=col)
        x += rng.uniform(0.35, 1.0) * densite
    arr = np.asarray(pil).astype(float)
    # remplir sous la ligne d'arbres
    yy = np.arange(H)[:, None]
    m = yy >= (base_y[None, :] + 2)
    arr[m] = np.broadcast_to(np.asarray(col, float), arr.shape)[m]
    return arr


def grain(img, force=3.0, graine=0):
    rng = np.random.default_rng(graine)
    return img + rng.normal(0, force, img.shape)


def vignette(img, force=0.35):
    yy, xx = np.mgrid[0:H, 0:L]
    d = np.sqrt(((xx - L / 2) / (L / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    return img * (1 - force * np.clip(d - 0.55, 0, 1)[..., None])


def enregistrer(img, chemin, flou=0.6):
    pil = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    if flou:
        pil = pil.filter(ImageFilter.GaussianBlur(flou))
    pil.save(chemin, "JPEG", quality=86, optimize=True, progressive=True)


# ---------------------------------------------------------------- scènes

def aube_montagnes():
    img = degrade_vertical([(0, (28, 40, 82)), (0.35, (92, 92, 150)), (0.55, (238, 160, 120)), (0.66, (255, 214, 160)), (1, (255, 214, 160))])
    img = soleil(img, L * 0.62, H * 0.60, 46, (255, 240, 205), halo=7)
    couches = [
        (0.52, 0.10, 11, (150, 130, 170), True),
        (0.60, 0.12, 12, (110, 98, 146), True),
        (0.68, 0.10, 13, (78, 70, 118), False),
        (0.77, 0.08, 14, (52, 46, 86), False),
        (0.88, 0.06, 15, (30, 26, 54), False),
    ]
    for i, (hm, amp, g, col, aigu) in enumerate(couches):
        img = peindre_couche(img, crete(hm, amp, g, aigu=aigu), col, brume=(255, 200, 170), intensite_brume=0.55 - i * 0.1)
    return vignette(grain(img, 2.5, 1))


def lac_crepuscule():
    img = degrade_vertical([(0, (36, 30, 74)), (0.3, (122, 72, 132)), (0.5, (236, 128, 120)), (0.6, (255, 190, 140)), (1, (255, 190, 140))])
    img = soleil(img, L * 0.38, H * 0.57, 38, (255, 228, 190), halo=8)
    img = peindre_couche(img, crete(0.50, 0.16, 21, aigu=True), (98, 66, 118), brume=(240, 150, 140), intensite_brume=0.5)
    img = peindre_couche(img, crete(0.56, 0.08, 22), (54, 40, 82), brume=(200, 120, 130), intensite_brume=0.3)
    base = np.full(L, H * 0.62) + bruit_1d(L, 4, graine=23) * 6
    img = sapins(img, base, (24, 20, 40), 22, 46, 24)
    img = reflet(img, int(H * 0.64), assombrir=0.8, teinte=(40, 30, 70))
    return vignette(grain(img, 2.5, 2))


def foret_brume():
    img = degrade_vertical([(0, (176, 202, 204)), (0.6, (214, 228, 222)), (1, (214, 228, 222))])
    img = soleil(img, L * 0.72, H * 0.28, 60, (250, 252, 240), halo=5, force=0.8)
    teintes = [(150, 176, 172), (118, 148, 142), (86, 116, 108), (56, 84, 76), (32, 54, 46), (18, 34, 28)]
    for i, col in enumerate(teintes):
        base = crete(0.40 + i * 0.1, 0.05, 30 + i, octaves=4)
        img = sapins(img, base, col, 26 + i * 10, 70 + i * 34, 40 + i)
        # brume entre les rangées
        yy = np.arange(H)[:, None, None]
        voile = np.exp(-((yy - (0.42 + i * 0.1) * H - 60) / 90.0) ** 2) * 0.35
        img = img * (1 - voile) + np.array([226, 234, 230]) * voile
    return vignette(grain(img, 2.0, 3), 0.25)


def aurore():
    img = degrade_vertical([(0, (4, 8, 22)), (0.5, (10, 24, 48)), (0.7, (18, 40, 62)), (1, (18, 40, 62))])
    img = etoiles(img, 1400, 50, 0.7)
    yy, xx = np.mgrid[0:H, 0:L].astype(float)
    for k, (col, y0, amp, ph) in enumerate([((60, 255, 170), 0.30, 0.08, 0.0), ((80, 220, 255), 0.22, 0.06, 1.7), ((170, 110, 255), 0.16, 0.05, 3.1)]):
        centre = (y0 + amp * np.sin(xx / L * 5.5 + ph) + 0.03 * np.sin(xx / L * 17 + ph * 2)) * H
        dist = (centre - yy)
        rideau = np.where(dist > 0, np.exp(-dist / (H * 0.16)), np.exp(dist / 14.0))
        stries = 0.75 + 0.25 * np.sin(xx / 11.0 + np.sin(xx / 70.0 + k) * 3) ** 2
        a = np.clip(rideau * stries * (0.5 - k * 0.12), 0, 1)[..., None]
        img = img + np.asarray(col, float) * a * 0.9
    img = peindre_couche(img, crete(0.60, 0.13, 51, aigu=True), (14, 22, 36))
    # neige légère sur les sommets
    prof = crete(0.60, 0.13, 51, aigu=True)
    ep = np.clip((H * 0.58 - prof) / (H * 0.1), 0, 1) * 26
    m = (yy >= prof[None, :]) & (yy < prof[None, :] + ep[None, :])
    img[m] = img[m] * 0.55 + np.array([70, 96, 118]) * 0.45
    base = np.full(L, H * 0.70) + bruit_1d(L, 4, graine=52) * 5
    img = sapins(img, base, (6, 12, 18), 18, 40, 53)
    img = reflet(img, int(H * 0.72), assombrir=0.7, teinte=(5, 15, 30))
    return grain(img, 2.0, 4)


def dunes():
    img = degrade_vertical([(0, (70, 120, 180)), (0.4, (180, 170, 170)), (0.55, (250, 190, 130)), (1, (250, 190, 130))])
    img = soleil(img, L * 0.3, H * 0.5, 54, (255, 236, 196), halo=6)
    xx = np.arange(L, dtype=float)
    yy = np.arange(H)[:, None]
    for i, (hm, col_lum, col_omb) in enumerate([(0.56, (230, 150, 96), (180, 100, 70)), (0.66, (214, 128, 78), (150, 78, 52)), (0.78, (196, 108, 62), (120, 58, 38)), (0.90, (170, 88, 48), (92, 42, 28))]):
        prof = (hm - 0.06 * np.sin(xx / L * (2.2 + i) * math.pi + i * 1.3) - 0.03 * bruit_1d(L, 3, graine=60 + i)) * H
        pente = np.gradient(prof)
        cote = (pente < 0).astype(float)[None, :]
        m = yy >= prof[None, :]
        prof_rel = np.clip((yy - prof[None, :]) / (0.18 * H), 0, 1)
        lum = np.asarray(col_lum, float)
        omb = np.asarray(col_omb, float)
        c = lum * cote[..., None] + omb * (1 - cote[..., None])
        c = c * (1 - 0.25 * prof_rel[..., None])
        img[m] = np.broadcast_to(c, img.shape)[m]
    return vignette(grain(img, 3.0, 5))


def ocean():
    img = degrade_vertical([(0, (40, 90, 160)), (0.45, (150, 190, 220)), (0.56, (250, 214, 170)), (0.58, (40, 80, 120)), (1, (10, 30, 60))])
    img = soleil(img, L * 0.5, H * 0.53, 40, (255, 244, 214), halo=6)
    yy, xx = np.mgrid[0:H, 0:L].astype(float)
    hz = 0.575 * H
    mer = yy > hz
    rng = np.random.default_rng(70)
    ondes = np.sin(xx / (6 + (yy - hz).clip(1) * 0.08) + rng.normal(0, 0.2, (H, L)) + yy * 0.9)
    largeur = 30 + (yy - hz).clip(0) * 0.9
    chemin = np.exp(-((xx - L * 0.5) / largeur) ** 2) * (ondes > 0.6)
    img[mer] += (np.array([255, 230, 190]) * chemin[..., None] * 0.8)[mer]
    img[mer] += (np.array([20, 40, 60]) * (ondes[..., None] * 0.15))[mer]
    return vignette(grain(img, 2.0, 6))


def collines():
    img = degrade_vertical([(0, (90, 150, 220)), (0.5, (190, 220, 240)), (1, (190, 220, 240))])
    pil = Image.fromarray(img.astype(np.uint8))
    d = ImageDraw.Draw(pil, "RGBA")
    rng = np.random.default_rng(80)
    for _ in range(9):
        cx, cy = rng.uniform(0, L), rng.uniform(H * 0.08, H * 0.4)
        for _ in range(14):
            r = rng.uniform(30, 90)
            ox, oy = rng.normal(0, 110), rng.normal(0, 22)
            d.ellipse([cx + ox - r, cy + oy - r * 0.6, cx + ox + r, cy + oy + r * 0.6], fill=(255, 255, 255, 46))
    img = np.asarray(pil.filter(ImageFilter.GaussianBlur(6))).astype(float)
    for i, (hm, col) in enumerate([(0.50, (120, 160, 120)), (0.58, (104, 152, 86)), (0.68, (88, 140, 62)), (0.80, (70, 120, 46)), (0.92, (50, 96, 34))]):
        img = peindre_couche(img, crete(hm, 0.07, 81 + i, octaves=3, base=2), col, brume=(200, 225, 235), intensite_brume=0.4 - i * 0.08)
    return vignette(grain(img, 2.5, 7), 0.25)


def nuit_etoilee():
    img = degrade_vertical([(0, (6, 8, 20)), (0.6, (16, 22, 46)), (1, (30, 34, 60))])
    yy, xx = np.mgrid[0:H, 0:L].astype(float)
    # voie lactée : bande diagonale diffuse et nuageuse
    d = (yy - (H * 0.95 - xx * 0.42)) / (H * 0.16)
    nuages = Image.fromarray((np.random.default_rng(89).random((H // 24, L // 24)) * 255).astype(np.uint8)).resize((L, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(18))
    nuages = np.asarray(nuages).astype(float) / 255.0
    bande = np.exp(-d ** 2) * (0.35 + 0.65 * nuages)
    img += np.array([110, 100, 140]) * bande[..., None] * 0.6
    img = etoiles(img, 2600, 90, 0.85)
    img = peindre_couche(img, crete(0.70, 0.15, 91, aigu=True), (12, 14, 26))
    img = peindre_couche(img, crete(0.84, 0.06, 92), (6, 8, 14))
    return grain(img, 1.8, 8)


SCENES = [
    ("01_aube_montagnes.jpg", aube_montagnes),
    ("02_lac_crepuscule.jpg", lac_crepuscule),
    ("03_foret_brume.jpg", foret_brume),
    ("04_aurore_boreale.jpg", aurore),
    ("05_dunes.jpg", dunes),
    ("06_ocean_calme.jpg", ocean),
    ("07_collines.jpg", collines),
    ("08_nuit_etoilee.jpg", nuit_etoilee),
]


def police(taille):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, taille)
    return ImageFont.load_default()


def icone_et_banniere(dossier_res, fond_source):
    os.makedirs(dossier_res, exist_ok=True)
    fond = Image.open(fond_source).convert("RGB")
    # Bannière TV 320x180
    b = fond.resize((320, 180), Image.LANCZOS)
    d = ImageDraw.Draw(b, "RGBA")
    d.rectangle([0, 110, 320, 180], fill=(0, 0, 0, 90))
    f = police(30)
    t = "Accueil Zen"
    w = d.textlength(t, font=f)
    d.text(((320 - w) / 2, 124), t, font=f, fill=(255, 255, 255, 255))
    b.save(os.path.join(dossier_res, "banniere.png"), optimize=True)
    # Icône 192x192 arrondie
    taille = 192
    ic = fond.crop((fond.width // 2 - fond.height // 2, 0, fond.width // 2 + fond.height // 2, fond.height)).resize((taille, taille), Image.LANCZOS)
    masque = Image.new("L", (taille, taille), 0)
    ImageDraw.Draw(masque).rounded_rectangle([0, 0, taille - 1, taille - 1], 42, fill=255)
    sortie = Image.new("RGBA", (taille, taille), (0, 0, 0, 0))
    sortie.paste(ic, (0, 0), masque)
    ImageDraw.Draw(sortie).text((taille / 2, taille / 2), "Z", font=police(96), fill=(255, 255, 255, 235), anchor="mm")
    sortie.save(os.path.join(dossier_res, "icone.png"), optimize=True)


def main():
    dossier_fonds, dossier_res = sys.argv[1], sys.argv[2]
    os.makedirs(dossier_fonds, exist_ok=True)
    for nom, f in SCENES:
        chemin = os.path.join(dossier_fonds, nom)
        enregistrer(f(), chemin)
        print("fond :", chemin, os.path.getsize(chemin) // 1024, "Ko")
    icone_et_banniere(dossier_res, os.path.join(dossier_fonds, SCENES[0][0]))
    print("icône et bannière :", dossier_res)


if __name__ == "__main__":
    main()

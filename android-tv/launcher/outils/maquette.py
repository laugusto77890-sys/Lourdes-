#!/usr/bin/env python3
"""Maquette de conception d'Accueil Zen (image d'illustration, PAS une capture de télé)."""
import math
import sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1920, 1080  # télé 1080p ≈ 960 x 540 dp → 1 dp = 2 px
F = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FL = "/usr/share/fonts/truetype/dejavu/DejaVuSans-ExtraLight.ttf"
import os
if not os.path.exists(FL):
    FL = F
fond, sortie = sys.argv[1], sys.argv[2]
img = Image.open(fond).convert("RGB").resize((W, H)).convert("RGBA")
ov = Image.new("RGBA", (W, H))
d = ImageDraw.Draw(ov)
for y in range(H):
    a = 0x55 * (1 - y / (H / 3)) if y < H / 3 else (0 if y < 2 * H / 3 else 0xAA * (y - 2 * H / 3) / (H / 3))
    d.line([(0, y), (W, y)], fill=(0, 0, 0, int(max(a, 0))))
img = Image.alpha_composite(img, ov)


def txt(im, x, y, s, size, font=F, fill=(255, 255, 255, 255), anchor="la"):
    ImageDraw.Draw(im).text((x, y), s, font=ImageFont.truetype(font, size), fill=fill, anchor=anchor)


txt(img, W - 112, 72, "20:41", 128, FL, anchor="ra")
txt(img, W - 112, 230, "Samedi 31 octobre", 40, anchor="ra", fill=(255, 255, 255, 220))
tw, th, gap = 272, 153, 40  # tuile 136 x 76 dp, marges 10 dp
noms = [("Netflix", (150, 20, 24)), ("YouTube", (200, 30, 30)), ("Prime Video", (20, 60, 110)),
        ("france.tv", (30, 40, 120)), ("Applis", None), ("Réglages", None)]
total = len(noms) * tw + (len(noms) - 1) * gap
x0 = (W - total) // 2
y0 = H - 56 - 60 - th - 40
for i, (n, c) in enumerate(noms):
    x = x0 + i * (tw + gap)
    foc = i == 0
    s = 1.14 if foc else 1.0
    w2, h2 = int(tw * s), int(th * s)
    xx, yy = x - (w2 - tw) // 2, y0 - (h2 - th) // 2
    tile = Image.new("RGBA", (w2, h2), (0, 0, 0, 0))
    td = ImageDraw.Draw(tile)
    td.rounded_rectangle([0, 0, w2 - 1, h2 - 1], int(20 * s), fill=(c + (255,)) if c else (255, 255, 255, 64))
    if c:
        td.text((w2 / 2, h2 / 2), n, font=ImageFont.truetype(F, int(32 * s)), fill="white", anchor="mm")
    else:
        cx, cy = w2 / 2, h2 / 2 - 14
        if n == "Applis":
            for a in range(3):
                for b in range(3):
                    td.rounded_rectangle([cx - 36 + a * 26, cy - 36 + b * 26, cx - 16 + a * 26, cy - 16 + b * 26], 5, fill="white")
        else:
            pts = []
            for k in range(16):
                r = 36 if k % 2 == 0 else 27
                for kk in (k, k + 1):
                    ang = math.pi * 2 * kk / 16
                    pts.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r))
            td.polygon(pts, fill="white")
            td.ellipse([cx - 11, cy - 11, cx + 11, cy + 11], fill=(150, 110, 150, 255))
        td.text((w2 / 2, h2 - 22), n, font=ImageFont.truetype(F, 20), fill="white", anchor="mm")
    if foc:
        sh = Image.new("RGBA", (W, H))
        ImageDraw.Draw(sh).rounded_rectangle([xx + 6, yy + 20, xx + w2 + 6, yy + h2 + 20], 24, fill=(0, 0, 0, 140))
        img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(18)))
    img.alpha_composite(tile, (xx, yy))
txt(img, W // 2, y0 - 70, "Netflix", 36, anchor="mm")  # nom de l'appli sélectionnée, centré comme dans l'appli
txt(img, W // 2, H - 70, "▼ Toutes les applis   ·   appui long sur OK : options", 26, anchor="mm", fill=(255, 255, 255, 150))
band = Image.new("RGBA", (W, H))
ImageDraw.Draw(band).rectangle([0, 0, W, 56], fill=(0, 0, 0, 170))
img = Image.alpha_composite(img, band)
txt(img, 24, 12, "MAQUETTE de conception — ce n'est pas une capture de votre télé (applis à titre d'exemple)", 28, fill=(255, 210, 120, 255))
img.convert("RGB").save(sortie, quality=88)

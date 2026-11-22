#!/usr/bin/env python3
"""Step 2: one card folder the engine (engine/card.html) can show, from the layers in <work>/ (see layers.py).
  <cards>/<name>/  color.webp maps.png (R height, G cut-out, B aura field) blur.webp glow.webp plate.webp frame.webp card.json
                   + bg.mp4 / frame-anim.mp4 when made (animated card, see bgvideo.py / frameanim.py)
  <cards>/card.html   the engine (copied)
Shapes (how the character is built in depth):
  close-up  the picture fills the window (a face or bust): the depth map + a rounded profile, full depth
  relief    a full figure: a rounded body with its top layer on the chest, SHALLOW, standing in front of a deep background
  float     a full figure, almost flat, floating out of the window: keeps its exact shape at any tilt
  scene     a character standing in its world: the background is a low relief rising toward the character
  world     a place (landscape, temple, street, cavern): the WHOLE picture as one relief that follows its real depth (foreground at the
            glass, the far distance deepest), everything behind the card's surface, so the frame hides it like a real window
  auto      close-up if the character covers most of the picture, else relief
usage: python card.py <work> <cards-dir> <name> [--title "TEXT"] [--frame frame.png] [--shape auto] [--glyph compass|sun|code|none]
                      [--particles sparkle,prism,embers] [--theme theme.json] [--planes planes.json] [--depth .16]
  planes.json: extra picture layers, e.g. a whale that swims out of the card:
    [{"file": "whale.png", "x": 0, "y": 300, "z": .06, "ze": .4, "pop": true, "swim": .012, "label": ["Whale", "swims out of the card"]}]
    x, y = where its top-left sits on the picture (picture px); z > 0 = in front of the card; pop = may cover the frame; swim = gentle drift"""
import argparse, json, shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy.ndimage import binary_dilation, distance_transform_edt, gaussian_filter, label

SKILL = Path(__file__).resolve().parent.parent
NSTEPS = 28
# z ranges in card widths. A deep range on a full figure makes its depth steps slide over each other on a tilt (the body swells, arms
# slide across it); shallow keeps its shape and the 3D comes from the gap to the deep background. A close-up face can go deep.
SHAPES = {"close-up": dict(zr=[-.12, .14], zBg=-.36), "relief": dict(zr=[-.03, .08], zBg=-.36),
          "float": dict(zr=[.03, .07], zBg=-.42), "scene": dict(zr=[-.04, .07], zBg=-.14, zScene=-.12, nbg=5),
          "world": dict(zr=[-.165, -.005], zBg=-.19, D=.16)}
PARTICLES = {"snow", "embers", "shards", "prism", "sparkle", "cloud", "petals", "code"}


def hsv(c):
    c = c.astype(np.float32) / 255; r, g, b = c[..., 0], c[..., 1], c[..., 2]
    v = c.max(-1); mn = c.min(-1); d = v - mn; s = np.where(v > 0, d / (v + 1e-6), 0)
    h = np.where(v == r, (g - b) / (d + 1e-6), np.where(v == g, 2 + (b - r) / (d + 1e-6), 4 + (r - g) / (d + 1e-6)))
    return (h / 6) % 1, s, v


def hue_rgb(h, s=1., v=1.):
    k = (np.array([5, 3, 1]) + h * 6) % 6
    return [round(float(v - v * s * max(0, min(k_, 4 - k_, 1))), 3) for k_ in k]


def auto_theme(C, a):
    """aura, rim, rays and box colours from the character's own strongest hues; softer bloom for a bright picture"""
    h, s, v = hsv(C); fig = a > .5
    w = (s * v * fig).ravel(); hist = np.bincount((h.ravel() * 36).astype(int) % 36, w, 36)
    hist = gaussian_filter(np.r_[hist, hist, hist], 1.2)[36:72]
    h1 = hist.argmax(); hist2 = hist.copy()
    for d in range(-6, 7): hist2[(h1 + d) % 36] = 0   # the second accent: at least 60 degrees away
    h2 = hist2.argmax() if hist2.max() > hist.max() * .15 else (h1 + 18) % 36
    h1, h2 = (h1 + .5) / 36, (h2 + .5) / 36
    bright = float(v[fig].mean()) > .62 or float(((v > .85) & (s < .25))[fig].mean()) > .12   # lots of white (hair, snow, light) blooms out
    return dict(aura=[hue_rgb(h1, .88), hue_rgb(h2, .7)], rim=hue_rgb(h1, .45), rays=hue_rgb(h2, .5), bg=hue_rgb(h1, .7, .09),
                glow=.8 if bright else 1.2, bloom=[.16, .9] if bright else [.32, .78], auraAmt=.45 if bright else .8)


def glow_mask(C, a):
    """parts that light up: strongly coloured bright spots on the character, a touch of its near-white highlights"""
    h, s, v = hsv(C); fig = a > .5
    m = ((s > .55) & (v > .6) & fig) * 1. + ((v > .92) & (s < .12) & fig) * .1
    return gaussian_filter(np.clip(m, 0, 1).astype(np.float32), 1.2)


def heights(C, a, dep, shape):
    fig = a > .5; Hh, Ww = a.shape; yy, xx = np.mgrid[:Hh, :Ww].astype(np.float32)
    din = distance_transform_edt(fig)
    if shape == "close-up":   # the depth map leads; a rounded profile from the outline keeps the edges soft
        dome = 1 - (1 - np.clip(din / (.085 * max(Hh, Ww)), 0, 1)) ** 2.2
        return np.clip(.8 * dep + .2 * dome, 0, 1) * (a > .02)
    ys, xs = np.nonzero(fig); cx, cy = xs.mean(), ys.mean()   # top layer on the middle of the body: a tilt turns him, never leans him
    coef = np.linalg.lstsq(np.c_[xs, ys, np.ones(len(xs))].astype(np.float64), dep[fig].astype(np.float64), rcond=None)[0]
    det = dep - (coef[0] * xx + coef[1] * yy); lo, hi = np.percentile(det[fig], [2, 99.5]); det = np.clip((det - lo) / (hi - lo + 1e-6), 0, 1)
    dome = 1 - (1 - np.clip(din / (.2 * max(Hh, Ww)), 0, 1)) ** 2.2
    wgt = np.exp(-(((xx - cx) / (.5 * xs.std())) ** 2 + ((yy - cy) / (.7 * ys.std())) ** 2) / 2)
    return np.clip((.6 * dome + .4 * det) * (.1 + .9 * wgt), 0, 1) * (a > .02)


def key_frame(path):
    """frame art with a flat magenta window -> RGBA with the window cut out, and the window box"""
    F = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    d = np.sqrt(((F - [255, 0, 255]) ** 2).sum(-1))
    lab, n = label(d < 150); sizes = np.bincount(lab.ravel()); sizes[0] = 0
    if n == 0 or sizes.max() < F.shape[0] * F.shape[1] * .15: raise SystemExit(f"{path}: no big magenta window found (see prompts/frame.md)")
    win = lab == sizes.argmax(); ys, xs = np.nonzero(win); box = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
    al = np.clip((d - 70) / 80, 0, 1); al[~gaussian_filter(win.astype(np.float32), 3).astype(bool) & (al < 1)] = 1
    al = np.where(gaussian_filter(win.astype(np.float32), 4) > .02, al, 1.)
    lb, _ = label(d < 230)   # looser: the anti-aliased pinkish rim of that outer magenta too
    border = np.isin(lb, np.unique(np.r_[lb[0], lb[-1], lb[:, 0], lb[:, -1]])) & (lb > 0) & ~binary_dilation(win, iterations=8)
    if border.any():   # magenta left OUTSIDE the frame (generators paint the canvas corners): take the frame's nearest colour, keep it solid
        iy, ix = distance_transform_edt(border, return_indices=True)[1]; F[border] = F[iy[border], ix[border]]; al[border] = 1
    near = gaussian_filter(win.astype(np.float32), 6) > .02   # magenta spill on the window rim
    spill = np.clip((np.minimum(F[..., 0], F[..., 2]) - F[..., 1]) / 255, 0, 1) * near
    F[..., 0] -= spill * 120; F[..., 2] -= spill * 140
    return np.dstack([F.clip(0, 255), al * 255]).astype(np.uint8), box


def font(size):
    for f in ("/System/Library/Fonts/Supplemental/Copperplate.ttc", "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", "C:/Windows/Fonts/georgiab.ttf", "DejaVuSans-Bold.ttf"):
        try: return ImageFont.truetype(f, size)
        except OSError: pass
    return ImageFont.load_default()


def builtin_frame(T, title):
    """a plain metal frame in the character's colours, for a card without generated frame art (the engine adds foil and glitter)"""
    W, H = 1024, 1536; win = [62, 92, 962, 1168]; R = 26
    c1 = np.array(T["rim"]) * 255; c0 = np.array(T["bg"]) * 255 * 2.2
    yy = np.linspace(0, 1, H)[:, None, None]; xx = np.linspace(0, 1, W)[None, :, None]
    base = c0 + (c1 - c0) * (.15 + .25 * np.cos((xx * 1.7 + yy * 2.3) * np.pi) ** 2)
    im = Image.fromarray(np.broadcast_to(base, (H, W, 3)).clip(0, 255).astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(im); gold = tuple(int(v) for v in np.clip(c1 * 1.15 + 30, 0, 255)) + (255,)
    for i, w in ((14, 6), (30, 2)): d.rounded_rectangle([i, i, W - i, H - i], 40, outline=gold, width=w)
    d.rounded_rectangle([win[0] - 12, win[1] - 12, win[2] + 12, win[3] + 12], R + 10, outline=gold, width=5)
    for x, y in ((40, 40), (W - 40, 40), (40, H - 40), (W - 40, H - 40)): d.ellipse([x - 16, y - 16, x + 16, y + 16], fill=gold)
    py0, py1 = win[3] + 46, H - 70; d.rounded_rectangle([110, py0, W - 110, py1], 30, fill=tuple(int(v * .45) for v in c0) + (255,), outline=gold, width=4)
    f = font(92 if len(title) <= 10 else 64); tw = d.textlength(title, font=f)
    d.text(((W - tw) / 2, (py0 + py1) / 2), title, font=f, fill=gold, anchor="lm")
    hole = Image.new("L", (W, H), 255); ImageDraw.Draw(hole).rounded_rectangle(win, R, fill=0)
    im.putalpha(Image.fromarray(np.minimum(np.asarray(im.getchannel("A")), np.asarray(hole.filter(ImageFilter.GaussianBlur(.8))))))
    return np.asarray(im), win


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("work"); ap.add_argument("cards"); ap.add_argument("name")
    ap.add_argument("--title"); ap.add_argument("--frame"); ap.add_argument("--shape", default="auto", choices=["auto", *SHAPES])
    ap.add_argument("--glyph", default="compass", choices=["compass", "sun", "code", "none"]); ap.add_argument("--particles", default="sparkle,prism,embers")
    ap.add_argument("--theme", help="json with any of: aura, rim, rays, bg, glow, bloom, auraAmt, fy"); ap.add_argument("--labels", help="json: layer captions")
    ap.add_argument("--planes", help="json list of extra layers (see above)"); ap.add_argument("--depth", type=float, help="world: how deep the picture goes (card widths, default .16)")
    A = ap.parse_args(); W_ = Path(A.work); out = Path(A.cards) / A.name; out.mkdir(parents=True, exist_ok=True)
    C = np.asarray(Image.open(W_ / "color.png").convert("RGB")); Hh, Ww = C.shape[:2]
    a_raw = np.asarray(Image.open(W_ / "alpha.png").convert("L")).astype(np.float32) / 255
    a = np.clip((a_raw - .5) * 2.2 + .5, 0, 1); fig = a > .5
    dep = np.asarray(Image.open(W_ / "depth.png")).astype(np.float32); dep /= 65535 if dep.max() > 255 else 255
    lo, hi = np.percentile(dep[fig], [2, 99.5]); dep = np.clip((dep - lo) / (hi - lo + 1e-6), 0, 1)
    cover = fig.mean(); shape = A.shape if A.shape != "auto" else ("close-up" if cover > .55 else "relief")
    S = SHAPES[shape]; parts = [p for p in A.particles.split(",") if p in PARTICLES]
    T = auto_theme(C, a)
    if shape == "world": T["auraAmt"] = .1   # a place: the aura (made for characters) would outline the cut-out like a sticker
    T.update(json.loads(Path(A.theme).read_text()) if A.theme else {})
    T.update(name=A.title or A.name.upper(), glyph=A.glyph, particles=parts, style="box")
    P = np.asarray(Image.open(W_ / "plate.png").convert("RGB"))
    plate = np.where((a_raw > .5)[..., None], P, C)   # the filled plate only under him; elsewhere the picture itself
    h = heights(C, a, dep, "close-up" if shape == "close-up" else "relief")
    h = gaussian_filter(h.astype(np.float32), 2.5 * Ww / 1216) * (a > .02)   # smooth contours: no jagged step edges
    NB = S.get("nbg", 0); zs = None
    if shape == "world":   # the depth map over the whole picture; z follows depth linearly (zs per step), all behind the card's surface
        D = A.depth or S["D"]; Z1 = S["zr"][1]
        d = np.asarray(Image.open(W_ / "depth.png")).astype(np.float32); d /= 65535 if d.max() > 255 else 255
        lo, hi = np.percentile(d, [2, 99.5]); h = gaussian_filter(np.clip((d - lo) / (hi - lo + 1e-6), 0, 1), 4 * Ww / 1216)
        NB, nfig = 12, 24; hf = float(np.quantile(h[fig], .05)) if fig.any() else .5   # more steps where the subject is
        ts = [0.] + [hf * i / NB for i in range(1, NB)] + [hf + (1 - hf) * j / nfig for j in range(nfig)]
        zs = [Z1 - D * (1 - t) for t in ts]; S = dict(S, zr=[Z1 - D, Z1], zBg=Z1 - D - .03, zScene=Z1 - D)
    elif NB:   # scene: the background is the low steps of the same relief, rising gently toward him
        bgh = .2 * np.exp(-distance_transform_edt(~fig) / (.12 * Ww))
        h = gaussian_filter((a * (.25 + .75 * h) + (1 - a) * bgh).astype(np.float32), 1.5 * Ww / 1216)
        ts = [0.] + [float(np.quantile(h[~fig], i / NB)) for i in range(1, NB)] + [.23] + \
             [float(np.quantile(h[fig], .04 + .93 * j / (NSTEPS - NB - 2))) for j in range(NSTEPS - NB - 1)]
    else:
        ts = [0.] + [float(np.quantile(h[fig & (h > .02)], .04 + .93 * i / (NSTEPS - 1))) for i in range(1, NSTEPS)]
    boxes = []
    for t in ts:
        m = (h >= t - .01) & ((a > .02) | (NB > 0)) if t > 0 else (a > .02) | (NB > 0)
        ys, xs = np.nonzero(m); p = 6
        boxes.append([max(0, xs.min() - p) / Ww, max(0, ys.min() - p) / Hh, min(Ww, xs.max() + p) / Ww, min(Hh, ys.max() + p) / Hh])
    if NB:   # deep scene steps slide past the picture's edge on a tilt: run them on under the frame (the textures clamp)
        boxes = [[-.12 if b[0] <= 0 else b[0], -.12 if b[1] <= 0 else b[1], 1.12 if b[2] >= 1 else b[2], 1.12 if b[3] >= 1 else b[3]] for b in boxes]
    planes = []
    for q in (json.loads(Path(A.planes).read_text()) if A.planes else []):   # extra layers: copied in, sized from the file
        src = Path(A.planes).parent / q["file"]; im = Image.open(src); shutil.copy(src, out / Path(q["file"]).name)
        planes.append(dict(q, file=Path(q["file"]).name, w=im.width, h=im.height))
    aura = np.clip(1 - distance_transform_edt(~fig) / (.07 * Ww), 0, 1) ** 1.6
    Image.fromarray((np.dstack([h, a, aura]) * 255).clip(0, 255).astype(np.uint8)).save(out / "maps.png")
    Image.fromarray(C).save(out / "color.webp", quality=95)
    Image.fromarray(plate.astype(np.uint8)).save(out / "plate.webp", quality=92)
    s = 6 * Ww / 1216; wa = gaussian_filter(a, s) + 1e-4   # alpha-weighted blur: fills the inside of a pulled-apart step
    Image.fromarray(np.dstack([gaussian_filter(C[..., i].astype(np.float32) * a, s) / wa for i in range(3)]).clip(0, 255).astype(np.uint8)).save(out / "blur.webp", quality=90)
    g = glow_mask(C, a); Image.fromarray((C.astype(np.float32) * g[..., None]).clip(0, 255).astype(np.uint8)).save(out / "glow.webp", quality=92)
    FR, win = key_frame(A.frame) if A.frame else builtin_frame(T, T["name"])
    Image.fromarray(FR).save(out / "frame.webp", quality=95)
    CH, CW = FR.shape[:2]; wW, wH = win[2] - win[0], win[3] - win[1]
    IS = max(wW * 1.08 / Ww, wH * 1.08 / Hh); fy = T.pop("fy", .42 if shape != "close-up" else .6)
    card = dict(k=A.name, W=Ww, H=Hh, CW=CW, CH=CH, win=win, IS=IS, IX0=(win[0] + win[2]) / 2 - Ww * IS / 2, IY0=win[1] - (Hh * IS - wH) * fy,
                frame="frame.webp", thresholds=ts, boxes=boxes, planes=planes, shape=shape, zs=zs, zr=S["zr"], zBg=S["zBg"], zScene=S.get("zScene", -.12),
                scene=NB > 0, nbg=NB, bgVideo="bg.mp4" if (out / "bg.mp4").exists() else None,
                frameAnim="frame-anim.mp4" if (out / "frame-anim.mp4").exists() else None, theme=T,
                labels=json.loads(Path(A.labels).read_text()) if A.labels else {})
    old = json.loads((out / "card.json").read_text()) if (out / "card.json").exists() else {}
    card.update({k: old[k] for k in ("bgFull", "bgAligned") if k in old and card["bgVideo"]})   # a rebuild keeps bgvideo.py's settings
    (out / "card.json").write_text(json.dumps(card, indent=1))
    shutil.copy(SKILL / "engine" / "card.html", Path(A.cards) / "card.html")
    print(f"{A.name}: {Ww}x{Hh}, character covers {cover * 100:.0f}% -> shape {shape}, frame {'art' if A.frame else 'built-in'}, "
          f"aura {T['aura']}, glow px {int((g > .3).sum())}\n  open: python {SKILL}/scripts/serve.py {A.cards}  ->  http://localhost:8790/card.html#{A.name}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Step 1: the four layers a card is built from, in <work>/:
  color.png  the picture (longest side brought to at least --min px)
  alpha.png  the character's cut-out mask (white = character)
  plate.png  the picture with the character removed and the hole filled
  depth.png  16-bit depth, white = near
A layer that already exists is kept: drop in the ones you made with Qwen Image Edit (or any editor) first, and only the
missing ones are made here, with free local models (downloaded once to ~/.cache/holo-card):
  cut-out  BiRefNet (or ISNet-anime) through rembg        plate  LaMa (ONNX), else OpenCV inpaint
  depth    Depth Anything V2 Small (ONNX)
usage: python layers.py <image> <work-dir> [--matte birefnet-general|isnet-anime|u2net] [--alpha-from-white cutout.png]
                        [--alpha-from-png qwen_cutout.png] [--min 1600]
  --alpha-from-png: a cut-out with transparency (Qwen Image Edit "... and output a PNG image"): its OUTLINE is kept and the inside made
  solid (Qwen leaves dark parts see-through); only small enclosed holes are filled, so gaps between hair curls stay open."""
import argparse, sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation, gaussian_filter

CACHE = Path.home() / ".cache" / "holo-card"
MEAN, STD = np.array([.485, .456, .406], np.float32), np.array([.229, .224, .225], np.float32)


def hf(repo, file):
    from huggingface_hub import hf_hub_download
    return hf_hub_download(repo, file, cache_dir=CACHE)


def ort_session(path):
    import onnxruntime as ort
    prov = [p for p in ("CoreMLExecutionProvider", "CUDAExecutionProvider") if p in ort.get_available_providers()] + ["CPUExecutionProvider"]
    try: return ort.InferenceSession(path, providers=prov)
    except Exception: return ort.InferenceSession(path, providers=["CPUExecutionProvider"])


def make_alpha(color, matte):
    from rembg import new_session, remove
    m = remove(Image.fromarray(color), session=new_session(matte), only_mask=True, post_process_mask=False)
    return np.asarray(m.convert("L").resize(color.shape[1::-1], Image.LANCZOS))


def alpha_from_white(path, size):
    """an editor's cut-out on flat white -> mask (anything not near-white, filled, softly edged)"""
    im = np.asarray(Image.open(path).convert("RGBA").resize(size, Image.LANCZOS)).astype(np.float32)
    if im[..., 3].min() < 250: return im[..., 3].astype(np.uint8)   # it already has transparency
    d = np.sqrt(((im[..., :3] - 255) ** 2).sum(-1))
    a = np.clip((d - 18) / 30, 0, 1)
    from scipy.ndimage import binary_fill_holes, label
    lab, n = label(a > .5); keep = np.bincount(lab.ravel()); keep[0] = 0
    big = np.isin(lab, np.nonzero(keep > keep.max() * .02)[0])   # drop specks
    a = np.where(binary_fill_holes(big), np.maximum(a, binary_fill_holes(big) * 1.), 0)
    return (gaussian_filter(a, .7) * 255).astype(np.uint8)


def fill_small_holes(a, frac=.004):
    """little see-through holes inside the character (between hair strands, in a sleeve) show the plate and read as damage: close them.
    Real gaps (between an arm and the body) are much bigger and stay open."""
    from scipy.ndimage import label
    holes = a < 128; lab, n = label(holes); sz = np.bincount(lab.ravel())
    edge = np.unique(np.r_[lab[0], lab[-1], lab[:, 0], lab[:, -1]])   # the background touches the border: never fill it
    small = np.isin(lab, [i for i in range(1, n + 1) if sz[i] < frac * a.size and i not in edge])
    return np.where(small, 255, a).astype(np.uint8)


def make_plate(color, alpha):
    hole = binary_dilation(alpha > 64, iterations=max(4, int(max(alpha.shape) * .012)))
    try:
        s = ort_session(hf("Carve/LaMa-ONNX", "lama_fp32.onnx")); N = 512
        x = np.asarray(Image.fromarray(color).resize((N, N), Image.LANCZOS)).astype(np.float32) / 255
        m = np.asarray(Image.fromarray((hole * 255).astype(np.uint8)).resize((N, N), Image.NEAREST)) > 127
        ins = s.get_inputs()
        out = s.run(None, {ins[0].name: x.transpose(2, 0, 1)[None], ins[1].name: m[None, None].astype(np.float32)})[0][0].transpose(1, 2, 0)
        out = out * 255 if out.max() <= 1.5 else out
        fill = np.asarray(Image.fromarray(out.clip(0, 255).astype(np.uint8)).resize(color.shape[1::-1], Image.LANCZOS))
        how = "LaMa"
    except Exception as e:   # no download possible: OpenCV's inpaint is rough but always there
        import cv2
        print("  LaMa unavailable (", str(e)[:80], ") - using OpenCV inpaint; a plate from Qwen Image Edit looks much better")
        small = cv2.resize(color, None, fx=.5, fy=.5, interpolation=cv2.INTER_AREA)
        hm = cv2.resize(hole.astype(np.uint8) * 255, small.shape[1::-1], interpolation=cv2.INTER_NEAREST)
        fill = cv2.resize(cv2.inpaint(small, hm, 9, cv2.INPAINT_TELEA), color.shape[1::-1], interpolation=cv2.INTER_CUBIC); how = "OpenCV"
    w = gaussian_filter(hole.astype(np.float32), 3)[..., None]
    return (fill * w + color * (1 - w)).clip(0, 255).astype(np.uint8), how


def make_depth(color):
    s = ort_session(hf("onnx-community/depth-anything-v2-small", "onnx/model.onnx")); name = s.get_inputs()[0].name
    H, W = color.shape[:2]; acc = np.zeros((H, W), np.float32)
    for side in (518, 770):   # two scales averaged: steadier edges
        k = side / max(H, W); h, w = max(14, round(H * k / 14) * 14), max(14, round(W * k / 14) * 14)
        x = (np.asarray(Image.fromarray(color).resize((w, h), Image.BICUBIC)).astype(np.float32) / 255 - MEAN) / STD
        d = s.run(None, {name: x.transpose(2, 0, 1)[None]})[0].squeeze()
        d = (d - d.min()) / (d.max() - d.min() + 1e-6)
        acc += np.asarray(Image.fromarray(d.astype(np.float32)).resize((W, H), Image.BICUBIC))
    acc /= 2
    return ((acc - acc.min()) / (acc.max() - acc.min() + 1e-6) * 65535).astype(np.uint16)


def alpha_from_png(path, size, t=.06, hole_max=.002):
    from scipy.ndimage import binary_closing, binary_erosion, binary_fill_holes, label
    a = np.asarray(Image.open(path).convert("RGBA").getchannel("A").resize(size, Image.LANCZOS)).astype(np.float32) / 255
    m = binary_closing(a > t, iterations=2)
    holes, n = label(binary_fill_holes(m) & ~m); small = np.bincount(holes.ravel()) < hole_max * a.size; small[0] = False
    m |= small[holes]
    solid = np.where(binary_erosion(m, iterations=3), 1., np.clip(a * 3, 0, 1) * m)
    assert .02 < solid.mean() < .98, f"{path}: the cut-out is empty or covers everything"
    return (solid * 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("image"); ap.add_argument("work")
    ap.add_argument("--matte", default="birefnet-general"); ap.add_argument("--alpha-from-white"); ap.add_argument("--alpha-from-png"); ap.add_argument("--min", type=int, default=1600)
    A = ap.parse_args(); out = Path(A.work); out.mkdir(parents=True, exist_ok=True)
    if not (out / "color.png").exists():
        im = Image.open(A.image).convert("RGB"); k = A.min / max(im.size)
        if k > 1:
            im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
            print(f"  picture enlarged x{k:.2f} (an AI upscaler such as Upscayl gives a sharper card)")
        im.save(out / "color.png")
    color = np.asarray(Image.open(out / "color.png").convert("RGB"))
    size = color.shape[1::-1]
    for f in ("alpha.png", "plate.png", "depth.png"):   # a layer made elsewhere must match the picture
        p = out / f
        if p.exists() and Image.open(p).size != size:
            Image.open(p).resize(size, Image.LANCZOS).save(p); print(f"  {f}: resized to the picture's {size[0]}x{size[1]}")
    if not (out / "alpha.png").exists():
        if A.alpha_from_png: a = alpha_from_png(A.alpha_from_png, size)
        else: a = fill_small_holes(alpha_from_white(A.alpha_from_white, size) if A.alpha_from_white else make_alpha(color, A.matte))
        Image.fromarray(a).save(out / "alpha.png")
        print(f"  alpha.png  ({'outline of the PNG cut-out, made solid' if A.alpha_from_png else 'from the white cut-out' if A.alpha_from_white else A.matte})")
    alpha = np.asarray(Image.open(out / "alpha.png").convert("L"))
    if (alpha > 127).mean() < .02: sys.exit("  the cut-out is almost empty: check alpha.png (try --matte isnet-anime for anime art)")
    if not (out / "plate.png").exists():
        plate, how = make_plate(color, alpha); Image.fromarray(plate).save(out / "plate.png"); print(f"  plate.png  ({how})")
    if not (out / "depth.png").exists():
        Image.fromarray(make_depth(color)).save(out / "depth.png"); print("  depth.png  (Depth Anything V2 Small)")
    print(f"layers ready in {out}: {size[0]}x{size[1]}, character covers {(alpha > 127).mean() * 100:.0f}% of the picture")


if __name__ == "__main__":
    main()

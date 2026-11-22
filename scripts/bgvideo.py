#!/usr/bin/env python3
"""Animated card, background: an image-to-video clip of plate.png -> <cards>/<name>/bg.mp4, a seamless loop (its last second
crossfades into its first). Small clips are upscaled: with an AI upscaler if given (--upscaler, e.g. Upscayl's
upscayl-bin or realesrgan-ncnn-vulkan), else Lanczos. card.json is updated to use it.
--ref <start image>: video generators return the clip cropped and zoomed a little (Grok: ~5-15 %). The first frame is matched to the
  start image (ORB features + RANSAC affine) and every frame is warped back onto it, so the clip lines up with the card's depth map.
  The start image may be a cleaned version of the card's picture (e.g. the scene with the subject removed): it is matched to the card's
  picture the same way.
--full: the whole picture, subject included, comes from the clip (use it when the subject stays still in the clip: a gate, a building).
usage: python bgvideo.py <clip.mp4> <cards-dir> <name> [--ref start.png] [--full] [--upscaler /path/to/upscayl-bin --models /path/to/models --model digital-art-4x]"""
import argparse, json, subprocess, tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def affine(src, dst):
    """2x3 affine taking src pixels onto dst pixels (both RGB arrays), from ORB matches + RANSAC; None if it cannot be trusted"""
    g = lambda a: cv2.cvtColor(a.astype(np.uint8), cv2.COLOR_RGB2GRAY)
    orb = cv2.ORB_create(6000); k1, d1 = orb.detectAndCompute(g(src), None); k2, d2 = orb.detectAndCompute(g(dst), None)
    if d1 is None or d2 is None: return None
    m = sorted(cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(d1, d2), key=lambda x: x.distance)[:1500]
    if len(m) < 30: return None
    M, inl = cv2.estimateAffine2D(np.float32([k1[x.queryIdx].pt for x in m]), np.float32([k2[x.trainIdx].pt for x in m]), ransacReprojThreshold=4, maxIters=5000)
    return M if M is not None and inl.sum() >= 25 else None


def frames_of(src, d):
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(src), str(d / "%04d.png")], check=True)
    return sorted(d.glob("*.png"))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("clip"); ap.add_argument("cards"); ap.add_argument("name")
    ap.add_argument("--upscaler"); ap.add_argument("--models"); ap.add_argument("--model", default="digital-art-4x"); ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--ref"); ap.add_argument("--full", action="store_true")
    A = ap.parse_args(); out = Path(A.cards) / A.name; C = json.loads((out / "card.json").read_text())
    target = max(C["W"], C["H"]) * C["IS"] * 1.1   # about the window's size in card pixels
    with tempfile.TemporaryDirectory() as td:
        a, b = Path(td, "a"), Path(td, "b"); a.mkdir(); b.mkdir()
        fs = frames_of(Path(A.clip).expanduser(), a)
        if A.upscaler and max(Image.open(fs[0]).size) < target:
            cmd = [A.upscaler, "-i", str(a), "-o", str(b), "-s", "4", "-n", A.model, "-f", "png"] + (["-m", A.models] if A.models else [])
            subprocess.run(cmd, check=True, capture_output=True); fs = sorted(b.glob("*.png"))
        w0, h0 = Image.open(fs[0]).size; k = min(1., target / max(w0, h0)) if max(w0, h0) > target else target / max(w0, h0)
        W2, H2 = int(w0 * k) // 2 * 2, int(h0 * k) // 2 * 2
        rd = lambda i: np.asarray(Image.open(fs[i]).convert("RGB").resize((W2, H2), Image.LANCZOS), np.float32)
        if A.ref:   # register: clip frame -> the card's picture geometry (W2 x H2 in the picture's aspect)
            pic = np.asarray(Image.open(out / "color.webp").convert("RGB")); H2 = int(W2 * pic.shape[0] / pic.shape[1]) // 2 * 2
            P = np.asarray(Image.fromarray(pic).resize((W2, H2), Image.LANCZOS)); R = np.asarray(Image.open(Path(A.ref).expanduser()).convert("RGB"))
            Rs = np.asarray(Image.fromarray(R).resize((W2, round(W2 * R.shape[0] / R.shape[1])), Image.LANCZOS))
            M1 = affine(Rs, P) if Path(A.ref).resolve() != (out / "color.webp").resolve() else None   # the start image onto the card picture
            f0 = np.asarray(Image.open(fs[0]).convert("RGB").resize((round(w0 * W2 / w0), round(h0 * W2 / w0)), Image.LANCZOS))
            M0 = affine(f0, Rs)   # the clip's first frame onto the start image
            if M0 is None: raise SystemExit("could not line the clip up with --ref (too few matching features); run without --ref")
            T = lambda M: np.vstack([M, [0, 0, 1]])
            Mt = (T(M1) @ T(M0) if M1 is not None else T(M0))[:2]
            sx = np.hypot(*Mt[:, 0]); print(f"clip -> picture: scale {sx:.3f}, shift {Mt[0, 2]:.0f},{Mt[1, 2]:.0f} px" + ("" if M1 is not None else " (start image = picture)"))
            src_w, src_h = round(w0 * W2 / w0), round(h0 * W2 / w0)
            rd = lambda i, Mt=Mt: cv2.warpAffine(np.asarray(Image.open(fs[i]).convert("RGB").resize((src_w, src_h), Image.LANCZOS)), Mt, (W2, H2),
                                                 flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT).astype(np.float32)
        N = len(fs); K = min(24, N // 3); M = N - K
        enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W2}x{H2}", "-r", str(A.fps), "-i", "-",
                                "-c:v", "libx264", "-crf", "17", "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out / "bg.mp4")],
                               stdin=subprocess.PIPE)
        for j in range(M):
            f = rd(j + K)
            if j >= M - K:   # crossfade the tail into the head: frame M-1 flows into frame 0
                w = (j - (M - K) + 1) / (K + 1); f = f * (1 - w) + rd(j - (M - K)) * w
            enc.stdin.write(f.clip(0, 255).astype(np.uint8).tobytes())
        enc.stdin.close(); enc.wait(); assert enc.returncode == 0, "ffmpeg failed"
    C["bgVideo"] = "bg.mp4"; C["bgFull"] = bool(A.full); C["bgAligned"] = bool(A.ref); (out / "card.json").write_text(json.dumps(C, indent=1))
    print(f"{out / 'bg.mp4'}: {W2}x{H2}, {M / A.fps:.2f} s loop")


if __name__ == "__main__":
    main()

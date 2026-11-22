#!/usr/bin/env python3
"""Animated card, frame light: an image-to-video clip of the frame art (made from the same frame.png, magenta window and all)
-> <cards>/<name>/frame-anim.mp4 holding ONLY its moving light, lined up with the crisp frame. The engine adds it on top.
How: the clip's magenta window is matched to the card's window (scale + offset, so a clip that came back zoomed still fits),
each pixel minus its darkest value over the clip = the light that moved; blurred a little (compression noise is fine detail,
real glints are broad), masked to the frame, half card size, seamless loop.
usage: python frameanim.py <clip.mp4> <cards-dir> <name>"""
import json, subprocess, sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, label

src, cards, name = Path(sys.argv[1]).expanduser(), Path(sys.argv[2]), sys.argv[3]
d = cards / name; C = json.loads((d / "card.json").read_text()); CW, CH = C["CW"], C["CH"]; wc = C["win"]
w, h = map(int, subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(src)],
                               capture_output=True, text=True).stdout.strip().split(",")[:2])
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(src), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
V = np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)
mag = np.sqrt(((V[0].astype(np.float32) - [255, 0, 255]) ** 2).sum(-1)) < 55   # strict: pink and violet frame parts must not count
lab, n = label(mag)
if n == 0: sys.exit("no magenta window in the clip's first frame: animate the frame art WITH its magenta window (prompts/animate.md)")
sz = np.bincount(lab.ravel()); sz[0] = 0; mag = lab == sz.argmax()
ys, xs = np.nonzero(mag); wv = [xs.min(), ys.min(), xs.max() + 1, ys.max() + 1]
sx, sy = (wc[2] - wc[0]) / (wv[2] - wv[0]), (wc[3] - wc[1]) / (wv[3] - wv[1])   # card px per clip px
OW, OH = CW // 2 // 2 * 2, CH // 2 // 2 * 2
aff = (2 / sx, 0, wv[0] - wc[0] / sx, 0, 2 / sy, wv[1] - wc[1] / sy)   # output px -> clip px
R = np.stack([np.asarray(Image.fromarray(f).transform((OW, OH), Image.AFFINE, aff, Image.BILINEAR)) for f in V]).astype(np.float32)
inside = np.asarray(Image.fromarray(np.full((h, w), 255, np.uint8)).transform((OW, OH), Image.AFFINE, aff, Image.BILINEAR)) / 255.
fa = np.asarray(Image.open(d / C["frame"]).getchannel("A").resize((OW, OH), Image.BILINEAR)) / 255.
R = gaussian_filter(R, (0, 1.6, 1.6, 0))
L = np.clip(R - R.min(0) - 14, 0, 255) * (fa * inside)[None, ..., None] * 1.6
N = len(L); K = min(24, N // 3); M = N - K
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OW}x{OH}", "-r", "24", "-i", "-",
                        "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(d / "frame-anim.mp4")], stdin=subprocess.PIPE)
for j in range(M):
    f = L[j + K]
    if j >= M - K: wgt = (j - (M - K) + 1) / (K + 1); f = f * (1 - wgt) + L[j - (M - K)] * wgt
    enc.stdin.write(f.clip(0, 255).astype(np.uint8).tobytes())
enc.stdin.close(); enc.wait(); assert enc.returncode == 0, "ffmpeg failed"
C["frameAnim"] = "frame-anim.mp4"; (d / "card.json").write_text(json.dumps(C, indent=1))
print(f"{d / 'frame-anim.mp4'}: clip window {wv} -> card {wc}, scale {sx:.3f} x {sy:.3f}, mean light {L.mean():.2f}, {M / 24:.2f} s loop")

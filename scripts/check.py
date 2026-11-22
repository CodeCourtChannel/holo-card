#!/usr/bin/env python3
"""Check a card before showing it: one sheet with the card tilted left, straight on, and tilted right (20 degrees), plus the
character alone (no effects) at the same three angles, so its shape can be compared directly.
Look at the sheet and compare the left and right views of the character:
  - it must be the SAME figure, only turned. If an arm, a hand or the head slides over the body, or the body swells on one side,
    the depth is fighting the picture: rebuild with card.py --shape relief (shallow) or --shape float (almost flat, safest).
  - a close-up face that fills the window may move a lot inside (that reads as real 3D); a full figure must not.
  - nothing is cut off by the window top (lower "fy" in the theme), the effects do not wash it out (lower bloom / glow).
usage: python check.py <cards-dir> <name>      -> <cards-dir>/<name>/check/sheet.jpg"""
import os, subprocess, sys
from pathlib import Path

from PIL import Image

SK = Path(__file__).resolve().parent
cards, name = Path(sys.argv[1]), sys.argv[2]; out = cards / name / "check"; out.mkdir(parents=True, exist_ok=True)
ALONE = "pure&hide=bg,glyph,rays,aura,parts,planes,frame,walls,edge"


def still(f, q, t=7):
    r = subprocess.run(["node", str(SK / "record.cjs"), str(cards), name, str(out / f), "600", "800"], capture_output=True, text=True,
                       env={**os.environ, "STILL": str(t), "Q": q})
    if r.returncode or "PAGEERROR" in r.stdout or not (out / f).exists(): sys.exit(f"render failed ({f}):\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    return Image.open(out / f).convert("RGB")


rows = [[still(f"{n}.png", q) for n, q in (("left", "pose=0,-20"), ("front", "front"), ("right", "pose=0,20"))],
        [still(f"{n}-alone.png", f"{q}&{ALONE}") for n, q in (("left", "pose=0,-20"), ("front", "front"), ("right", "pose=0,20"))]]
W, H = rows[0][0].size; sheet = Image.new("RGB", (W * 3, H * 2))
for j, row in enumerate(rows):
    for i, im in enumerate(row): sheet.paste(im, (i * W, j * H))
sheet.save(out / "sheet.jpg", quality=88)
print(f"{name}: look at {out / 'sheet.jpg'} (top: the card left / front / right; bottom: the character alone at the same angles)")

# Layer prompts (cut-out, clean background, depth)

A card needs four pictures of the same size, made from the source image:

| File | What it is | Free local ways to make it |
|---|---|---|
| `color.png` | the source picture (upscaled if small) | the image itself; Upscayl or Real-ESRGAN for 2x |
| `alpha.png` | the character's cut-out mask, white = character | Qwen Image Edit (prompt below); `scripts/layers.py` (BiRefNet through rembg) |
| `plate.png` | the picture with the character removed and the hole filled | Qwen Image Edit (prompt below); `scripts/layers.py` (LaMa) |
| `depth.png` | grey depth map, white = near | Qwen Image Edit (prompt below); `scripts/layers.py` (Depth Anything V2 Small) |

When a layer comes from an image editor, keep its framing identical to `color.png`. Editors often change the size a little
(Qwen Image Edit works at about 2 megapixels): `layers.py` resizes a dropped-in layer back to the picture.

## Qwen Image Edit (tested with Qwen Image 2.1 Edit on a 6 GB GPU, about 100 s per layer)

**Cut-out** (Qwen writes real transparency when the prompt ends with "output a PNG image"):
```
Remove the background, and output a PNG image. The character, its hair and everything it holds are solid and fully opaque, not see-through.
```
Qwen's PNG cut-outs keep the OUTLINE well but often leave dark parts see-through (dark skin, a dark coat). Use only the outline:
`scripts/layers.py <image> <work> --alpha-from-png qwen_cutout.png` makes the inside solid and keeps the real gaps (between hair
curls, under an arm) open. A cut-out on a flat white background works too: `--alpha-from-white cutout.png`.

**Clean background (plate)**: name what to remove and what fills the space. Try 2 seeds, because one seed may leave the character in.
```
Remove the <character / whale / gate> completely and fill the space where it was with <what is behind it: the same night sky / blue water with sunbeams>, so the background is complete and empty. Same style, same colours and light.
```

**Depth map.** Asked plainly, Qwen shades by BRIGHTNESS (white hair comes out "near", a darker face "far"), and on a tilt the hair
slides over the face. Tell it to ignore brightness and spell out the real order, from nearest to farthest:
```
Create a depth map of this picture as a smooth grayscale image. Ignore how bright or dark things are. The middle of his face is pure white and closest, and his head rounds away from it like a ball. His arm and fist are mid grey, darker than his face. His hair tips, his shoulders and the clouds are dark grey, and the empty background is black. Keep it soft and blurry with smooth gradients: no textures, no hair strands, no line art, no fine detail.
```
Rewrite the middle for your picture (what is nearest, what rounds away, what is set back). Make 3 seeds and keep the one closest
to the free depth model's map. "Estimate the depth" or "Depth map." alone only redraw the picture.

## Checks

- Overlay `alpha.png` on the picture at 2x zoom: hair and fingers are inside, and the background is outside.
- `plate.png` has no ghost of the character. A faint ghost is fine only where the character will cover it.
- `depth.png`: what is nearest in reality is brightest. For a person filmed from low down, the shoes are nearest and the head furthest.
  Build the card and look at `check.py`'s sheet: on a tilt the character must stay the same figure.

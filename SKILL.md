---
name: holo-card
description: Turn any picture with a main subject (an anime or cartoon character, a 3D character render, a photo of a person or pet, an object, or a landscape) into a stunning 3D holographic trading card that tilts with the mouse, glows, has an aura, magic glyph, particles and foil frame, and pulls apart into its layers on click; as one local web page, plus an MP4 of it. Two kinds: a STATIC 3D card (needs only this skill plus any free image generator or local Qwen Image for the frame and, optionally, the layers) and an ANIMATED card (also needs an image-to-video generator to bring the background and the frame light to life). Use when someone asks for a "holo card", "3D card", "trading card", "collectible card", "Pokemon-style card of my character", "turn this image into a card", or wants a picture to "pop out in 3D".
---

# Holo Card

One picture in, one premium card out: the character stands in a deep shadow-box behind a foil frame, the card follows the mouse, light rolls over the frame, and a click pulls it apart into its layers. Everything runs locally, and the free models are downloaded once.

`SKILL_DIR` is the folder this file lives in. Work in `./holo-cards/` of the folder you run from: `work/<name>/` for layers, `cards/` for the finished cards.

## First run

```bash
bash "$SKILL_DIR/scripts/setup.sh"            # Python env with the layer models (about 1-2 GB of downloads on first use)
bash "$SKILL_DIR/scripts/setup.sh" --record   # also Playwright + Chromium, to record videos and run check.py (needs Node 18+, ffmpeg)
PY="$SKILL_DIR/.venv/bin/python"
```

## Ask once, then work

Ask in ONE message (each with a default):
1. **Static or animated?** Animated needs an image-to-video tool the user can run (Grok Imagine, Kling, Runway, Pika, Luma, Hailuo, or local Wan/LTX). Default: static.
2. **Name on the card** and a short subtitle. Default: the file name in capitals.
3. **Frame art:** can they generate images (local Qwen Image, ChatGPT, Grok, Gemini, Flux, SDXL)? If yes, you write the prompt for them (or run it, if a generator CLI or API is available). If not, use the built-in frame. Default: you write the prompt.
4. **Layers from their own editor?** If they have Qwen Image Edit (or another instruction editor), they can make a better clean background and cut-out with the prompts in `prompts/layers.md`. Default: the local models.

## Pipeline

### 1. Look at the picture
Open it. Decide:
- **What the main subject is.** A close-up face or bust that fills most of the frame becomes a `close-up`. A full figure, a pet or an object becomes `relief`. A place (a landscape, a temple, a street, a cavern, even with a creature or a gate in it) becomes `world`: the whole picture follows its real depth.
- **Imagine the picture in reality:** what is nearest to the camera and what is furthest? (A low camera looking up at a person: shoes nearest, head furthest.) The depth map must say the same; check it in step 2.
- **Should something break out of the card?** A creature or object that is cut by the picture's edge (a whale, a dragon's head, a sword) can swim out over the frame as its own layer: see step 4, `--planes`.
- **The theme:** the subject's world, its two strongest accent colours, and which glyph fits: `compass` (martial, ice, fate), `sun` (joy, light, divine), `code` (tech, sci-fi), or `none`. Particles from: `snow embers shards prism sparkle cloud petals code`, three that belong to the subject.

### 2. Layers
```bash
$PY "$SKILL_DIR/scripts/layers.py" <image> holo-cards/work/<name>    # add --matte isnet-anime for anime / flat cartoon art
```
It writes `color.png alpha.png plate.png depth.png` and keeps any of them that already exist, so the user's Qwen layers can be dropped in first (prompts that work, and Qwen's traps, in `prompts/layers.md`). For a transparent PNG cut-out from Qwen use `--alpha-from-png cutout.png` (keeps its outline, makes the inside solid); for a "character on white" result, `--alpha-from-white cutout.png`.
Small pictures (under ~1500 px) look soft on the card: upscale them first (Upscayl `high-fidelity-4x`, then down to 1600 px wide).
**Check them by eye at 2x zoom:** hair and fingers inside the mask, no background outside it, no ghost of the subject in the plate. A wrong mask ruins the card. Fix it before going on: try the other `--matte`, or use the editor.

### 3. Frame
Write the frame prompt from `prompts/frame.md`: a theme paragraph for this subject, plus the fixed block that asks for a flat magenta window. Make 2-3 tries and keep the best. Zoom in to check the name-plate spelling and that the window is clean magenta. Without a generator, skip this step: `card.py` draws a built-in frame in the subject's colours.

### 4. Build the card
```bash
$PY "$SKILL_DIR/scripts/card.py" holo-cards/work/<name> holo-cards/cards <name> --title "NAME" \
    --frame frame.png --shape auto --glyph compass --particles snow,embers,shards
```
`--shape auto` picks `close-up` when the subject fills most of the picture and `relief` otherwise; use `--shape world --glyph none` for places (`--depth .16` = how deep the picture goes). Optional: `--theme theme.json` (aura, rim, rays, bg, glow, bloom, auraAmt, fy = how high the picture sits in the window, 0 = top) and `--labels labels.json` (bg, glyph and aura captions for the pulled-apart view).

**Breakout layer** (`--planes planes.json`): e.g. a whale that swims out of the card. Get the whole creature first (if the picture cuts it, widen the picture with an outpaint/expand tool, then cut the creature out with `layers.py`), remove it from the card's picture (the plate prompt), build the card on the empty scene, and add the creature as a plane in front with `"pop": true` (it may cover the frame), `"swim": .01` (a gentle drift), `"glitter": 0`, plus a blurred dark copy just behind it as its shadow on the frame. Make it a little bigger than in the picture so it clearly leaves the window.

The card is a closed box: its four sides show the scene reflected round the window's edge between bands of the frame's metal (`card.json` `boxDepth`, default .13), and everything behind the frame is hidden by the window as a real window would.

### 5. Check it (always)
```bash
$PY "$SKILL_DIR/scripts/check.py" holo-cards/cards <name>
```
Open `check/sheet.jpg`. The top row is the card tilted left, straight on and tilted right. The bottom row is the character alone at the same angles. Compare left and right:
- **The character must be the same figure, only turned.** If an arm, a hand or the head slides over the body, or the body swells on one side, the depth is fighting the picture. Rebuild with `--shape relief` (shallow), or `--shape float` (almost flat, the safest). This is the most common failure on full figures; a deep build makes it happen.
- **A close-up face that fills the window may move a lot inside.** That reads as real 3D.
- **Straight on, the card looks like the picture.** Nothing is cut by the window top: lower `fy` in the theme. Nothing washes out: lower `bloom` and `glow`.

### 6. Animated card (only if asked)
1. Background: image-to-video of `work/<name>/plate.png` with the background prompt in `prompts/animate.md`. Then:
   `$PY "$SKILL_DIR/scripts/bgvideo.py" clip.mp4 holo-cards/cards <name> --ref <the start image>`
   `--ref` lines the clip up with the picture (generators return it cropped and zoomed a little). For a `world` card whose subject stays still in the clip (a gate, a building), animate the whole picture instead of the plate and add `--full`: the subject then lives too (lanterns flicker). Never use a clip in which the subject MOVES (a swimming whale) behind a still cut-out: it shows as a ghost; animate the plate.
2. Frame light: image-to-video of the frame art WITH its magenta window, using the frame-light prompt. Then:
   `$PY "$SKILL_DIR/scripts/frameanim.py" clip.mp4 holo-cards/cards <name>`

Both scripts loop the clip seamlessly and update `card.json`. Check the clips first: the camera must be locked, and the frame text must not change.

### 7. Show it
```bash
$PY "$SKILL_DIR/scripts/serve.py" holo-cards/cards      # open http://localhost:8790/card.html#<name>
node "$SKILL_DIR/scripts/record.cjs" holo-cards/cards <name> holo-cards/<name>.mp4 1080 1350 30 0 16   # DPR=2 for extra sharpness
```
The recording plays a 16 s show: the card builds, tilts, pulls apart into its labelled layers, shows them, and closes again.

## Page controls
- **Mouse:** tilt. **Click:** pull the layers apart, or close them.
- **Debug options** (`card.html?c=<name>&...`):
  - `front`: no tilt.
  - `pure`: no effects.
  - `hide=bg,glyph,rays,aura,parts,planes,frame,walls,edge,steps`
  - `pose=rx,ry`: a held tilt.
  - `zr=a,b`: try another depth range.
  - `sides=thin`: the old thin gold edge instead of the closed box; `box=.2`: another box depth.
  - `nophys`: clip layers to the window in picture space (the old way; deep layers then slide outside the card on a tilt).

## What makes it look premium (keep these)
- **A shallow subject, a deep box.** The 3D comes from the gap between the subject and its background, never from stretching the subject.
- **Depth that matches reality.** Never a dome centred on the body: the near parts (shoes, a reaching hand, a coat flaring out) come forward, the rest goes back as it would in the real scene. Anything cut by the window stays behind the card's surface.
- **Frame art matters most.** Make several tries and pick the best one.
- **Colour comes from the picture.** The aura, rays and frame take the subject's own accents. Never use a generic purple glow.
- **Close-ups can go deep.** A face that fills the window hides the side walls, so the full depth reads as real 3D.
- **Effects stay subtle.** For a very bright picture (white hair, snow), card.py already lowers the bloom and aura. If the picture still washes out, lower `bloom` and `glow` in the theme.

## Credits (say them when you share a card)
- three.js (MIT) renders the card.
- BiRefNet (MIT) and ISNet via rembg make the cut-out.
- LaMa (Apache-2.0) fills the plate.
- Depth Anything V2 Small (Apache-2.0) makes the depth.

Pictures of characters someone else owns (anime, games, films) are for personal fan art only.

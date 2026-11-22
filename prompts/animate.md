# Animation prompts (animated card only)

An animated card adds two short videos, each made by image-to-video. Any video generator with image-to-video works: Grok Imagine, Kling, Runway, Pika, Luma, Hailuo, or local Wan 2.x / LTX-Video.

| Video | Start image | Becomes |
|---|---|---|
| background loop | `plate.png` (the picture without the character) | `bg.mp4`, the living world behind him (`scripts/bgvideo.py`) |
| frame light | the frame art with its magenta window (`frame.png`) | `frame-anim.mp4`, only its moving light is kept (`scripts/frameanim.py`) |

Both scripts make the clip loop seamlessly with a crossfade, so 5 to 8 seconds is enough.

## Background loop

```
Keep this exact picture and framing, locked-off static camera. Animate it gently: <3 to 5 motions from this scene: mist drifting, embers rising, water rippling, clouds moving slowly, light flickering, snow falling, petals drifting, stars twinkling>. No people, no new objects, no text, no camera move, no zoom.
```

Pick motions that already belong in the scene. Calm is better here: the character in front carries the energy.

## Frame light

```
Keep this exact trading-card frame, perfectly still, locked-off camera, same framing, and the magenta window stays flat magenta. Animate only the light: a slow shine sweeps across the metal, the gems glint and sparkle one by one, the top medallion glows and pulses softly. Nothing moves or changes shape. No zoom, no text changes.
```

## Checks

- The camera must not move. If the clip zooms or pans, generate it again. `frameanim.py` lines the frame up by its magenta window, so a small zoom is fixed automatically, but a moving camera is not.
- The frame text and shapes must not change during the clip. Only the light may move.
- Some generators return the clip zoomed in. That's fine for the background (it's cover-fitted), and the frame light is realigned.

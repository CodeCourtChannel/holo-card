# Frame art prompt

The card frame is a separate picture: an ornate frame whose art window is a flat magenta (#FF00FF) hole.
`prep_card.py` finds the magenta window, cuts it out and fits the character into it.
Any image generator works: local Qwen Image, ChatGPT/Codex, Grok, Gemini, Flux, SDXL.

Build the prompt from two parts. The first is the theme, written for this character. The second is the fixed block below, pasted unchanged.

## 1. Theme (write this for each character)

Describe the frame's materials and motifs from the character's world. Don't name the character for drawing, and say "do not draw any person". Put the name plate text in quotes, exactly as it must be spelled.

Examples that worked:

- Anime fighter, ice and crimson: "Theme: a demon martial artist with crimson markings (do not draw any person). Antique gold frame with frosted blue ice crystals growing along the sides, crimson lacquer bands, a twelve-point snowflake compass medallion at the top centre. The name plate is black lacquer with gold and reads exactly CRIMSON FIST."
- Cartoon sun god: "Theme: a joyful sun god (do not draw any person). A frame of bold black ink brush swirls and white flame-shaped cloud curls, gold sunburst corners, holographic rainbow foil trim. The name plate is white with gold and reads exactly SUN GOD."
- 3D tech character: "Theme: a tech founder (do not draw any person). Dark indigo and violet tech-ninja frame: black lacquer with glowing purple circuit lines, silver chains along the sides, glowing blue { } badges on the corners, a purple moon at the top centre. The name plate reads exactly NOVA, and under it, smaller, FOUNDER."
- Landscape or object: "Theme: a misty mountain lake at dawn (do not draw any person). Weathered bronze frame with carved pine branches, small inset moonstones, and a sunrise medallion at the top. The name plate reads exactly SILVER LAKE."

Colour rule: take the frame's main colours from the character picture (its brightest accent and its darkest tone). That way the frame and the art read as one card.

## 2. Fixed block (paste as is)

```
Portrait 2:3 image. Show ONLY an ornate premium collectible trading-card FRAME, perfectly flat and straight-on (no perspective, no hand, no table, no mockup). The card fills the canvas edge to edge. The big inner art window starts about 6% in from the left, right and top edges and ends at about 76% of the height; it is ONE perfectly flat solid magenta #FF00FF rounded rectangle with nothing inside it: no character, no texture, no gradient, no glow over it. Below the window sits the name plate. Extremely detailed, crisp, luxurious, cinematic studio lighting on the metal and gems, premium foil card for a fantasy card game. Spell every word exactly as written and add no other text, no logo of a company, no watermark, no signature.
```

## Check before using a frame

- The window is one clean magenta area. If the generator painted something inside it, try again.
- The name plate spelling is exact. Zoom in.
- The art is at least 1000 px wide. Upscale it first if not.
- Make 2 or 3 tries and keep the best. Frame quality decides how premium the card looks.

# mkcv Brand

This document records the visual identity of mkcv: the design philosophy behind the logo, README banner, and social preview, plus the palette and typefaces they use.

## Assets

All brand assets live in `docs/assets/`.

| File                 | Dimensions        | Use                                            |
|----------------------|-------------------|------------------------------------------------|
| `logo.svg`           | 512 × 512 viewBox | Source logo mark, transparent outside the tile |
| `logo.png`           | 512 × 512         | Raster logo for avatars and package indexes    |
| `banner.png`         | 1600 × 560        | README hero banner                             |
| `social-preview.png` | 1280 × 640        | GitHub social preview and Open Graph card      |

The logo PNG is rasterized directly from the SVG, so the two never drift:

```bash
rsvg-convert -w 512 -h 512 docs/assets/logo.svg -o docs/assets/logo.png
```

## Design Philosophy: Prompt & Proof

The identity treats the command line and the printed page as two ends of one sentence. A prompt is where intent begins. A proof is the printer's first impression pulled from set type and checked before release. Every mark in the identity sits on the path between the two: a typed command on one side, a document ready to be read on the other.

Composition comes from the typesetter's grid, not from illustration. Text is drawn as rules, never as letters, so the resume becomes pure structure: a heavy rule for the name, a hairline divider, small square bullets, and justified lines that end in a short final line. The wordmark baselines, the pipeline rows, and the page lines share one row grid, and the page margins are equal on all four sides. When two things look aligned, they are aligned by measurement.

Between the prompt and the page, five hairline gates stand for the five pipeline stages. Raw material enters at double density, faint and broken. At each gate some rows stop at a small terminal mark, and the survivors grow longer, brighter, and more regular. After the fifth gate, the remaining lines share baselines with the page's body text and match its line lengths: full measures where the page has full measures, short lines where a bullet ends. The diagram rewards a second look instead of explaining itself.

The palette is two materials and one signal: ink, paper, and vermilion, the color of the proofreader's pencil. Vermilion appears only as the cursor: after the wordmark, at the end of the last line on the page, and under the typed lines in the logo. The cursor is always a rule segment, the line that is still being written. Graphite and mist carry everything secondary, so the hierarchy holds on both GitHub's light and dark themes.

Two typographic voices meet. Geist Mono sets the wordmark exactly as you type it, with slightly tightened tracking at display sizes. Instrument Serif Italic sets the tagline the way a well-made book sets a subtitle. The prompt chevron hangs in the margin like hanging punctuation, so the wordmark and tagline share one clean left edge.

The work must look patiently made. Rules are snapped to whole pixels, alignments are measured rather than estimated, and the logo is drawn on a 16-unit grid so every straight edge lands on a whole pixel at 32px. Refinement means removing, not adding.

## Palette

The palette uses eight values. Vermilion is reserved for the cursor and appears nowhere else.

| Name      | Hex       | Role                                                      |
|-----------|-----------|-----------------------------------------------------------|
| Ink       | `#15181E` | Backgrounds, logo tile, name rule on the page             |
| Paper     | `#F2EEE6` | Page, wordmark, logo chevron and lines, resolved rows     |
| Vermilion | `#E4572E` | Cursor only                                               |
| Graphite  | `#7D838D` | Prompt chevron in the lockup, gate markers, raw rows      |
| Mist      | `#A9AEB6` | Tagline, mid-pipeline rows                                |
| Lead      | `#4A4F57` | Body text rules on the page                               |
| Pencil    | `#A8A296` | Secondary page rules (contact line, dates)                |
| Gate      | `#2C313A` | Pipeline gate hairlines                                   |

## Typography

Both typefaces are licensed under the SIL Open Font License 1.1. They are rasterized into the PNG assets; the repository does not redistribute the font files. The logo uses no type, only geometry.

| Typeface                | Use      | License                                                                                                              |
|-------------------------|----------|----------------------------------------------------------------------------------------------------------------------|
| Geist Mono Regular      | Wordmark | SIL OFL 1.1, Copyright 2024 The Geist Project Authors ([vercel/geist-font](https://github.com/vercel/geist-font))     |
| Instrument Serif Italic | Tagline  | SIL OFL 1.1, Copyright 2022 The Instrument Serif Project Authors ([Instrument/instrument-serif](https://github.com/Instrument/instrument-serif)) |

## Usage

Follow these rules when you place the brand in new contexts:

- Use the tagline as written: "AI-tailored, ATS-ready resumes from the command line."
- Set the chevron in Paper inside the logo mark and in Graphite in the wordmark lockup, where it precedes the name.
- Keep the logo at 16px or larger; it is drawn to stay legible at 32px.
- Keep vermilion for the cursor. Do not use it for emphasis, links, or status.

## Social Preview

GitHub does not read the social preview from the repository: upload `docs/assets/social-preview.png` manually under **Settings → General → Social preview**.

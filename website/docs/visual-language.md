# Etch visual language

Etch shows configuration becoming a reviewable plan. Its identity is the stack
of modules, a stylus making a deliberate mark, and a small spark. Product
graphics show grouped module changes and owned destinations. Forge shows
generation and source ownership; the company site introduces the workshop and
its projects. Share their typography, themes, and action hierarchy while keeping
Etch's plan and composition motif.

## Logo and spacing

The approved mark is maintained in `public/logo.svg`. The header, favicon,
manifest, and social card all use that asset. Preserve the layer and stylus
geometry. The rounded dark tile is intentional; its corners remain transparent.
Do not add an opaque rectangle behind the tile or crop the view box.

The artwork uses fixed Catppuccin Mocha colors so the same mark is recognizable
on all four website themes. Use mantle for the tile, text and rosewater for
the stylus, and the lavender, blue, sapphire, red, and maroon palette for the
layers and spark. The surrounding website follows its active theme.

Allow at least one quarter of the displayed logo width as clear space from
neighboring content. The header uses a 40-pixel mark and a 12-pixel gap before
the name. Check the mark at 16 and 32 pixels for favicons, 40 pixels for
navigation, and larger sizes for sharing.

## Plans and terminals

Use the shared DaisyUI terminal for website workflow illustrations and code.
Group output by module, indent each destination beneath its module, and label
illustrations as illustrative. A plan reports possible changes; the graphic
must not imply that an action has run. The home illustration combines Git and
Zsh modules and ends with “Nothing changed yet.”

Fira Sans handles headings and prose; Fira Code handles commands, paths, and
plan labels. Both are bundled locally. Keep the shared terminal colors and
theme surfaces described in the [website presentation contract](../README.md#website-presentation).

The header mark is decorative because the adjacent Etch text names its
link. Retain its empty alt text. The workflow figure is informative: retain its
accessible label, readable plan text, and caption. Standalone SVGs have a title
and description; social metadata provides descriptive image alt text.

## Social artwork

The 1200 × 630 card pairs the identity and tagline with the same two-module
plan. It uses the default dark theme palette and embeds Fira Sans 400/700,
Fira Code 400, and the canonical logo in a self-contained SVG. The PNG is the
published social image, so a sharing service does not need fonts or SVG support.
The static SVG is export artwork; its plan frame does not introduce a custom
website component.

After editing the logo, card generator, or bundled fonts, install the existing
Playwright Chromium browser and regenerate both checked-in card assets:

```sh
npx playwright install chromium
npm run assets:generate
```

Edit `scripts/generate-social-card.ts`, rather than the embedded data in the
generated SVG. Ordinary builds use the checked-in assets and require no browser.
Browser checks verify loaded fonts, current logo embedding, artwork bounds,
transparent icon corners, responsive layouts, accessibility treatment, and the
published PNG's size and theme surface. Review the rendered card as well.

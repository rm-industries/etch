# Themes and accessibility

Forge starts with four Catppuccin themes, bundled fonts, semantic layout
components, keyboard navigation, reduced-motion behavior, and automated
accessibility checks. Customization must preserve those user-facing guarantees.

## Choose a theme

The site follows the operating-system color preference: Latte is the default
light theme and Mocha is the dark theme. Theme definitions live in
`src/themes/`, and `src/components/theme/ThemeHead.astro` initializes them.

The available `data-theme` values are `latte`, `frappe`, `macchiato`, and
`mocha`. If a project adds a theme control, apply one of those values to the
document element, persist only a validated value, and retain an operating-system
fallback. Test the control with JavaScript disabled so content and navigation
remain usable.

## Change colors or add a theme

Keep theme values in `src/themes/` instead of scattering colors through Astro
components. Update `src/themes/site-theme.test.ts` whenever the registered theme
set or light/dark defaults change.

Prefer DaisyUI component classes in templates. Use Tailwind utilities only for
layout or behavior that DaisyUI does not provide, and keep ordinary CSS in
`src/styles/global.css` or `src/styles/print.css`. Do not add component-local CSS
for patterns that belong to a shared primitive.

After changing a theme, inspect text, links, controls, focus indicators, code,
cards, and article typography in both color schemes. Then run:

```sh
npm run lint:css
npm run test:e2e
npm run lighthouse:ci
```

## Replace fonts

Fira Sans and Fira Code are installed through Fontsource and imported by
`src/styles/global.css`; no remote font service is used. To replace them:

```sh
npm uninstall @fontsource/fira-sans @fontsource/fira-code
npm install @fontsource/inter @fontsource/source-code-pro
```

Replace the imports and the `--font-sans` and `--font-mono` values in
`src/styles/global.css`. Import only weights the site uses. For system fonts,
remove the Fontsource packages and imports and retain suitable generic fallback
families.

Run `npm run build` after changing fonts. Missing weights fail at build time;
unexpected transfer growth fails the Lighthouse budget.

## Preserve layout semantics

- Wrap pages in `src/layouts/BaseLayout.astro`.
- Keep one level-one heading that identifies each page.
- Do not add a second `main` landmark inside the layout.
- Use real links and buttons rather than clickable generic elements.
- Preserve the skip link, visible focus states, current-page indication, and
  named navigation.
- Use `navigation/Pagination.astro` only with real previous and next routes.
- Use the shared container and card primitives before creating a new variant.

## Review accessibility

Automation catches many regressions but cannot judge wording, reading order,
alternative-text quality, or every visual state. After changing content,
navigation, themes, components, or interaction:

1. run `npm run test:a11y`;
2. complete `docs/accessibility-checklist.md` with the actual date, browsers,
   screen sizes, input methods, and result;
3. test keyboard-only use at desktop and mobile widths;
4. inspect light, dark, reduced-motion, and print behavior; and
5. record unresolved failures as issues rather than checking an unverified item.

The CMS interface is supplied by Sveltia and is outside the template's public
site audit. Evaluate that interface with the people who will edit the site.

See the [accessibility review checklist](../accessibility-checklist.md) and
[performance budget](../performance-budget.md) for the enforced baseline.

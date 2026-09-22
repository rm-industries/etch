# Accessibility review checklist

This checklist records the manual accessibility review of the unmodified Forge
template. Generated-project maintainers must repeat it after changing content,
navigation, themes, components, or interactive behavior; replace the review
record below with their own date, environment, results, and linked issues.

## Baseline review

- **Date:** 2026-08-30
- **Environment:** Chromium via Playwright 1.62.1 against the production preview
- **Viewport coverage:** desktop and 320 × 640 mobile
- **Input:** keyboard and pointer
- **Result:** passed without a release-blocking accessibility issue

## Manual checks

- [x] Keyboard order starts with the skip link and then follows the visible
      page order without trapping focus.
- [x] Every interactive element displays a visible focus indicator in light
      and dark modes.
- [x] Activating **Skip to content** moves focus to the single main landmark.
- [x] Text, controls, focus indicators, and linked text remain distinguishable
      in the default Latte and Mocha themes.
- [x] Reduced-motion preference removes smooth scrolling and shortens CSS
      animations and transitions.
- [x] Representative pages contain one descriptive level-one heading and do
      not skip heading levels.
- [x] Public pages expose a banner, named primary navigation, one main landmark,
      and a content information landmark.
- [x] Desktop and mobile navigation remain operable using only the keyboard.
- [x] The custom 404 page identifies the error and provides a clear route home.

The content manager startup and no-index policy are tested separately. Its
editor interface is supplied by the pinned Sveltia dependency and is outside
this public-site audit; evaluate that third-party UI against the needs of the
project's editors before deployment.

## Automated companion checks

Run `npm run test:a11y` after each manual review. The suite applies axe-core's
WCAG 2.0, 2.1, and 2.2 A/AA rules to representative public routes in both
default color schemes. It also asserts landmarks, level-one headings, skip-link
behavior, responsive overflow, current-page navigation, and reduced motion.
Serious or critical axe violations block the browser-test job.

Automated checks do not replace judgment about reading order, wording, focus
order, contrast in newly introduced states, or whether alternative text conveys
the intended meaning. Record any failure as a linked release-blocking issue
rather than checking off an unverified item.

# Frontend Changes — Dark/Light Theme Toggle

## Summary

Added an icon-based dark/light theme toggle button to the Course Materials Assistant UI. The app previously shipped a dark theme only. The toggle is fixed to the top-right corner of the viewport, matches the existing design aesthetic, animates smoothly on switch, is fully keyboard-accessible, and persists the user's choice across reloads via `localStorage`.

## Files Changed

### `frontend/index.html`
- Added a `<button id="themeToggle" class="theme-toggle">` as the first child of `.container`. It contains two inline SVG icons — a sun (`.icon-sun`) and a moon (`.icon-moon`) — using `stroke="currentColor"` to match the existing send-button icon idiom. The button carries `aria-label="Toggle theme"` and a `title` for tooltip/screen-reader support.
- Bumped the cache-busting query string from `?v=9` to `?v=10` on both the `style.css` link and the `script.js` include, so the aggressive no-cache setup picks up the changes.

### `frontend/style.css`
- Added a `[data-theme="light"]` block immediately after `:root` that overrides the existing CSS color variables (`--background`, `--surface`, `--text-primary`, `--border-color`, etc.) with light values. Because the entire stylesheet already consumes colors via `var(--...)`, no per-rule edits were needed — flipping the attribute reskins the whole app. The blue `--primary-color` / `--user-message` are intentionally kept identical in both themes for brand consistency.
- Added `transition: background-color 0.3s ease, color 0.3s ease` to the `body` rule so the theme swap fades smoothly instead of snapping.
- Added `.theme-toggle` styles: fixed top-right positioning (`top: 1rem; right: 1rem; z-index: 100`), a 44px circular button (adequate touch target), using `var(--surface)` background, `var(--border-color)` border, and `var(--shadow)`. Reuses the app's established interaction idioms — hover lift (`transform: translateY(-1px)` + `--surface-hover`) like the send button, and the focus ring (`box-shadow: 0 0 0 3px var(--focus-ring)` with `outline: none`) used across inputs and buttons.
- Added an icon crossfade: the sun and moon SVGs are stacked absolutely and transition opacity + rotate/scale over `0.3s`. In dark mode the moon shows; under `[data-theme="light"]` the sun shows and the moon rotates/fades out — giving the toggle a smooth animated feel.

### `frontend/script.js`
- Added `themeToggle` to the module-level DOM element globals and assigned it in the `DOMContentLoaded` handler.
- Applied the saved theme as the **first** action inside `DOMContentLoaded` (before the async `createNewSession`/`loadCourseStats` calls) to prevent a flash of the wrong theme on load. It reads `localStorage.getItem('theme')`, defaults to `'dark'`, and sets `data-theme` on the `<html>` element.
- Wired `themeToggle.addEventListener('click', toggleTheme)` in `setupEventListeners()`.
- Added a `toggleTheme()` function that flips the current `data-theme` between `dark` and `light`, applies it to `<html>`, and persists the choice under the `localStorage` key `theme`.

## Accessibility

- Uses a native `<button>`, so it is automatically focusable, in the tab order, and activated by both Enter and Space — no custom key handling required.
- `aria-label="Toggle theme"` provides an accessible name for screen readers.
- A visible focus ring (matching the rest of the app) indicates keyboard focus.
- 44×44px hit target meets touch-accessibility guidance.

## Persistence

- Theme preference is stored under the `localStorage` key `theme` (values `"dark"` or `"light"`).
- On load the saved value is applied before any async work, so the selection survives reloads without a visible flash.

## Manual Verification

1. Run the app (`./run.sh`) and open `http://localhost:8000`.
2. Click the top-right button — the UI transitions smoothly between dark and light; the icon swaps between sun and moon.
3. Tab to the button — a focus ring appears; press Enter or Space — it toggles.
4. Reload the page — the chosen theme persists with no flash.

---

# Frontend Changes — Light Theme Refinement (Accessibility)

## Summary

Refined the light theme into a polished, WCAG AA–compliant variant. The initial light theme relied on the shared color variables but left several colors hardcoded outside the variable system, so they did not adapt to light mode and produced poor contrast. Those colors were promoted to CSS variables and given accessible light-mode values, and the light palette was tuned for contrast. The dark theme is visually unchanged.

## Files Changed

### `frontend/style.css`

**Promoted hardcoded colors to variables** (added to `:root` with their existing dark values, so dark mode is unchanged):
- `--link-color` — was `#93c5fd` hardcoded on `.source-link`.
- `--code-bg` — was `rgba(0, 0, 0, 0.2)` hardcoded on inline `code` and `pre` blocks.
- `--error-text` — was `#f87171` hardcoded on `.error-message`.
- `--success-text` — was `#4ade80` hardcoded on `.success-message`.

The four hardcoded literals in the rules (`.source-link` color, `.message-content code`/`pre` background, `.error-message`/`.success-message` color) now reference these variables.

**Refined the `[data-theme="light"]` block** for accessibility:
- `--primary-color` / `--primary-hover` deepened to `#1d4ed8` / `#1e40af` so white text on primary/user-message bubbles passes AA (~6.5:1).
- `--user-message` matched to the deeper primary; `--assistant-message` / `--surface-hover` set to `#eef2f7` for a soft neutral surface.
- `--text-primary` `#0f172a` (~16:1 on background) and `--text-secondary` `#475569` (~7:1) for high-contrast body text.
- `--focus-ring` / `--welcome-border` aligned to the deeper blue.
- Light-mode values for the newly promoted vars: `--link-color: #1d4ed8`, `--code-bg: rgba(0,0,0,0.05)` (subtle light-gray tint instead of a dark tint), `--error-text: #b91c1c`, `--success-text: #15803d` — all passing AA on their respective backgrounds.

### `frontend/index.html`
- Bumped the `style.css` cache-buster from `?v=10` to `?v=11`.

## Accessibility

- Body text ≈ 16:1, secondary text ≈ 7:1 (both exceed the 4.5:1 AA threshold).
- White text on the primary/user-message blue ≈ 6.5:1 (passes AA).
- Links, code, error, and success text use darkened light-mode values that pass AA on their backgrounds.

## Manual Verification

1. `./run.sh`, open `http://localhost:8000`, toggle to light theme.
2. Confirm: light background, dark readable text; source-link pills legible; code blocks show a light-gray (not dark) background; error/success message text is legible.
3. Toggle back to dark — confirm no visual regression.


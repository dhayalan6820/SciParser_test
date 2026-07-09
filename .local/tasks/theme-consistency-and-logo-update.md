# Fix theme consistency, update logo

## What & Why
Switching between light/dark theme only partially applies — several panels (chat schedule/execution panels, browser preview, glass effects) are hardcoded to dark colors and don't respond to the theme toggle. Separately, the app's logo/atom-icon assets need to be replaced with new brand artwork, with distinct versions for light and dark mode.

## Done looks like
- Toggling between light and dark theme updates every visible panel consistently — no leftover hardcoded-dark (or hardcoded-light) sections anywhere in the app shell, sidebar, chat page, schedule/execution panels, or browser preview.
- The atom icon and full Sciparser logo throughout the app (sidebar, mobile header, signup/login page, welcome/empty state) are replaced with the new artwork.
- The logo automatically swaps between a light-mode version and a dark-mode version depending on the active theme.

## Out of scope
- Redesigning layout or adding new theme options beyond light/dark.
- Changing branding copy/tagline text.

## Steps
1. **Audit and fix hardcoded theme colors** — Replace hardcoded hex/Tailwind dark colors in chat page panels (schedule/execution panels), the browser preview component, and glass-panel CSS with theme-aware CSS variables/classes so they follow the active theme.
2. **Replace logo/icon assets** — Swap in the new atom icon and full logo assets (light and dark variants) in place of the current `atom-icon.png` / `logo.png` assets used across the sidebar, mobile header, signup page, and empty-state screen.
3. **Theme-aware logo switching** — Render the light-mode logo when the theme is light and the dark-mode logo when the theme is dark, everywhere the logo/icon currently appears.
4. **Verify** — Manually toggle theme across all major pages/panels and confirm consistent appearance and correct logo per theme.

## Relevant files
- `Frontend/src/contexts/ThemeContext.tsx`
- `Frontend/src/App.tsx`
- `Frontend/src/index.css`
- `Frontend/src/components/ui/chat_page.tsx`
- `Frontend/src/components/ui/signup-1.tsx`
- `Frontend/src/components/ui/browser-preview.tsx`
- `Frontend/src/assets/atom-icon.png`
- `Frontend/src/assets/logo.png`
- `attached_assets/AI-Loader_1783019819349.png`
- `attached_assets/sciparser_logo_light_1783019860001.png`
- `attached_assets/sciparser_logo_dark_1783019865645.png`

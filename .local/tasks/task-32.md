---
title: Implement brand logo
---
# Implement Brand Logo

## What & Why
Replace the current placeholder icon/text branding with the official SciParser logo image (atom icon + "Sciparser" wordmark + tagline). The image is already in the project at `attached_assets/image_1782899313091.png`.

## Done looks like
- Sidebar header shows the logo image instead of the Sparkles icon + "SciParser AI" text
- Login/signup page shows the logo image instead of the Unsplash placeholder
- The collapsed icon-only sidebar rail (shown on the schedules page) shows the logo image instead of the Sparkles icon
- Logo looks crisp and correctly sized across dark backgrounds (the image has a dark/transparent-friendly background already)

## Out of scope
- Redesigning any layout or colors
- Favicon / browser tab icon changes
- Mobile splash screen

## Steps
1. **Copy image asset** — Copy `attached_assets/image_1782899313091.png` to `Frontend/src/assets/logo.png` so Vite can bundle it. Vite's `@` alias resolves to `Frontend/src/`, so import it as `import logo from "@/assets/logo.png"`.

2. **Update sidebar header** — In `chat_page.tsx`, replace the Sparkles icon + "SciParser AI" text block in the sidebar header with an `<img src={logo} />` using `h-8` height, `w-auto`, and `object-contain`. Remove the now-unused `Sparkles` icon div.

3. **Update collapsed icon-only rail** — Still in `chat_page.tsx`, the collapsed schedules-page rail also shows a Sparkles icon circle. Replace it with the logo image constrained to a small square (e.g. `h-8 w-8 object-contain`).

4. **Update login page** — In `signup-1.tsx`, change the default `logo.src` prop from the Unsplash URL to the imported logo asset. Adjust the `<img>` sizing class from `h-9 w-9 rounded-lg object-cover` to `h-9 w-auto rounded-none object-contain` so the rectangular logo renders correctly without cropping.

## Relevant files
- `Frontend/src/components/ui/chat_page.tsx:2337-2349`
- `Frontend/src/components/ui/chat_page.tsx:2260-2268`
- `Frontend/src/components/ui/signup-1.tsx:29-103`
- `attached_assets/image_1782899313091.png`
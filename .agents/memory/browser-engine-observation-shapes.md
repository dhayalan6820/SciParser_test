---
name: Browser-engine observation text shapes
description: The two browser-automation engines wired into this repo render interactive-element/DOM text in completely different, non-obvious formats — any regex-based detector over "observation text" must be verified against both, not assumed from one sample.
---

# Browser-engine observation text shapes

This repo can drive either Firefox (via camoufox) or Chrome (via the `browser_use` library's CDP session), selected by `config.BROWSER_ENGINE` (default: `"camoufox"`). Both feed an LLM/tool-loop a text "observation" of the page, but the shape of that text is entirely different between them:

- **camoufox (Firefox, default engine)** — `_CAMOUFOX_DOM_JS` in `Backend/src/agents/browser_use_bridge.py` strips ALL role/ARIA attributes and collapses every interactive element to one line: `  [N] <tag>[type] visible text`. There is no `role="listbox"`/`role="option"` anywhere in the text — a detector that keys off ARIA role keywords will never fire on this engine.
- **browser_use (Chrome/CDP)** — `DOMTreeSerializer` renders `[backend_node_id]<tag attr=value ... />` with **unquoted** attribute values, and puts an element's own visible/option text on a **separate following line**, not inline or in a bullet list.

**Why:** A detector/regex written by inspecting only one engine's output (or by assuming a "reasonable-looking" bullet-list/quoted-attribute format that neither engine actually produces) can silently never match in production. This was caught by reading the actual serializer source (`browser_use`'s `DOMTreeSerializer`) and the actual JS extractor source (`_CAMOUFOX_DOM_JS`) directly, plus loading a real ARIA-compliant autocomplete widget in headless Chromium to confirm the raw DOM shape — not by guessing from documentation or plausible-looking examples.

**How to apply:** Whenever adding/changing a regex-based parser over agent "observation" text (dropdown detection, form-field extraction, etc.), verify against both engines' actual current source/output before trusting the pattern, and add regression test fixtures captured from each engine's real shape (see `Backend/tests/test_address_agent.py` for an example of camoufox-shaped and browser_use-shaped fixtures side by side). Don't rely on a single assumed format working across engines.

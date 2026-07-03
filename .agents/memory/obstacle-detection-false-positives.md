---
name: Obstacle detection false positives (OTP/CAPTCHA text matching)
description: Why bare keyword regexes on page text falsely trigger OTP/CAPTCHA prompts, and the pattern used to avoid it.
---

`detect_otp`/`detect_captcha_type` in `src/services/obstacle_handler.py` match against raw tool-observation text, which can include marketing banners, FAQ copy, footer disclaimers, or unrelated field labels (promo/discount/zip/area code, SMS-signup/newsletter opt-ins) — not just an actual blocking modal.

A bare keyword match on phrases like "verification code" or "otp" is not evidence the current step is blocked; the same phrase appears constantly in incidental page text with no real input field driving it.

**Why:** A prior version of `detect_captcha_type` treated `'verification code' in text and ('type' in text or 'enter' in text)` as a captcha signal — broad enough that ordinary "enter the verification code we sent to your email" OTP copy got misclassified as captcha (checked first) and silently swallowed real OTP detection. Separately, standalone `\bverification code\b` / `\botp\b` OTP patterns fired on any incidental mention.

**How to apply:** For any new obstacle-type regex, require it to co-occur with an actionable/imperative cue (enter/type/confirm/provide, or "required/sent/to continue") within a short character window, not just a bare keyword hit — and add an explicit false-positive exclusion list (promo/discount/coupon/zip/area code, newsletter/SMS-opt-in phrasing) checked before pattern matching. Don't let one obstacle-type's detector (e.g. captcha) use keywords that belong to another type (e.g. "verification code") without requiring its own core signal (e.g. "captcha") to also be present.

# Generic obstacle-handling framework (OTP first)

## What & Why
Today the agent only has one reusable "obstacle" pattern: CAPTCHA
detection + procedural memory. Every other blocker a website can throw at
it mid-task — an emailed/texted verification code (OTP), a cookie-consent
wall, an unexpected "confirm you're human" interstitial, a forced
re-login, a paywall, a rate-limit page, etc. — currently has no shared way
to be recognized, paused on, and resolved. That's why the booking.com OTP
screen dead-ended into a generic error instead of asking the user for the
code.

Instead of writing one-off fixes each time a new blocker type shows up,
build one general **Obstacle Handler** framework, following the same
detect → pause/ask-or-retry → resume → remember shape the CAPTCHA system
already proves out, and make OTP verification the first new obstacle type
built on top of it. Once the framework exists, adding the next blocker
type later (e.g. cookie banners) is a small, contained addition instead of
new plumbing.

An OTP code sent to the user's own inbox/phone specifically requires a
human handoff — the agent can never retrieve it itself — so the OTP
instance of this framework routes through the existing in-chat
NEEDS_INPUT form flow to ask the user for the code and then resume.

## Done looks like
- A shared mechanism exists for recognizing "the run just hit a known
  obstacle mid-task" and reacting appropriately, instead of the run dying
  with a generic error.
- OTP/verification-code screens are the first obstacle type wired into
  this mechanism: the run pauses, the chat clearly asks the user for the
  code, and the run resumes once it's provided.
- The obstacle and its resolution are remembered per site/flow (like
  CAPTCHA skills today), so the same site is recognized instantly on
  future runs instead of re-discovering the pattern.
- If the user doesn't respond in time or the code is rejected, the agent
  explains that clearly instead of leaving a dead/confusing state.
- Adding a future obstacle type (e.g. cookie-consent walls) is documented
  as a small, contained addition to this same framework — not a new
  request-response pattern.

## Out of scope
- Automatically retrieving the code from the user's email/SMS inbox
  (would need a mail/SMS integration and explicit consent — flag as a
  future idea, don't build now).
- Building out every possible obstacle type now — only the shared
  framework plus the OTP instance.
- Redesigning the general NEEDS_INPUT form UI.

## Steps
1. **Extract a general obstacle-handling framework** — generalize the
   existing CAPTCHA detect/pause/resume/remember pattern into a reusable
   shape that any new obstacle type can plug into, instead of duplicating
   detection and memory logic per type.
2. **Add OTP/verification-code as the first new obstacle type** — a
   detector that recognizes "enter the code sent to your email/phone"
   patterns mid-run, using the new framework's pause/resume hook.
3. **Route OTP pauses through the existing NEEDS_INPUT form** — surface
   the code request in-chat via the same form mechanism used for missing
   task info, then resume the run with the submitted code.
4. **Persist OTP resolutions as learned procedures** — record successful
   handling per site/flow using the framework's shared memory so future
   runs recognize and pause immediately.
5. **Graceful failure messaging** — replace the current generic/dead-end
   error with a clear explanation and retry option when the user doesn't
   respond in time or the code is rejected.

## Relevant files
- `Backend/src/services/brain.py`
- `Backend/src/services/memory_service.py`
- `Backend/src/services/ATAG.py`
- `Backend/src/main.py`
- `Frontend/src/components/ui/chat_page.tsx`
